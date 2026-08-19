import json
import unittest
import urllib.error
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from ourstate_rss.generator import FeedError, build_feed, fetch_posts, normalize_posts, plain_text


FIXTURE = Path(__file__).parent / "fixtures" / "posts.json"


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200, content_type: str = "application/json"):
        self._body = body
        self.status = status
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self._body


class SequenceOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def fixture_bytes():
    return FIXTURE.read_bytes()


class GeneratorTests(unittest.TestCase):
    def test_plain_text_strips_markup_and_decodes_entities(self):
        self.assertEqual("Newest & Best", plain_text("<p>Newest &amp; <strong>Best</strong></p>"))

    def test_normalize_posts_orders_newest_first(self):
        source = list(reversed(json.loads(fixture_bytes())))
        posts = normalize_posts(source)
        self.assertEqual([103, 102, 101], [post.id for post in posts])
        self.assertEqual("Newest & Best", posts[0].title)
        self.assertEqual("A story about North Carolina.", posts[0].excerpt)

    def test_normalize_posts_rejects_external_canonical_url(self):
        source = json.loads(fixture_bytes())
        source[0]["link"] = "https://example.com/copied-story/"
        with self.assertRaisesRegex(FeedError, "canonical URL"):
            normalize_posts(source)

    def test_normalize_posts_rejects_empty_and_malformed_results(self):
        for source in ([], {}, [{"id": 1}]):
            with self.subTest(source=source):
                with self.assertRaises(FeedError):
                    normalize_posts(source)

    def test_fetch_posts_uses_limit_timeout_user_agent_and_retries(self):
        opener = SequenceOpener([
            urllib.error.URLError("temporary"),
            FakeResponse(fixture_bytes()),
        ])
        sleeps = []
        posts = fetch_posts("https://www.ourstate.com/wp-json/wp/v2/posts", limit=3, opener=opener, sleeper=sleeps.append)

        self.assertEqual(3, len(posts))
        self.assertEqual([1.0], sleeps)
        self.assertEqual(2, len(opener.requests))
        request, timeout = opener.requests[0]
        self.assertEqual(30, timeout)
        self.assertIn("per_page=3", request.full_url)
        self.assertIn("OurStateRSS", request.get_header("User-agent"))

    def test_fetch_posts_rejects_bad_status_content_type_and_json(self):
        cases = [
            FakeResponse(b"[]", status=500),
            FakeResponse(b"[]", content_type="text/html"),
            FakeResponse(b"not json"),
        ]
        for response in cases:
            with self.subTest(response=response):
                with self.assertRaises(FeedError):
                    fetch_posts("https://www.ourstate.com/wp-json/wp/v2/posts", opener=SequenceOpener([response, response]), sleeper=lambda _: None)

    def test_build_feed_has_stable_guids_dates_attribution_and_escaping(self):
        posts = normalize_posts(json.loads(fixture_bytes()))
        payload = build_feed(
            posts,
            "https://johnvoorhees.github.io/ourstate-rss/feed.xml",
            now=datetime(2026, 8, 19, 14, 0, tzinfo=UTC),
        )
        root = ET.fromstring(payload)

        self.assertEqual("rss", root.tag)
        items = root.findall("./channel/item")
        self.assertEqual(3, len(items))
        self.assertEqual("Newest & Best", items[0].findtext("title"))
        self.assertEqual("ourstate-post-103", items[0].findtext("guid"))
        self.assertEqual("false", items[0].find("guid").attrib["isPermaLink"])
        self.assertEqual("Tue, 18 Aug 2026 23:28:42 +0000", items[0].findtext("pubDate"))
        self.assertIn("A story about North Carolina.", items[0].findtext("description"))
        self.assertIn("Read the original at Our State", items[0].findtext("description"))
        self.assertNotIn("<strong>", items[0].findtext("description"))
        self.assertIn(b"Newest &amp; Best", payload)


if __name__ == "__main__":
    unittest.main()
