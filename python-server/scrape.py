import requests
from bs4 import BeautifulSoup
import json

def extract_medium_metadata_from_url(url: str):
    """
    Scrapes a Medium article URL and extracts metadata like title, author, etc.
    """
    # ======== FETCH HTML CONTENT ========
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()  # Fail fast if URL invalid or blocked

    soup = BeautifulSoup(response.text, "html.parser")

    # ======== META HELPER ========
    def meta(name=None, prop=None):
        tag = soup.find("meta", attrs={"name": name}) if name else soup.find("meta", property=prop)
        return tag["content"].strip() if tag and tag.has_attr("content") else None

    # ======== CORE METADATA ========
    title = meta("title") or meta(prop="og:title")
    description = meta("description") or meta(prop="og:description")
    author = meta("author") or meta(prop="article:author")
    published_date = meta(prop="article:published_time")
    image_url = meta(prop="og:image")
    canonical_url = soup.find("link", rel="canonical")
    canonical_url = canonical_url["href"] if canonical_url else meta(prop="og:url")
    twitter_handle = meta("twitter:creator")
    reading_time = meta("twitter:data1")
    site_name = meta(prop="og:site_name")
    twitter_card = meta("twitter:card")

    # ======== STRUCTURED JSON-LD ========
    json_ld_data = None
    for script_tag in soup.find_all("script", type="application/ld+json"):
        try:
            json_ld_data = json.loads(script_tag.string)
            if isinstance(json_ld_data, dict) and "headline" in json_ld_data:
                break
        except json.JSONDecodeError:
            continue

    # ======== EXTRA DETAILS ========
    author_profile = None
    link_author = soup.find("link", rel="author")
    if link_author:
        author_profile = link_author["href"]

    favicon = soup.find("link", rel="icon")
    favicon = favicon["href"] if favicon else None

    tags = None
    if json_ld_data and isinstance(json_ld_data, dict):
        tags = json_ld_data.get("keywords")

    # ======== AGGREGATE ========
    metadata = {
        "title": title,
        "subtitle": json_ld_data.get("headline") if json_ld_data else None,
        "description": description,
        "author_name": author,
        "author_profile": author_profile,
        "twitter_handle": twitter_handle,
        "published_date": published_date,
        "reading_time": reading_time,
        "cover_image": image_url,
        "canonical_url": canonical_url,
        "favicon": favicon,
        "platform": site_name or "Medium",
        "twitter_card": twitter_card,
        "tags": tags,
    }

    return metadata

