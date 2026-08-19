import tempfile
import unittest
from pathlib import Path

from ourstate_rss.generator import FeedError
from scripts.update_feed import write_feed


VALID_A = b'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>A</title></channel></rss>'
VALID_B = b'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>B</title></channel></rss>'
INVALID = b'<rss><channel>'


class UpdateFeedTests(unittest.TestCase):
    def test_write_feed_creates_missing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "docs" / "feed.xml"
            self.assertTrue(write_feed(destination, VALID_A))
            self.assertEqual(VALID_A, destination.read_bytes())

    def test_write_feed_does_not_rewrite_identical_content(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "feed.xml"
            destination.write_bytes(VALID_A)
            before = destination.stat().st_mtime_ns
            self.assertFalse(write_feed(destination, VALID_A))
            self.assertEqual(before, destination.stat().st_mtime_ns)

    def test_write_feed_atomically_replaces_changed_content(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "feed.xml"
            destination.write_bytes(VALID_A)
            self.assertTrue(write_feed(destination, VALID_B))
            self.assertEqual(VALID_B, destination.read_bytes())
            self.assertEqual([], list(destination.parent.glob(".feed.xml.*.tmp")))

    def test_write_feed_rejects_invalid_xml_and_preserves_previous_feed(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "feed.xml"
            destination.write_bytes(VALID_A)
            with self.assertRaisesRegex(FeedError, "invalid RSS XML"):
                write_feed(destination, INVALID)
            self.assertEqual(VALID_A, destination.read_bytes())


if __name__ == "__main__":
    unittest.main()
