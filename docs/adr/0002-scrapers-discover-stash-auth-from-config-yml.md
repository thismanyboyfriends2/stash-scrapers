# Scrapers that call back into Stash discover auth from Stash's config.yml

Stash gives a script scraper only the fragment on stdin: no server connection, no session, no API key. py_common's GraphQL helper reads its key from `py_common/config.ini`, which is empty on a fresh install. So on any Stash with authentication on, a scraper that calls back into Stash (the Performer Image Scraper) failed until the user edited that file by hand.

We decided that such scrapers read `api_key`, `port` and TLS settings straight from Stash's own `config.yml`. It's the same file Stash authenticates against, and the scraper runs as Stash's child process on the same machine or container, so the file is always reachable. If that has no key, they fall back to `config.ini`, and then to no key.

## Considered Options

- **`config.ini` only (the CommunityScrapers convention).** Rejected: it needs a manual step that users miss, and it goes stale when the key is regenerated.
- **An environment variable on the Stash container.** Rejected: it's still manual, and it's outside the scraper's control.
- **Rewriting it as a plugin,** which gets `server_connection` for free. Deferred: the one-click "Scrape with…" on an Image is the UX we want, and a plugin is tracked separately (#29).

## Consequences

- We depend on Stash's config layout: the `api_key`, `port`, `ssl_cert_path` and `ssl_key_path` keys at the top level, and the `stash.crt`/`stash.key` defaults. If Stash renames these, discovery quietly falls back to `config.ini`.
- The scraper bypasses `py_common.graphql` and talks to Stash with stdlib `urllib`, so it can inject the discovered key and report auth failures honestly.
- Stash fetches `performerUpdate` image URLs without auth, so the scraper sends image bytes as a base64 data URI rather than a Stash URL.
