# Developing Stash Scrapers: Python Guide

Python script structure and `py_common` utilities for the scrapers that [developing-stash-scrapers](SKILL.md)'s decision table routed here — this guide assumes that decision is already made.

## Python Script Structure

Every Python scraper follows this shape — CLI args in, JSON on stdout, exit 69 on failure:

```python
#!/usr/bin/env python3
import sys
import json
from py_common import log, util
from py_common.types import ScrapedPerformer
from py_common.deps import ensure_requirements

ensure_requirements()

import requests

def performer_by_name(args):
    """Fetch performer from API by name."""
    name = args.get("name", "").strip()
    if not name:
        return {}

    try:
        api_url = f"https://api.example.com/performers?q={name}"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data or not data.get("results"):
            return {}

        result_data = data["results"][0]

        performer: ScrapedPerformer = {
            "name": util.dig(result_data, "name", default=""),
            "aliases": util.dig(result_data, "aliases", default=[]),
            "birthdate": util.dig(result_data, "birthdate", default=None),
            "images": util.dig(result_data, "images", default=[]),
        }

        return performer

    except Exception as e:
        log.error(f"Failed to scrape performer '{name}': {e}")
        return {}

if __name__ == "__main__":
    op, args = util.scraper_args()

    try:
        if op == "performer-by-name":
            result = performer_by_name(args)
        else:
            result = {}

        print(json.dumps(result))
    except Exception as e:
        log.error(f"Scraper failed: {e}")
        sys.exit(69)  # signals scraping failure to Stash
```

`ensure_requirements()` must run before importing any package it installs. Exit code 69, specifically, tells Stash the scrape failed — `sys.exit(0)` on an exception hides the failure from Stash.

## Key Utilities from py_common/

### scraper_args()
Parse CLI arguments sent from Stash:
```python
op, args = util.scraper_args()
# op: "performer-by-name", "scene-by-url", etc.
# args: {"name": "..."}, {"url": "..."}, etc.
```

### dig(obj, *keys, default=None)
Safe nested dictionary/list access with fallback defaults:
```python
title = util.dig(data, "title", default="Unknown")
subtitle = util.dig(data, "meta", ("title", "name"), default="")  # Try "title" or "name"
```

### log module
Structured logging (never use `print()` for Stash integration):
```python
from py_common import log

log.debug("Detailed information (visible in Stash logs)")
log.error("Something failed")
log.warning("Non-fatal issue")
```

### types module
TypedDict definitions for output validation:
```python
from py_common.types import ScrapedPerformer

performer: ScrapedPerformer = {
    "name": "Name",
    "aliases": ["Stage Name"],
    "birthdate": "1990-01-01",
    "measurements": {"waist": 24, "bust": 36, "hip": 35},
    "images": ["https://example.com/image.jpg"],
    # ... other optional fields
}
```

Common types:
- `ScrapedPerformer` - name (required), aliases, birthdate, measurements, social media, images
- `ScrapedScene` - title, performers, studio, tags, date, URL
- `ScrapedStudio` - name (required), URL, parent studio
- `ScrapedGallery` - title, performers, studio, tags

## Dependency Management

`ensure_requirements()` (used above) auto-installs on first run from `requirements.txt`:

```
requests>=2.28.0
beautifulsoup4>=4.11.0
lxml>=4.9.0
```

## Configuration Management

Some scrapers need API keys or user settings. Persistent configuration is stored per-scraper:

```python
from py_common.config import get_config

config = get_config("""
# API key for authentication
api_key =

# Optional setting with default
timeout = 30
""")

if not config.api_key:
    log.warning("API key not configured - scraper will fail")

api_key = config.api_key
timeout = int(config.timeout)
```

Config files persist in the scraper directory and survive scraper reinstalls.

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
    datestr = "Jan 1, 2020"
    parsed = datetime.strptime(datestr, "%b %d, %Y").isoformat()
except ValueError:
    log.warning(f"Could not parse date: {datestr}")
    parsed = None
```

## Stash GraphQL Integration (Advanced)

For scrapers that need to query Stash's own database:

```python
from py_common.graphql import StashClient
from py_common.config import get_config

config = get_config("stash_url = http://localhost:9999\napi_key =")
client = StashClient(config.stash_url, config.api_key)

# Query performers already in Stash
performers = client.query_performers(name="Query")
```

This is rarely needed - most scrapers operate on external data only.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using `print()` instead of `log.*()` | Use `from py_common import log` and `log.debug()`, `log.error()` |
| Returning XML instead of JSON | Always `json.dumps()` before `print()` |
| Fields that don't match `types.py` | Import and validate against type definitions |
| Not handling missing data | Use `dig()` with defaults instead of direct key access |
| Hardcoded absolute paths | Use relative paths or config files |
| Direct SQLite database access | Use GraphQL helpers via `py_common.graphql` when needed |
| Ignoring network errors | Wrap HTTP calls in try/except, log failures, return empty/null |
| Exit code 0 on errors | Always `sys.exit(69)` on exception for Stash to handle properly |

## Wiring it into the scraper

Add the script alongside the `.yml`, then point `action.script` at it (see [developing-stash-scrapers](SKILL.md)'s File: YourScraper.yml).

Run it standalone first — `python3 YourScraper.py performer-by-name '{"name": "Test Performer"}'`, expecting JSON on stdout — before testing in the Stash GUI (see the main skill's Testing section): a shell error is faster to read than a GUI round-trip. Debug output lands in the same `~/.stash/stash.log` covered there.
