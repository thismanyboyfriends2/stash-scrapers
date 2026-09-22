#!/usr/bin/env python3
"""
Performer Image Scraper
Sets the current image being scraped as the attached performer's profile picture.
Requires exactly one performer to be attached to the image.

Stash gives a script scraper nothing but the fragment on stdin, so the
scraper finds Stash's API key and port itself, from Stash's own config.yml.
See docs/adr/0002-scrapers-discover-stash-auth-from-config-yml.md.
"""
import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import NoReturn

try:
    import py_common
    from py_common import log
except ModuleNotFoundError:
    print(
        "py_common not found. Add the CommunityScrapers source to Stash:\n"
        "https://stashapp.github.io/CommunityScrapers/stable/index.yml",
        file=sys.stderr
    )
    sys.exit(1)


UNVERIFIED_TLS = ssl.create_default_context()
UNVERIFIED_TLS.check_hostname = False
UNVERIFIED_TLS.verify_mode = ssl.CERT_NONE


class StashError(Exception):
    """A failure talking to Stash, with a message fit for the user."""


def read_config_values(path):
    """Read top-level `key: value` scalars from a Stash config.yml."""
    values = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line[0] in " \t#-":
                continue
            key, sep, value = line.partition(":")
            if not sep:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            values[key.strip()] = value
    return values


def find_stash_config():
    """Locate Stash's config.yml, or None if it can't be found.

    Checked in order: $STASH_CONFIG_FILE (set by the official Docker image),
    the config dir this scraper is installed under (<config>/scrapers/<name>/),
    then the default ~/.stash.
    """
    candidates = []
    if os.environ.get("STASH_CONFIG_FILE"):
        candidates.append(Path(os.environ["STASH_CONFIG_FILE"]))
    candidates.append(Path(__file__).resolve().parent.parent.parent / "config.yml")
    candidates.append(Path.home() / ".stash" / "config.yml")
    return next((p for p in candidates if p.is_file()), None)


def read_py_common_api_key():
    """Read api_key from py_common's config.ini, the community-standard place."""
    ini = Path(py_common.__file__).parent / "config.ini"
    if not ini.is_file():
        return None
    for line in ini.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == "api_key":
            return value.strip() or None
    return None


def uses_tls(config, config_dir):
    """Mirror Stash's InitTLS: cert and key from config, else stash.crt/stash.key
    in the config dir or ~/.stash."""
    search = [d for d in (config_dir, Path.home() / ".stash") if d]

    def find(setting, default_name):
        if config.get(setting):
            return config[setting]
        return next((d / default_name for d in search if (d / default_name).is_file()), None)

    return bool(find("ssl_cert_path", "stash.crt") and find("ssl_key_path", "stash.key"))


class StashConnection:
    def __init__(self, base_url, api_key, key_source=None):
        self.base_url = base_url
        self.api_key = api_key
        self.key_source = key_source

    @classmethod
    def discover(cls):
        config_path = find_stash_config()
        config = read_config_values(config_path) if config_path else {}
        port = config.get("port") or "9999"
        scheme = "https" if uses_tls(config, config_path.parent if config_path else None) else "http"
        base_url = f"{scheme}://localhost:{port}"

        if config.get("api_key"):
            return cls(base_url, config["api_key"], str(config_path))
        ini_key = read_py_common_api_key()
        if ini_key:
            return cls(base_url, ini_key, "py_common/config.ini")
        return cls(base_url, None)

    def _request(self, path, data=None):
        headers = {}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["ApiKey"] = self.api_key
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers)
        try:
            # Stash is on localhost and usually self-signed: don't verify
            return urllib.request.urlopen(request, timeout=30, context=UNVERIFIED_TLS)
        except urllib.error.HTTPError as e:
            if e.code == 401 and not self.api_key:
                raise StashError(
                    "Stash has authentication enabled but no API key was found. "
                    "Generate one in Stash under Settings → Security."
                ) from e
            if e.code == 401:
                raise StashError(
                    f"Stash rejected the API key from {self.key_source}. "
                    "It may have been regenerated; check Settings → Security."
                ) from e
            raise StashError(f"Stash returned HTTP {e.code} for {path.split('?')[0]}") from e
        except (urllib.error.URLError, OSError) as e:
            reason = getattr(e, "reason", e)
            raise StashError(f"Could not connect to Stash at {self.base_url}: {reason}") from e

    def graphql(self, query, variables):
        payload = json.dumps({"query": query, "variables": variables}).encode()
        with self._request("/graphql", payload) as response:
            result = json.load(response)
        if result.get("errors"):
            messages = "; ".join(e.get("message", "") for e in result["errors"])
            raise StashError(f"Stash returned GraphQL errors: {messages}")
        return result.get("data") or {}

    def fetch_data_uri(self, url):
        """Download a Stash-served file and return it as a base64 data URI.

        Only the path is kept: the host in the URL is whatever Stash believes
        it is reached by, which may not be reachable from here.
        """
        parts = urllib.parse.urlsplit(url)
        path = urllib.parse.urlunsplit(("", "", parts.path, parts.query, ""))
        with self._request(path) as response:
            content_type = response.headers.get_content_type()
            data = response.read()
        return f"data:{content_type};base64,{base64.b64encode(data).decode()}"


FIND_IMAGE = """
    query FindImage($image_id: ID!) {
        findImage(id: $image_id) {
            id
            paths {
                image
            }
            performers {
                id
                name
            }
        }
    }
"""

UPDATE_PERFORMER = """
    mutation PerformerUpdate($input: PerformerUpdateInput!) {
        performerUpdate(input: $input) {
            id
            name
        }
    }
"""


def announce_result_to_stash(result) -> NoReturn:
    """Output result to Stash via stdout."""
    if result is None:
        result = {}
    print(json.dumps(result))
    sys.exit(0)


def main():
    try:
        run()
    except StashError as e:
        log.error(str(e))
        announce_result_to_stash(None)


def run():
    fragment = json.loads(sys.stdin.read())

    image_id = fragment.get("id")
    if not image_id:
        log.error("No image ID provided in fragment")
        announce_result_to_stash(None)

    log.debug(f"Processing image ID: {image_id}")

    stash = StashConnection.discover()
    image = stash.graphql(FIND_IMAGE, {"image_id": str(image_id)}).get("findImage")

    if not image:
        log.error(f"Image {image_id} not found in Stash")
        announce_result_to_stash(None)

    performers = image.get("performers") or []
    image_url = (image.get("paths") or {}).get("image")

    if not image_url:
        log.error(f"Image {image_id} has no image path")
        announce_result_to_stash(None)

    if len(performers) == 0:
        log.error(f"Image {image_id} has no performers attached")
        announce_result_to_stash(None)
    elif len(performers) > 1:
        performer_names = ", ".join(p.get("name", "Unknown") for p in performers)
        log.error(f"Image {image_id} has multiple performers: {performer_names}")
        announce_result_to_stash(None)

    performer = performers[0]
    performer_id = performer.get("id")
    performer_name = performer.get("name", "Unknown")

    log.debug(f"Updating performer '{performer_name}' (ID: {performer_id}) with image {image_id}")

    image_data = stash.fetch_data_uri(image_url)
    updated = stash.graphql(UPDATE_PERFORMER, {"input": {"id": performer_id, "image": image_data}})

    if not updated.get("performerUpdate"):
        log.error(f"Failed to update performer {performer_id} image")
        announce_result_to_stash(None)

    log.info(f"Successfully updated performer '{performer_name}' profile image")

    # Return empty result - the performer's image has been updated
    announce_result_to_stash({})


if __name__ == "__main__":
    main()
