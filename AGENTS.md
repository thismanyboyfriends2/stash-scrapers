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

`docs/agents/` is gitignored and never committed — it holds the maintainer's private tooling
notes (internal issue-tracker routing, label mappings, domain-doc conventions) and won't exist in
a fresh clone or fork. If it's present, read it for that extra context; if it's absent, the
sections below are self-contained and don't depend on it.

### Issue tracker

Issues and feature requests for this repo are filed as GitHub issues
(`thismanyboyfriends2/stash-scrapers`). See `docs/agents/issue-tracker.md` if present for the
maintainer's fuller internal workflow.

### Triage labels

Five canonical triage-role labels, kept separate from this repo's own work-type labels
(bug/enhancement/etc.): `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`,
`wontfix`. See `docs/agents/triage-labels.md` if present for any repo-specific label-name mapping.

### Domain docs

Single-context layout: read `CONTEXT.md` and `docs/adr/` at the repo root before making an
architectural change, if they exist. See `docs/agents/domain.md` if present for more on how to
use them.
