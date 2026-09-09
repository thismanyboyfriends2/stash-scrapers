# AGENTS.md

## Project Overview

Template repo for Stash scraper source indexes — YAML definitions Stash (an adult video library app) uses to fetch metadata from websites. New scrapers follow the [Stash scraper spec](https://docs.stashapp.cc/in-app-manual/scraping/scraperdevelopment/).

## Build Commands

```bash
./build_site.sh              # build to _site/
./build_site.sh _site/main   # build to a custom directory
```

Packages each scraper YAML into a ZIP, then writes `index.yml` with metadata, git-commit-hash versions, and SHA256 checksums.

## Scraper Layout

```
scrapers/
├── simple-scraper.yml           # flat: single-file scraper
└── complex-scraper/             # nested: multi-file scraper, e.g. Python deps
    ├── scraper.yml               # main definition ('package' key marks the entry file with deps)
    └── helper.py                 # included in the ZIP
```

Metadata is grep'd from the YAML, not parsed — it must appear as literal top-level lines:

```yaml
name: "Scraper Name"
# ignore: *.pyc __pycache__    # glob patterns excluded from the ZIP
# requires: other-scraper      # comma-separated dependency IDs
```

## CI/CD

`.github/workflows/deploy.yml` builds and deploys to GitHub Pages on every push to `main` touching `scrapers/**`. Checkout uses `fetch-depth: '0'` — full history is required for `build_site.sh`'s git-commit-hash versioning, so don't shallow-clone if editing the workflow.

Published at `https://<username>.github.io/<repo>/main/index.yml`.

## Agent skills

### Issue tracker

Issues tracked in GitHub Issues (thismanyboyfriends2/stash-scrapers), via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context layout — CONTEXT.md + docs/adr/ at repo root. See `docs/agents/domain.md`.
