"""Fetch Our State post metadata and serialize it as RSS 2.0."""

from __future__ import annotations

import html
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime
from html.parser import HTMLParser
from typing import Callable, Sequence


USER_AGENT = "OurStateRSS/1.0 (+https://github.com/johnvoorhees/ourstate-rss)"
ALLOWED_HOST = "www.ourstate.com"


class FeedError(RuntimeError):
    """Raised when source data cannot safely produce a feed."""


@dataclass(frozen=True, slots=True)
class Post:
    id: int
    published: datetime
    modified: datetime
    url: str
    title: str
    excerpt: str


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def plain_text(value: str) -> str:
    """Return normalized text from a small HTML fragment."""
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return " ".join(html.unescape("".join(parser.parts)).split())


def _utc_datetime(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise FeedError(f"post {field} must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise FeedError(f"post {field} is not an ISO 8601 date") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _rendered_text(value: object, field: str) -> str:
    if not isinstance(value, dict) or not isinstance(value.get("rendered"), str):
        raise FeedError(f"post {field}.rendered is missing")
    result = plain_text(value["rendered"])
    if not result:
        raise FeedError(f"post {field} is empty")
    return result


def _canonical_url(value: object) -> str:
    if not isinstance(value, str):
        raise FeedError("post canonical URL is missing")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or not parsed.path.startswith("/"):
        raise FeedError("post canonical URL is outside www.ourstate.com")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def normalize_posts(source: object) -> list[Post]:
    """Validate and normalize WordPress post objects."""
    if not isinstance(source, list) or not source:
        raise FeedError("WordPress returned no posts")

    posts: list[Post] = []
    for raw in source:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), int):
            raise FeedError("post id is missing")
        posts.append(
            Post(
                id=raw["id"],
                published=_utc_datetime(raw.get("date_gmt"), "date_gmt"),
                modified=_utc_datetime(raw.get("modified_gmt"), "modified_gmt"),
                url=_canonical_url(raw.get("link")),
                title=_rendered_text(raw.get("title"), "title"),
                excerpt=_rendered_text(raw.get("excerpt"), "excerpt"),
            )
        )
    return sorted(posts, key=lambda post: (post.published, post.id), reverse=True)


def fetch_posts(
    api_url: str,
    limit: int = 20,
    opener: Callable[..., object] = urllib.request.urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> list[Post]:
    """Fetch recent post metadata with one bounded retry."""
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    separator = "&" if "?" in api_url else "?"
    query = urllib.parse.urlencode(
        {
            "per_page": limit,
            "orderby": "date",
            "order": "desc",
            "_fields": "id,date_gmt,modified_gmt,link,title,excerpt",
        }
    )
    request = urllib.request.Request(
        f"{api_url}{separator}{query}",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with opener(request, timeout=30) as response:
                status = getattr(response, "status", None)
                if status != 200:
                    raise FeedError(f"WordPress returned HTTP {status}")
                content_type = response.headers.get("Content-Type", "")
                if not content_type.lower().startswith("application/json"):
                    raise FeedError(f"WordPress returned {content_type or 'an unknown content type'}")
                try:
                    source = json.loads(response.read())
                except (json.JSONDecodeError, UnicodeDecodeError) as error:
                    raise FeedError("WordPress returned malformed JSON") from error
                return normalize_posts(source)
        except (FeedError, OSError, urllib.error.URLError) as error:
            last_error = error
            if attempt == 0:
                sleeper(1.0)
    raise FeedError(f"unable to fetch Our State posts: {last_error}") from last_error


def _rfc2822(value: datetime) -> str:
    return format_datetime(value.astimezone(UTC))


def build_feed(posts: Sequence[Post], feed_url: str, now: datetime | None = None) -> bytes:
    """Build deterministic RSS 2.0 bytes from normalized posts."""
    if not posts:
        raise FeedError("cannot build an empty feed")
    if now is not None and now.tzinfo is None:
        raise ValueError("now must include a timezone")

    ET.register_namespace("atom", "http://www.w3.org/2005/Atom")
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Our State — Personal RSS Mirror"
    ET.SubElement(channel, "link").text = "https://www.ourstate.com/"
    ET.SubElement(channel, "description").text = (
        "Unofficial metadata-only feed for personal reading. All articles belong to Our State."
    )
    ET.SubElement(channel, "language").text = "en-US"
    latest_modified = max(post.modified for post in posts)
    ET.SubElement(channel, "lastBuildDate").text = _rfc2822(latest_modified)
    ET.SubElement(
        channel,
        "{http://www.w3.org/2005/Atom}link",
        {"href": feed_url, "rel": "self", "type": "application/rss+xml"},
    )

    for post in posts:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = post.title
        ET.SubElement(item, "link").text = post.url
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = f"ourstate-post-{post.id}"
        ET.SubElement(item, "pubDate").text = _rfc2822(post.published)
        ET.SubElement(item, "description").text = (
            f"<p>{html.escape(post.excerpt)}</p>"
            f'<p><a href="{html.escape(post.url, quote=True)}">Read the original at Our State</a>.</p>'
        )

    ET.indent(rss, space="  ")
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)
