# Stash Scrapers

A collection of scrapers for [Stash](https://stashapp.cc/).

## Installation

1. Go to **Settings** > **Metadata Providers**
2. Click **Available Scrapers** > **Add Source**
3. Enter the source URL:
   ```
   https://thismanyboyfriends2.github.io/stash-scrapers/main/index.yml
   ```
4. Click **Confirm**

The scrapers will appear in the Available Scrapers list.

## Scrapers

| Scraper | Description |
|---------|-------------|
| **MeanBitches** | Scrapes scenes and galleries from megasite.meanworld.com. Supports URL scraping, scene search, and metadata enrichment. |
| **Performer Image Scraper** | Utility scraper that sets the currently viewed image as the attached performer's profile picture. Requires exactly one performer to be tagged on the image. |

## Dependencies

### MeanBitches

Requires Python packages: `requests`, `beautifulsoup4`, `lxml`

### Performer Image Scraper

Requires `py_common` from CommunityScrapers. Add this source to Stash:
```
https://stashapp.github.io/CommunityScrapers/stable/index.yml
```

## Licence

[AGPL-3.0](LICENCE)
