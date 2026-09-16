---
name: developing-stash-scrapers
description: Use when creating or modifying a Stash scraper (performer, scene, gallery, or studio)
---

# Developing Stash Scrapers

## Overview

Stash scrapers extract metadata (performer info, scene details, images) from external websites and return JSON to Stash. A scraper is a YAML config plus an optional Python script. This repo builds and publishes them as an index — see `AGENTS.md`'s **Scraper Layout** and **CI/CD** sections for the ZIP/`index.yml` packaging and the `# ignore:`/`# requires:` metadata comments `build_site.sh` greps out; this skill doesn't repeat that.

**Official docs:** [scraper development](https://docs.stashapp.cc/in-app-manual/scraping/scraperdevelopment/), [scraping manual](https://docs.stashapp.cc/in-app-manual/scraping/).

## YAML-first

Start every scraper in YAML. Reach for Python only where the table's right column says so — YAML can't do it.

| Scenario | Use |
|----------|-----|
| Static HTML, CSS/XPath selectors, JSON in `<script>` tags | YAML XPath |
| Regex cleanup, date parsing, value mapping | YAML `postProcess` (see Common YAML Patterns below) |
| JavaScript-rendered pages | YAML XPath with `driver: { useCDP: true }` (see `onlyfans-performer/onlyfans-performer.yml`) — needs Chrome CDP path set in Stash's System settings, not a Python browser driver |
| HTTP auth/headers, pagination, JSON APIs | Python — see [developing-stash-scrapers-python](developing-stash-scrapers-python.md) |
| Anti-bot bypass (CloudFlare), rate limiting, retries | Python |
| Cross-source matching logic | Python |

## File: YourScraper.yml

Follow `AGENTS.md`'s Scraper Layout for where the file goes (flat `scrapers/name.yml` vs. nested `scrapers/name/name.yml`) and its metadata comments (`name:`, `# ignore:`, `# requires:`). Minimum viable XPath scraper:

```yaml
name: "Your Scraper Name"

performerByURL:
  - action: scrapeXPath
    url:
      - "example.com/profile"
    scraper: performerScraper

xPathScrapers:
  performerScraper:
    performer:
      Name:
        selector: "//div[@class='performer-info']//h1"
      Birthdate:
        selector: "//div[@class='performer-info']//span[@class='dob']"
        postProcess:
          - parseDate: "MMM dd, yyyy"
```

For complex logic, point to a Python script instead (see `scrapers/x-tweet/x-tweet.yml` for the full set of operations one scraper can expose):

```yaml
sceneByURL:
  - action: script
    url:
      - "example.com/"
    script:
      - python3
      - YourScraper.py
      - scene-by-url
```

## Creating a New Scraper

1. Create the scraper file under `scrapers/` per `AGENTS.md`'s Scraper Layout (flat or nested — nested only if you need a `.py`/`requirements.txt` alongside it).
2. Write the YAML (see File: YourScraper.yml above), using XPath for everything the table above marks YAML.
3. Test in the Stash GUI (see Testing below). Done when every DevTools-verified selector returns the right element and the returned data is complete.
4. Only if a table row above says Python: add `YourScraper.py` — see [developing-stash-scrapers-python](developing-stash-scrapers-python.md).
5. Add the scraper to the README's Scrapers table (and Dependencies section if it needs anything beyond `py_common`).

## Common YAML Patterns

`postProcess` entries nest their args under the transform's own key (`replace:`, `parseDate:`, `map:`), not a `type:`/`field:` pair — see `scrapers/cruel-girlfriend/CruelGirlfriend.yml` and `scrapers/onlyfans-performer/onlyfans-performer.yml` for real usage.

### Using Regex to Clean Text
```yaml
postProcess:
  - replace:
      - regex: ^\s+|\s+$
        with: ""
```
`regex` can capture groups and `with` back-reference them (`$1`) — used in `CruelGirlfriend.yml` to pull a value out of a JSON blob embedded in a `<script>` tag.

### Parsing Dates
```yaml
postProcess:
  - parseDate: "MMM dd, yyyy"
```

### Extracting JSON from Script Tags
XPath can extract JSON embedded in `<script>` tags, then `replace` regexes a field out of it (see `CruelGirlfriend.yml`'s `$script` variable):
```yaml
selector: "//script[@type='application/ld+json']"
postProcess:
  - replace:
      - regex: '(?s).+"name":\s*"([^"]+)".+'
        with: $1
```

### Mapping Values
```yaml
postProcess:
  - map:
      "active": "Active"
      "retired": "Retired"
```

## Testing Your Scraper

### Testing in Stash GUI (Primary Method)
1. Copy the scraper's directory (or its lone `.yml` for a flat scraper) into your local Stash installation's `scrapers/` folder — this repo's `build_site.sh`/`index.yml` publishing is for distribution, not needed for local iteration
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

- Simple YAML: `scrapers/onlyfans-performer/onlyfans-performer.yml` — XPath-only performer scraper, plus the `driver: useCDP` pattern for JS-rendered pages.
- Complex YAML: `scrapers/cruel-girlfriend/CruelGirlfriend.yml` — XPath variables (`$script`), `queryURLReplace` regex chains, scene/gallery fragment scraping.
- Python: see [developing-stash-scrapers-python](developing-stash-scrapers-python.md) for the real dispatch pattern, `py_common` usage, and error handling, drawn from `scrapers/MeanBitches/MeanBitches.py`, `scrapers/x-tweet/x-tweet.py`, and `scrapers/performer-image-scraper/performer-image-scraper.py`.
