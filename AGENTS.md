# AGENTS.md

This file provides guidance to coding agents when working with code in this repository.

## Project Overview

This is a template repository for creating and publishing Stash scraper source indexes. Stash is an adult video library application, and scrapers are YAML definitions that fetch metadata from websites.

## Build Commands

```bash
# Build scraper packages and index (outputs to _site/)
./build_site.sh

# Build to custom directory
./build_site.sh _site/main
```

The build script:
- Packages each scraper YAML into a ZIP file
- Generates `index.yml` with metadata, versions (git commit hashes), and SHA256 checksums
- Handles both flat scrapers (`scrapers/*.yml`) and complex scrapers in subdirectories

## Architecture

### Scraper Organisation

```
scrapers/
├── simple-scraper.yml           # Flat: single-file scraper
└── complex-scraper/             # Nested: multi-file scraper
    ├── scraper.yml              # Main definition (or 'package' for dependencies)
    └── helper.py                # Supporting files included in ZIP
```

### YAML Metadata Format

Metadata is extracted from YAML files using grep:

```yaml
name: "Scraper Name"
# ignore: *.pyc __pycache__    # Glob patterns to exclude from ZIP
# requires: other-scraper      # Comma-separated dependency IDs
```

### CI/CD Pipeline

GitHub Actions (`.github/workflows/deploy.yml`) automatically:
1. Triggers on pushes to `main` affecting `scrapers/**`
2. Runs `build_site.sh` with full git history (required for versioning)
3. Deploys to GitHub Pages

Published URL: `https://<username>.github.io/<repo>/main/index.yml`

## Creating Scrapers

Scrapers follow the Stash scraper specification. See [Stash scraper development docs](https://docs.stashapp.cc/in-app-manual/scraping/scraperdevelopment/).

For multi-file scrapers with Python dependencies, use a subdirectory structure and declare dependencies with `# requires:` comments.

## Agent skills

### Issue tracker

Issues tracked in GitHub Issues (thismanyboyfriends2/stash-scrapers), via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context layout — CONTEXT.md + docs/adr/ at repo root. See `docs/agents/domain.md`.
