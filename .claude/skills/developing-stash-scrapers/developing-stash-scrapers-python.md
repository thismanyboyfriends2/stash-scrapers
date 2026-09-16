# Developing Stash Scrapers: Python Guide

Python script structure and `py_common` conventions for the scrapers that [developing-stash-scrapers](SKILL.md)'s decision table routed here — this guide assumes that decision is already made.

## `py_common` is not vendored here

`py_common` ships with Stash's [CommunityScrapers](https://stashapp.github.io/CommunityScrapers/stable/index.yml) source, not with this repo — it only exists on a user's machine if they've added that source to Stash. Every import must be guarded, and the YAML must declare the dependency so `build_site.sh` records it in `index.yml` (see `AGENTS.md`'s `# requires:` convention):

```python
try:
    from py_common import log, util
except ModuleNotFoundError:
    print(
        "py_common not found. Add the CommunityScrapers source to Stash:\n"
        "https://stashapp.github.io/CommunityScrapers/stable/index.yml",
        file=sys.stderr,
    )
    sys.exit(1)
```

```yaml
# requires: py_common
```

Real examples of the guard: `scrapers/x-tweet/x-tweet.py`, `scrapers/performer-image-scraper/performer-image-scraper.py`.

`py_common`'s own API isn't in this repo to grep — if you need something beyond what's used in the three example scripts below, check it in a local Stash installation's `py_common` source (under CommunityScrapers) rather than guessing the signature.

## Python Script Structure

Every Python scraper in this repo follows this shape — operation name as `sys.argv[1]`, JSON args on stdin, JSON on stdout, exit 69 on failure (this is what tells Stash the scrape failed — `sys.exit(0)` on an exception hides the failure). Based on `scrapers/MeanBitches/MeanBitches.py`:

```python
#!/usr/bin/env python3
import json
import sys

from py_common import log


def read_json_input() -> dict:
    """Read and parse the JSON args Stash pipes in on stdin."""
    try:
        raw = sys.stdin.read()
        if not raw:
            log.error("No input data received")
            sys.exit(69)
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        log.error(f"Error reading input: {e}")
        sys.exit(69)


def scrape_scene_url(url: str) -> dict:
    try:
        # ... fetch and parse ...
        return {"title": "..."}
    except Exception as e:
        log.error(f"Failed to scrape '{url}': {e}")
        return {}


if __name__ == "__main__":
    input_data = read_json_input()
    operation = sys.argv[1] if len(sys.argv) > 1 else "unknown"

    if operation == "scrapeSceneURL":
        print(json.dumps(scrape_scene_url(input_data.get("url"))))
    else:
        log.error(f"Unknown operation: {operation}")
        sys.exit(69)
```

The `if __name__ == "__main__":` guard matters: without it, importing this module (e.g. from a test) re-runs the dispatch against real stdin.

## `py_common` usage seen in this repo

### `log`
Structured logging — never use `print()` for anything except the final JSON result, since stdout is Stash's parse channel:
```python
from py_common import log

log.debug("Detailed information (visible in Stash logs)")
log.error("Something failed")
log.warning("Non-fatal issue")
```

### `py_common.cache.cache_to_disk`
Used in `MeanBitches.py` to cache expensive scrapes:
```python
from py_common.cache import cache_to_disk

@cache_to_disk(ttl=3600)  # seconds
def scrapeSceneURL(url: str) -> dict:
    ...
```

### `py_common.graphql`
Used in `performer-image-scraper.py` to query Stash's own database (e.g. resolving the performer attached to the image currently being scraped) — rarely needed; most scrapers only touch external data.

## Dependency Management

Third-party packages beyond `py_common` go in `requirements.txt` next to the scraper (see `scrapers/MeanBitches/requirements.txt`):
```
requests>=2.28.0
beautifulsoup4>=4.11.0
lxml>=4.9.0
```

## Common Patterns

### Making HTTP Requests
```python
import requests

try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.RequestException as e:
    log.error(f"HTTP request failed: {e}")
    return {}
```

### Parsing HTML with BeautifulSoup
```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html_content, "html.parser")
name = soup.find("h1", class_="performer-name")
if name:
    name_text = name.get_text(strip=True)
```

### Handling Dates
```python
from datetime import datetime

try:
    parsed = datetime.strptime(datestr, "%b %d, %Y").isoformat()
except ValueError:
    log.warning(f"Could not parse date: {datestr}")
    parsed = None
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Importing `py_common` without a `try`/`except ModuleNotFoundError` guard | It's an external dependency, not vendored here — guard it (see above) and print the CommunityScrapers install URL |
| Adding `# requires: py_common` only to the script, not the YAML | `build_site.sh` greps `# requires:` from the `.yml`, not the `.py` — the index needs it there |
| Using `print()` instead of `log.*()` for anything but the final result | Stash parses stdout as the scrape output; stray prints corrupt it |
| Missing the `if __name__ == "__main__":` guard | Dispatch runs on import, consuming stdin unexpectedly |
| Returning XML instead of JSON | Always `json.dumps()` before `print()` |
| Ignoring network errors | Wrap HTTP calls in try/except, log failures, return `{}` |
| Exit code 0 on errors | Always `sys.exit(69)` on failure so Stash knows the scrape failed |

## Wiring it into the scraper

Add the script alongside the `.yml` (nested layout, per `AGENTS.md`'s Scraper Layout), then point `action.script` at it (see [developing-stash-scrapers](SKILL.md)'s File: YourScraper.yml).

Run it standalone first — `echo '{"name": "Test Performer"}' | python3 YourScraper.py performer-by-name`, expecting JSON on stdout — before testing in the Stash GUI (see the main skill's Testing section): a shell error is faster to read than a GUI round-trip. Debug output lands in the same `~/.stash/stash.log` covered there.
