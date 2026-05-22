"""Instagram fallback downloader.

yt-dlp's Instagram extractor is currently broken upstream.
This module uses Instagram's private v1 API directly with
Chrome cookies (extracted via yt-dlp's cookie decryptor).
"""

import os
import re
import requests
from yt_dlp.cookies import extract_cookies_from_browser


def _get_session() -> requests.Session:
    """Create a requests session with Chrome Instagram cookies."""
    jar = extract_cookies_from_browser("chrome")
    session = requests.Session()
    for cookie in jar:
        if "instagram" in cookie.domain:
            session.cookies.set(cookie.name, cookie.value, domain=cookie.domain)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "X-IG-App-ID": "936619743392459",
    })
    return session


def _shortcode_from_url(url: str) -> str | None:
    """Extract shortcode from an Instagram URL."""
    m = re.search(r"instagram\.com/(?:[^/]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None


def _shortcode_to_media_id(shortcode: str) -> int:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    media_id = 0
    for char in shortcode:
        media_id = media_id * 64 + alphabet.index(char)
    return media_id


def _fetch_media_info(session: requests.Session, media_id: int) -> dict | None:
    """Fetch media info from Instagram's v1 API."""
    url = f"https://www.instagram.com/api/v1/media/{media_id}/info/"
    resp = session.get(url)
    if resp.status_code != 200:
        return None
    data = resp.json()
    items = data.get("items", [])
    return items[0] if items else None


def is_instagram_url(url: str) -> bool:
    return bool(re.search(r"instagram\.com|instagr\.am", url, re.IGNORECASE))


def instagram_extract_info(url: str) -> dict | None:
    """Extract Instagram video metadata. Returns None if it can't handle the URL."""
    shortcode = _shortcode_from_url(url)
    if not shortcode:
        return None

    session = _get_session()
    media_id = _shortcode_to_media_id(shortcode)
    item = _fetch_media_info(session, media_id)
    if not item:
        return None

    username = item.get("user", {}).get("username", "Unknown")
    caption = item.get("caption")
    caption_text = caption.get("text", "") if caption else ""
    title = caption_text.split("\n")[0][:80] if caption_text else f"Video by {username}"

    thumbnail = None
    candidates = item.get("image_versions2", {}).get("candidates", [])
    if candidates:
        thumbnail = candidates[0].get("url")

    duration = item.get("video_duration")

    return {
        "title": title,
        "thumbnail": thumbnail,
        "author": username,
        "duration": int(duration) if duration else None,
        "platform": "Instagram",
        "url": url,
    }


def instagram_download(url: str, download_folder: str, progress_cb=None) -> dict:
    """Download an Instagram video. Returns dict with title, file_path, etc.

    Raises Exception on failure.
    """
    shortcode = _shortcode_from_url(url)
    if not shortcode:
        raise ValueError("Could not extract Instagram shortcode from URL")

    session = _get_session()
    media_id = _shortcode_to_media_id(shortcode)
    item = _fetch_media_info(session, media_id)
    if not item:
        raise ValueError("Could not fetch Instagram media info. The post may be private or deleted.")

    video_versions = item.get("video_versions", [])
    if not video_versions:
        raise ValueError("No video found in this Instagram post (may be a photo).")

    # Pick the best quality (first is usually highest)
    video_url = video_versions[0]["url"]

    username = item.get("user", {}).get("username", "Unknown")
    caption = item.get("caption")
    caption_text = caption.get("text", "") if caption else ""
    title = caption_text.split("\n")[0][:80] if caption_text else f"Video by {username}"

    # Sanitize filename
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title).strip() or "Instagram Video"
    filename = f"{safe_title} [{shortcode}].mp4"
    file_path = os.path.join(download_folder, filename)

    # Download with progress
    resp = session.get(video_url, stream=True)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0

    with open(file_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            f.write(chunk)
            downloaded += len(chunk)
            if progress_cb and total > 0:
                progress_cb(downloaded, total)

    return {
        "title": title,
        "author": username,
        "file_path": file_path,
    }
