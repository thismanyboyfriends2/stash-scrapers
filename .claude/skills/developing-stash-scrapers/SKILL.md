---
name: developing-stash-scrapers
description: Use when creating or modifying a Stash scraper (performer, scene, gallery, or studio)
---

# Developing Stash Scrapers

## Overview

Stash scrapers extract metadata (performer info, scene details, images) from external websites and return JSON to Stash. A scraper is a YAML config plus an optional Python script, sharing utilities from `py_common/`.

**Official docs:** [scraper development](https://docs.stashapp.cc/in-app-manual/scraping/scraperdevelopment/), [scraping manual](https://docs.stashapp.cc/in-app-manual/scraping/).

## YAML-first

Start every scraper in YAML. Reach for Python only where the table's right column says so — YAML can't do it.

| Scenario | Use |
|----------|-----|
| Static HTML, CSS/XPath selectors, JSON in `<script>` tags | YAML XPath |
| Regex cleanup, date parsing, value mapping | YAML `postProcess` (see Common YAML Patterns below) |
| HTTP auth/headers, pagination, JSON APIs | Python — see [developing-stash-scrapers-python](developing-stash-scrapers-python.md) |
| JavaScript rendering (Selenium/Playwright) | Python |
| Anti-bot bypass (CloudFlare), rate limiting, retries | Python |
| Cross-source matching logic | Python |

## Directory Layout

```
YourScraper/
├── YourScraper.yml       # Metadata and XPath rules
├── YourScraper.py        # Python logic (if needed)
├── requirements.txt      # Dependencies (if needed)
└── manifest              # Version metadata
```

## File: YourScraper.yml

Minimum viable YAML structure:

```yaml
# Name displayed in Stash GUI
name: "Your Scraper Name"

# Scraper type: performer, scene, gallery, studio
scraperType: "performer"

# URL patterns this scraper handles
urls:
  - "example.com/profile"

# XPath-based action
action:
  type: "xpathAction"
  xpathSelector: "//div[@class='performer-info']"
  postProcess:
    - type: "parseDate"
      field: "birthdate"
      format: "MMM dd, yyyy"
```

For complex logic, point to Python script instead:

```yaml
action:
  type: "script"
  script:
    - python3
    - YourScraper.py
    - operation-name
```

## File: manifest

Metadata for your scraper:

```
id: yourscrapername
version: "0.1"
date: "2025-01-28"
```

## Creating a New Scraper

1. `mkdir YourScraper && cd YourScraper`
2. Write `manifest` (see File: manifest below).
3. Write `YourScraper.yml` (see File: YourScraper.yml below), using XPath for everything the table above marks YAML.
4. Test in the Stash GUI (see Testing below). Done when every DevTools-verified selector returns the right element and the returned data is complete.
5. Only if a table row above says Python: add `YourScraper.py` — see [developing-stash-scrapers-python](developing-stash-scrapers-python.md).

## Common YAML Patterns

### Using Regex to Clean Text
PostProcess with regex replacement:
```yaml
postProcess:
  - type: "replace"
    regex: "[^a-zA-Z0-9]"
    with: ""
```

### Parsing Dates
Use PostProcess with date format specification:
```yaml
postProcess:
  - type: "parseDate"
    field: "birthdate"
    format: "MMM dd, yyyy"
```

### Extracting JSON from Script Tags
XPath can extract JSON embedded in `<script>` tags:
```yaml
xpathSelector: "//script[@type='application/json']/text()"
```

### Mapping Values
PostProcess can map values to standardised forms:
```yaml
postProcess:
  - type: "map"
    field: "status"
    map:
      "active": "Active"
      "retired": "Retired"
```

### Handling Images
Extract image URLs via XPath and include in output. Stash automatically downloads and manages images from returned URLs:
```yaml
postProcess:
  - type: "trim"  # Clean whitespace from URLs
```

## Testing Your Scraper

### Testing in Stash GUI (Primary Method)
1. Copy scraper directory to Stash's `scrapers/` folder
2. In Stash, search for a performer or navigate to content
3. Trigger the scraper from the GUI
4. Verify returned data is accurate and complete

### Debugging XPath Selectors
Use browser DevTools:
1. Open the target website in your browser
2. Right-click → Inspect to open DevTools
3. Test XPath in the console: `$x("//xpath/selector")`
4. Refine selectors until they return correct elements
5. Update your YAML with verified selectors

### Checking Stash Logs
View `~/.stash/stash.log` (or `C:\Users\YourName\.stash\stash.log` on Windows) for:
- Scraper input/output (logged at ERROR level)
- XPath evaluation results
- PostProcess transformation steps
- Error messages or parsing failures

## Edge Cases in YAML

- **Missing elements** → Return null or empty value (Stash handles gracefully)
- **Multiple matching elements** → XPath returns first match by default; adjust selector specificity if needed
- **Invalid dates** → PostProcess `parseDate` validates format; invalid dates are skipped
- **Special characters** → PostProcess `replace` can sanitise text before returning
- **Image URLs that expire** → Return URLs; Stash handles downloads

## Done means

- Every XPath selector was verified in browser DevTools (`$x("//xpath/selector")`), not guessed.
- Every extracted field has a fallback for when it's missing (see Edge Cases above).
- The scraper ran in the Stash GUI against a real URL and returned complete, correct data.
- Python exists only for rows the table above assigned to Python — everything else stayed YAML.

## Real Examples

- Simple YAML: any scraper with just a `.yml` file, no `.py`.
- Complex YAML: `DominaPlanet.yml` — advanced XPath variables, PostProcess chaining.
- Python: see [developing-stash-scrapers-python](developing-stash-scrapers-python.md) for examples, script structure, `py_common` utilities, error handling, and dependency auto-installation.
