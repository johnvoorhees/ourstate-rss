# Our State RSS

This project generates an unofficial, metadata-only RSS feed for personal reading from [Our State](https://www.ourstate.com/). All article content belongs to Our State and its respective authors and photographers.

The feed publishes only titles, canonical links, publication dates, short excerpts supplied by Our State, and source attribution. It does not republish full articles or images.

## Feed

Subscribe at:

`https://johnvoorhees.github.io/ourstate-rss/feed.xml`

## How it works

The generator makes one hourly read-only request for up to 20 recent posts from Our State's public WordPress REST API. It validates the response, creates RSS 2.0 XML, and replaces `docs/feed.xml` atomically only when the feed is valid and has changed.

The runtime is a launchd job on `johns-mac-mini-1`. GitHub Pages publishes the `docs` directory from the `main` branch. No inbound access to the Mac mini is required.

## Development

Run the tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Generate the feed without publishing it:

```bash
PYTHONPATH=src python3 scripts/update_feed.py
xmllint --noout docs/feed.xml
```

## Mac mini runtime

The runtime checkout is `/Users/johnvoorhees/Code/ourstate-rss`.

Run and publish manually:

```bash
/Users/johnvoorhees/Code/ourstate-rss/scripts/publish.sh
```

Inspect the LaunchAgent:

```bash
launchctl print gui/$(id -u)/com.johnvoorhees.ourstate-rss
```

Reload it after changing the plist:

```bash
launchctl bootout gui/$(id -u)/com.johnvoorhees.ourstate-rss 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.johnvoorhees.ourstate-rss.plist
```

Runtime logs are written to `logs/publish-out.log` and `logs/publish-err.log`. A failed fetch or invalid response leaves the previously published feed untouched.
