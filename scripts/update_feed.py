#!/usr/bin/env python3
"""Update the published Our State RSS document atomically."""

from __future__ import annotations

import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from ourstate_rss.generator import FeedError, build_feed, fetch_posts


API_URL = "https://www.ourstate.com/wp-json/wp/v2/posts"
PUBLIC_FEED_URL = "https://johnvoorhees.github.io/ourstate-rss/feed.xml"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPOSITORY_ROOT / "docs" / "feed.xml"


def _validate_rss(content: bytes) -> None:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as error:
        raise FeedError(f"invalid RSS XML: {error}") from error
    if root.tag != "rss" or root.attrib.get("version") != "2.0" or root.find("channel") is None:
        raise FeedError("invalid RSS XML: expected an RSS 2.0 channel")


def write_feed(destination: Path, content: bytes) -> bool:
    """Validate and atomically write content, returning whether it changed."""
    _validate_rss(content)
    if destination.exists() and destination.read_bytes() == content:
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path.replace(destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return True


def main() -> int:
    try:
        posts = fetch_posts(API_URL, limit=20)
        content = build_feed(posts, PUBLIC_FEED_URL)
        changed = write_feed(OUTPUT_PATH, content)
    except FeedError as error:
        print(f"Our State RSS update failed: {error}", file=sys.stderr)
        return 1

    state = "updated" if changed else "unchanged"
    print(f"Our State RSS {state}: {len(posts)} items at {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
