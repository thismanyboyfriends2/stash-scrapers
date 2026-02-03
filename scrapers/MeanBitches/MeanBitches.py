import json
import sys
import re
import html
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from difflib import SequenceMatcher
from bs4 import BeautifulSoup
from py_common import log
from py_common.cache import cache_to_disk


# Constants
BASE_URL = "https://megasite.meanworld.com"
DEFAULT_DIRECTOR = "Glenn King"
MAX_SEARCH_PAGES = 5


def fetch_html(url: str, timeout: int = 10, params: Optional[dict] = None) -> str:
    """Fetch HTML content from URL with error handling.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        params: Optional dict of query parameters

    Returns:
        HTML content as string

    Raises:
        ValueError: If URL is invalid
        Exception: Network or parsing errors

    Note: High-level caching is provided by search_scenes_by_name() and scrapeSceneURL()
    to minimize redundant network requests.
    """
    if not url or not isinstance(url, str):
        raise ValueError(f"Invalid URL: {url}")

    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as e:
        raise Exception(f"HTTP Error {e.response.status_code}: {str(e)}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error: {str(e)}")


def normalize_url(url: str) -> Optional[str]:
    """Convert relative URL to absolute URL."""
    if not url or not isinstance(url, str):
        return None

    url = url.strip()
    return f"{BASE_URL}{url}" if url.startswith('/') else url or None


def extract_title_from_filename(filename: str) -> Optional[str]:
    """Extract title from video filename by removing path and extension."""
    if not filename or not isinstance(filename, str):
        return None

    filename = filename.strip()
    if not filename:
        return None

    # pathlib.Path.stem removes both path and extension
    title = Path(filename).stem
    return title if title else None


def readJSONInput() -> dict:
    """Read and parse JSON input from stdin.

    Returns:
        Parsed JSON data as dict

    Raises:
        SystemExit: On JSON parsing error
    """
    try:
        input_data = sys.stdin.read()
        if not input_data:
            log.error("No input data received")
            sys.exit(69)
        parsed = json.loads(input_data)
        log.debug(f"Input received: {json.dumps(parsed)}")
        return parsed
    except json.JSONDecodeError as e:
        log.error(f"Invalid JSON input: {str(e)}")
        sys.exit(69)
    except Exception as e:
        log.error(f"Error reading input: {str(e)}")
        sys.exit(69)


def extract_title(html_content: str) -> Optional[str]:
    """Extract title from data-title attribute of packageinfo div."""
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        packageinfo = soup.find('div', id=re.compile(r'packageinfo_\d+'))
        if packageinfo and packageinfo.get('data-title'):
            return html.unescape(str(packageinfo['data-title']))
    except Exception as e:
        log.debug(f"Error extracting title: {str(e)}")
    return None


def extract_details(html_content: str) -> Optional[str]:
    """Extract details from vidImgContent paragraph."""
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        vid_content = soup.find('div', class_=re.compile(r'vidImgContent'))
        if vid_content:
            p_tag = vid_content.find('p')
            if p_tag:
                return html.unescape(p_tag.get_text(strip=True))
    except Exception as e:
        log.debug(f"Error extracting details: {str(e)}")
    return None


def extract_studio_name(html_content: str) -> Optional[str]:
    """Extract studio name from breadcrumb link."""
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        for link in soup.find_all('a', class_='link_bright'):
            href = str(link.get('href', ''))
            # Studio links have relative hrefs
            if href.startswith('/'):
                return html.unescape(link.get_text(strip=True))
    except Exception as e:
        log.debug(f"Error extracting studio name: {str(e)}")
    return None


def extract_performers(html_content: str) -> list:
    """Extract all performer names from infolink class."""
    performers = []
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        for link in soup.find_all('a', class_=re.compile(r'link_bright.*infolink')):
            name = link.get_text(strip=True)
            if name:
                performers.append({"name": html.unescape(name)})
    except Exception as e:
        log.debug(f"Error extracting performers: {str(e)}")
    return performers


def extract_image(html_content: str) -> Optional[str]:
    """Extract image URL from og:image meta tag, preview thumb, scene search results, or JavaScript."""
    try:
        soup = BeautifulSoup(html_content, 'lxml')

        # 1: try og:image meta tag
        og_image = soup.find('meta', property='og:image')
        if og_image:
            url = str(og_image.get('content', '')).strip()
            # Skip empty URLs or URLs that are just the base path
            if url and not url.endswith('contentthumbs/'):
                # Upgrade to 4x quality: convert any version (1x, 2x, 3x) to 4x
                url = re.sub(r'/meanbitches/content/contentthumbs/(.*)-[1234]x\.jpg$', r'/content//contentthumbs/\1-4x.jpg', url)
                if url:
                    return url

        # 2: Extract preview image from dvd_preview_thumb class
        preview_img = soup.find('img', class_=re.compile(r'dvd_preview_thumb'))
        if preview_img:
            thumb_url = str(preview_img.get('src', '')).strip()
            if thumb_url:
                return normalize_url(thumb_url) or thumb_url

        # 3: search for scene by title to get image from search results
        title = extract_title(html_content)
        if title:
            search_results = search_scenes_by_name(title)
            if search_results and search_results[0].get("image"):
                return search_results[0]["image"]

        # 4: try to extract movie thumbnail from JavaScript
        thumb_match = re.search(r'thumbnail:\s*"([^"]*\.jpg)"', html_content)
        if thumb_match:
            thumb_url = thumb_match.group(1).strip()
            if thumb_url:
                return normalize_url(thumb_url) or thumb_url

    except Exception as e:
        log.debug(f"Error extracting image: {str(e)}")

    return None


def extract_date(html_content: str) -> Optional[str]:
    """Extract date from page"""
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        for li in soup.find_all('li', class_=re.compile(r'text_med')):
            text = li.get_text(strip=True)
            date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', text)
            if date_match:
                date_str = date_match.group(1).strip()
                try:
                    parsed_date = datetime.strptime(date_str, "%m/%d/%Y")
                    return parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    return date_str
    except Exception as e:
        log.debug(f"Error extracting date: {str(e)}")
    return None


def extract_tags(html_content: str) -> list:
    """Extract all tag names from blogTags."""
    tags = []
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        blogtags_div = soup.find('div', class_=re.compile(r'blogTags'))
        if blogtags_div:
            for link in blogtags_div.find_all('a', class_=re.compile(r'border_btn')):
                tag_name = link.get_text(strip=True)
                if tag_name:
                    tags.append({"name": html.unescape(tag_name)})
    except Exception as e:
        log.debug(f"Error extracting tags: {str(e)}")
    return tags


def extract_studio_code(html_content: str) -> Optional[str]:
    """Extract studio code from upload path in HTML."""
    try:
        match = re.search(r'/content//upload/([^/]+)/', html_content)
        if match:
            return match.group(1)
    except Exception as e:
        log.debug(f"Error extracting studio code: {str(e)}")
    return None


def extract_search_result_data(container, scene_url: str, title: str) -> dict:
    """Extract scene data from search results HTML without scraping individual pages.

    Extracts: title, url, image, performer, studio, date
    Skips: description, tags, code (available on full page but not needed for search)
    """
    result: dict[str, Any] = {
        "title": html.unescape(title.strip()),
        "url": scene_url
    }

    try:
        soup = container

        img_tag = soup.find('img', class_='update_thumb')
        video_tag = soup.find('video', class_='update_thumb')

        if img_tag:
            # IMG tag: try src0_2x, src0_1x, then src
            img_url = img_tag.get('src0_2x') or img_tag.get('src0_1x') or img_tag.get('src')
            if img_url:
                img_url = img_url.strip()
                img_url = normalize_url(img_url) or img_url
                result["image"] = img_url
        elif video_tag:
            # VIDEO tag: try poster_2x, poster_1x, then poster (poster attribute uses poster_Nx naming)
            img_url = video_tag.get('poster_2x') or video_tag.get('poster_1x') or video_tag.get('poster')
            if img_url:
                img_url = img_url.strip()
                img_url = normalize_url(img_url) or img_url
                result["image"] = img_url

        # Extract performer
        perf_link = soup.find('a', href=re.compile(r'https://megasite\.meanworld\.com/models/'))
        if perf_link:
            perf_name = perf_link.get_text(strip=True)
            result["performers"] = [{"name": perf_name}]

        # Extract studio
        studio_link = soup.find('a', href=re.compile(r'^/[^/]+/$'))
        if studio_link:
            studio_name = studio_link.get_text(strip=True)
            result["studio"] = {"name": studio_name}

        # Extract date
        for li in soup.find_all('li', class_='text_med'):
            date_text = li.get_text(strip=True)
            if re.match(r'\d{1,2}/\d{1,2}/\d{4}', date_text):
                try:
                    parsed_date = datetime.strptime(date_text, "%m/%d/%Y")
                    result["date"] = parsed_date.strftime("%Y-%m-%d")
                    break
                except (ValueError, AttributeError):
                    # Invalid date format, continue to next date candidate
                    pass

    except Exception as e:
        log.debug(f"Error parsing search result: {str(e)}")

    return result


def _fetch_and_parse_search_page(query: str, page: int, search_name: str) -> tuple:
    """Fetch and parse a single search results page.

    Args:
        query: Search query (requests will handle URL encoding)
        page: Page number to fetch
        search_name: Original search name (for exact match checking)

    Returns:
        Tuple of (results_list, has_exact_match)
    """
    page_results = []
    has_exact_match = False

    try:
        # Build search URL with params
        search_url = "https://megasite.meanworld.com/search.php"
        params: dict[str, Any] = {"query": query}
        if page > 1:
            params["page"] = page

        # Fetch page
        try:
            html_content = fetch_html(search_url, params=params)
        except Exception as e:
            log.error(f"Error fetching search page {page}: {str(e)}")
            return page_results, has_exact_match

        # Parse results
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            all_containers = soup.find_all('div', class_=re.compile(r'latestUpdateB'))

            if not all_containers:
                return page_results, has_exact_match

            for container in all_containers:
                try:
                    # Skip latestUpdateBinfo containers
                    classes = container.get('class') or []
                    if isinstance(classes, list) and 'latestUpdateBinfo' in classes:
                        continue

                    # Find the scene link
                    scene_link = None
                    for link in container.find_all('a', href=re.compile(r'https://megasite\.meanworld\.com/scenes/.*_vids\.html')):
                        title = link.get_text(strip=True)
                        if title:
                            scene_link = link
                            break

                    if not scene_link:
                        continue

                    scene_url = str(scene_link.get('href', ''))
                    title = scene_link.get_text(strip=True)

                    if not scene_url or not title:
                        continue

                    # Check for exact match
                    if html.unescape(title).lower() == search_name.lower():
                        has_exact_match = True

                    # Extract data
                    result = extract_search_result_data(container, scene_url, title)
                    page_results.append(result)

                except Exception as e:
                    log.error(f"Error processing scene container on page {page}: {str(e)}")
                    continue

        except Exception as e:
            log.error(f"Error parsing search page {page}: {str(e)}")

    except Exception as e:
        log.error(f"Error in _fetch_and_parse_search_page: {str(e)}")

    return page_results, has_exact_match


def _search(query: str, name: str, max_pages: int) -> list:
    """Fetch search results."""
    results = []
    exact_match_found = False

    for page in range(1, max_pages + 1):
        if exact_match_found:
            break

        page_results, has_exact_match = _fetch_and_parse_search_page(query, page, name)
        results.extend(page_results)

        if has_exact_match:
            exact_match_found = True
            log.debug(f"Exact match found on page {page}, stopping search")
            break

        # Stop if no results on this page
        if not page_results:
            break

    return results


def search_scenes_by_name(name: str) -> list:
    """Search for scenes by name - returns array of scene fragments, sorted by relevance."""
    results = []

    if not name or not isinstance(name, str):
        log.error(f"Invalid search name: {name}")
        return results

    try:
        name = name.strip()
        if not name:
            return results

        max_pages = 5
        results = _search(name, name, max_pages)

        results.sort(key=_relevance_score, reverse=True)

        # Log sample of first result
        if results:
            first = results[0]
            first_fields = ", ".join(first.keys())
            log.debug(f"Search returning {len(results)} results. First result fields: {first_fields}")

    except Exception as e:
        log.error(f"Error searching scenes by name: {str(e)}")

    return results


# Sort results by relevance
def _relevance_score(scene):
    title = scene.get("title", "").lower()
    query = name.lower()

    return SequenceMatcher(None, query, title).ratio() * 1000


def _resolve_scene_fragment(scene_fragment: dict, prefer_exact_match: bool = False):
    """Resolve a scene fragment by attempting to scrape URL or search by title.

    Common logic for query_scene_fragment and enrich_scene_fragment.

    Args:
        scene_fragment: Scene fragment dict with optional 'url', 'title', 'file_name', 'urls'
        prefer_exact_match: If True, search results prefer exact title match

    Returns:
        Enriched scene dict or original fragment if resolution fails
    """
    # Attempt to scrape URL(s) if present
    # Try URLs in order: urls array first (if available), then main url field
    urls_to_try = []

    # Add urls from array if available
    if "urls" in scene_fragment and isinstance(scene_fragment.get("urls"), list):
        urls_to_try.extend(scene_fragment.get("urls", []))

    # Add main url if not already in array
    if "url" in scene_fragment:
        main_url = scene_fragment.get("url")
        if main_url and main_url not in urls_to_try:
            urls_to_try.append(main_url)

    # Try each URL in order
    for url in urls_to_try:
        if url and isinstance(url, str) and url.startswith("http"):
            # Check domain requirement if specified
            if "megasite.meanworld.com" not in url:
                # Skip non-megasite URLs and continue to next URL
                continue

            try:
                result = scrapeSceneURL(url)
                # Only return result if it has meaningful data (at least a title)
                # Gallery pages might scrape "successfully" but only get studio/director
                if result.get("title"):
                    return result
                else:
                    log.debug(f"URL {url} returned incomplete data (no title), trying next URL")
            except Exception as e:
                # If URL fails, try next URL or fall through to search by title
                log.debug(f"Failed to scrape URL {url}, trying next URL: {str(e)}")

    # Extract title from fragment or filename
    title = scene_fragment.get("title")
    if not title and "file_name" in scene_fragment:
        title = extract_title_from_filename(scene_fragment.get("file_name", ""))

    # Search by title if available
    if title:
        log.debug(f"All URLs failed, falling back to search by title: '{title}'")
        search_results = search_scenes_by_name(title)
        if search_results:
            if prefer_exact_match:
                # Find the best match: prefer exact title match, otherwise use first result
                best_match = search_results[0]
                for result in search_results:
                    if result["title"].lower() == title.lower():
                        best_match = result
                        break
                log.debug(f"Found {len(search_results)} search results, using best match: {best_match.get('url')}")
                return scrapeSceneURL(best_match["url"])
            else:
                # Return the first (best) match
                log.debug(f"Found {len(search_results)} search results, using first: {search_results[0].get('url')}")
                return scrapeSceneURL(search_results[0]["url"])
        else:
            log.debug(f"No search results found for title: '{title}'")
    else:
        log.debug("No title available for fallback search")

    # If we can't find it, return the fragment as-is
    log.debug(f"Returning original fragment with {len(scene_fragment)} fields")
    return scene_fragment


def query_scene_fragment(scene_fragment: dict) -> dict:
    """Query for scenes matching a fragment - returns single enriched scene.

    This is used by sceneByQueryFragment to find a scene matching a fragment.
    """
    return _resolve_scene_fragment(scene_fragment, prefer_exact_match=False)


def enrich_scene_fragment(scene_fragment: dict) -> dict:
    """Enrich a scene fragment (from URL or partial data) by scraping full details.

    This is used by sceneByFragment to enrich scenes from library.
    Only scrapes megasite.meanworld.com URLs (skips meanbitches.com which return 404).
    Prefers exact title matches when searching.
    """
    return _resolve_scene_fragment(scene_fragment, prefer_exact_match=True)


@cache_to_disk(ttl=3600)  # Cache for 1 hour
def scrapeSceneURL(url: str) -> dict:
    """Scrape scene data from MeanBitches page by URL.

    Raises an exception on 404 or network errors so that calling code
    (e.g. _resolve_scene_fragment) can fall back to searching by title.
    """
    ret: dict[str, Any] = {'url': url}

    html_content = fetch_html(url)

    if title := extract_title(html_content):
        ret['title'] = title

    if details := extract_details(html_content):
        ret['details'] = details

    studio = {}
    if studio_name := extract_studio_name(html_content):
        studio['name'] = studio_name
    studio['url'] = "https://www.meanbitches.com/"
    if studio:
        ret['studio'] = studio

    if performers := extract_performers(html_content):
        ret['performers'] = performers

    if image := extract_image(html_content):
        ret['image'] = image

    if date := extract_date(html_content):
        ret['date'] = date

    if tags := extract_tags(html_content):
        ret['tags'] = tags

    if code := extract_studio_code(html_content):
        ret['code'] = code

    ret['director'] = "Glenn King"

    return ret


def scrapeGalleryURL(url: str) -> dict:
    """Scrape gallery data from MeanBitches page by URL."""
    # For galleries, use the same extraction as scenes but with photographer instead of director
    ret = scrapeSceneURL(url)

    # Replace director with photographer
    if 'director' in ret:
        del ret['director']
    ret['photographer'] = "Glenn King"

    return ret


# Read the input
input_data = readJSONInput()
operation = sys.argv[1] if len(sys.argv) > 1 else "unknown"
log.debug(f"=== OPERATION START: {operation} ===")

if operation == "scrapeSceneURL":
    url = str(input_data.get('url'))
    ret = scrapeSceneURL(url)
    print(json.dumps(ret))
elif operation == "scrapeGalleryURL":
    url = str(input_data.get('url'))
    ret = scrapeGalleryURL(url)
    print(json.dumps(ret))
elif operation == "searchScenes":
    name = str(input_data.get('name'))
    ret = search_scenes_by_name(name)
    print(json.dumps(ret))
elif operation == "queryScene":
    ret = query_scene_fragment(input_data)
    print(json.dumps(ret))
elif operation == "enrichScene":
    ret = enrich_scene_fragment(input_data)
    print(json.dumps(ret))
else:
    log.error(f"Unknown operation: {operation}")
    sys.exit(69)
