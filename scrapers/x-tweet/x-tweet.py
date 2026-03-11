#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone

import requests
from py_common import log, util


def parse_tweet_url(url: str) -> tuple[str, str]:
    """Return (username, tweet_id) from an x.com or twitter.com status URL."""
    match = re.search(r'(?:twitter|x)\.com/([^/?]+)/status/(\d+)', url)
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def scrape_scene_by_url(url: str) -> dict:
    username, tweet_id = parse_tweet_url(url)
    if not tweet_id:
        log.error(f"Could not extract tweet ID from URL: {url}")
        return {}

    api_url = f"https://api.fxtwitter.com/{username}/status/{tweet_id}"
    log.debug(f"Fetching: {api_url}")

    try:
        response = requests.get(api_url, timeout=15)
        data = response.json()
    except requests.exceptions.RequestException as e:
        log.error(f"Request failed: {e}")
        return {}

    if data.get("code") != 200:
        log.warning(f"fxtwitter API returned {data.get('code')}: {data.get('message')}")
        return {
            "code": tweet_id,
            "url": url,
            "studio": {"name": username},
            "performers": [{"name": username}],
            "tags": [{"name": "Missing or removed"}],
        }

    tweet = data.get("tweet", {})
    text = tweet.get("text", "")
    author = tweet.get("author", {})

    # Date from unix timestamp
    date = None
    timestamp = tweet.get("created_timestamp")
    if timestamp:
        date = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).strftime("%Y-%m-%d")

    # Title: first non-empty line of tweet text
    first_line = next((line for line in text.splitlines() if line.strip()), text)

    # Use screen_name (handle) for both studio and performer
    handle = author.get("screen_name") or username

    # Tags: prefer API-provided hashtags list, fall back to regex on text
    hashtags = tweet.get("hashtags")
    raw_tags = hashtags if hashtags is not None else re.findall(r'#(\w+)', text)
    tags = [{"name": tag} for tag in raw_tags]

    return {
        "title": first_line,
        "date": date,
        "code": tweet_id,
        "details": text,
        "url": url,
        "studio": {"name": handle},
        "performers": [{"name": handle}],
        "tags": tags,
    }


if __name__ == "__main__":
    op, args = util.scraper_args()
    log.debug(f"Operation: {op}")

    if op == "scene-by-url":
        result = scrape_scene_by_url(str(args.get("url", "")))
        print(json.dumps(result))
    else:
        log.error(f"Unknown operation: {op}")
        sys.exit(69)
