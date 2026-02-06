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
| **Cruel Girlfriend** | Scrapes scenes and galleries from cruelgf.com. Extracts title, date, description, tags, performers (from page title), and cover image. Supports both direct clip URLs and ThePornDB-style `.html` URLs. |
| **MeanBitches** | Scrapes scenes and galleries from megasite.meanworld.com. Supports URL scraping, scene search, and metadata enrichment. |
| **OnlyFans Performer Scraper** | Scrapes performer metadata from OnlyFans profile pages. Extracts display name (as alias), bio, profile image, and all linked URLs (social media, wishlists, etc.). |
| **Performer Image Scraper** | Utility scraper that sets the currently viewed image as the attached performer's profile picture. Requires exactly one performer to be tagged on the image. |

## Dependencies

### MeanBitches

Requires Python packages: `requests`, `beautifulsoup4`, `lxml`

### OnlyFans Performer Scraper

Requires Chrome DevTools Protocol (CDP) for JavaScript rendering. Configure the Chrome path in Stash:

1. Go to **Settings** > **System**
2. Set **Chrome CDP path** to your Chrome/Chromium executable, e.g.:
   - Windows: `C:\Program Files\Google\Chrome\Application\chrome.exe`
   - Linux: `/usr/bin/chromium`
   - macOS: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`

### Performer Image Scraper

Requires `py_common` from CommunityScrapers. Add this source to Stash:
```
https://stashapp.github.io/CommunityScrapers/stable/index.yml
```

## Licence

[AGPL-3.0](LICENCE)
