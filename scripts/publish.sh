#!/bin/bash

set -euo pipefail

REPO_DIR="/Users/johnvoorhees/Code/ourstate-rss"
LOCK_DIR="$REPO_DIR/.publish.lock"

cd "$REPO_DIR"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Our State RSS publisher is already running; skipping."
  exit 0
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT

git pull --quiet --ff-only origin main
PYTHONPATH=src python3 scripts/update_feed.py

if git diff --quiet -- docs/feed.xml; then
  echo "Our State RSS has no changes to publish."
  exit 0
fi

git add -- docs/feed.xml
git commit -m "Update Our State feed" -- docs/feed.xml
git push --quiet origin main
