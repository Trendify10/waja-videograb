import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from yt_dlp import YoutubeDL

from backend.config import get_download_folder, load_config
from backend.instagram import is_instagram_url, instagram_extract_info, instagram_download

HISTORY_PATH = Path(__file__).resolve().parent.parent / "history.json"

# In-memory job tracking
jobs: dict[str, dict] = {}

# Robust format strings with full fallback chains.
# The key insight: Instagram/Facebook/TikTok often serve a single combined
# mp4 — they don't have separate video-only and audio-only streams.
# The fallback chain must end with formats that catch these combined streams.
# Prefer H.264 + AAC so files play natively in QuickTime on macOS.
# VP9/AV1 downloads are technically valid but QuickTime can't play them.
_FORMAT_SORT = ["vcodec:h264", "acodec:aac"]

FORMAT_OPTIONS = {
    "best": {
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "format_sort": _FORMAT_SORT,
    },
    "1080p": {
        "format": "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
        "merge_output_format": "mp4",
        "format_sort": _FORMAT_SORT,
    },
    "720p": {
        "format": "bv*[height<=720]+ba/b[height<=720]/bv*+ba/b",
        "merge_output_format": "mp4",
        "format_sort": _FORMAT_SORT,
    },
    "mp3": {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    },
}

# Platforms that require login cookies for video (not just audio)
_COOKIE_PLATFORMS = {"instagram.com", "instagr.am", "facebook.com", "fb.watch"}


def _url_needs_cookies(url: str) -> bool:
    url_lower = url.lower()
    return any(p in url_lower for p in _COOKIE_PLATFORMS)


def _add_cookies(ydl_opts: dict, url: str, cookies_browser: str | None):
    """Add cookie config. Auto-uses Chrome for Facebook/Instagram URLs."""
    if cookies_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_browser,)
    elif _url_needs_cookies(url):
        ydl_opts["cookiesfrombrowser"] = ("chrome",)


def extract_info(url: str, cookies_browser: str | None = None) -> dict:
    """Fetch video metadata without downloading."""

    # Instagram fallback — yt-dlp's extractor is broken upstream
    if is_instagram_url(url):
        result = instagram_extract_info(url)
        if result:
            return result

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    _add_cookies(ydl_opts, url, cookies_browser)

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # Detect platform from extractor name
    extractor = (info.get("extractor") or info.get("extractor_key") or "").lower()
    if "youtube" in extractor:
        platform = "YouTube"
    elif "tiktok" in extractor:
        platform = "TikTok"
    elif "instagram" in extractor:
        platform = "Instagram"
    elif "facebook" in extractor:
        platform = "Facebook"
    else:
        platform = info.get("extractor_key", "Unknown")

    return {
        "title": info.get("title", "Unknown"),
        "thumbnail": info.get("thumbnail"),
        "author": info.get("uploader") or info.get("channel") or "Unknown",
        "duration": info.get("duration"),
        "platform": platform,
        "url": url,
    }


def start_download(url: str, fmt: str, cookies_browser: str | None = None) -> str:
    """Start a background download job. Returns job_id."""
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "state": "queued",
        "percent": 0,
        "speed": None,
        "eta": None,
        "file_path": None,
        "error": None,
        "title": None,
    }

    thread = threading.Thread(
        target=_run_download,
        args=(job_id, url, fmt, cookies_browser),
        daemon=True,
    )
    thread.start()
    return job_id


def _run_download(job_id: str, url: str, fmt: str, cookies_browser: str | None):
    """Execute the download in a background thread."""
    job = jobs[job_id]
    job["state"] = "downloading"

    download_folder = get_download_folder()

    # Instagram fallback — bypass yt-dlp entirely
    if is_instagram_url(url) and fmt != "mp3":
        try:
            def ig_progress(downloaded, total):
                job["percent"] = round(downloaded / total * 100, 1)
                speed = None  # Instagram doesn't give us speed info
                job["speed"] = speed
                job["eta"] = None

            result = instagram_download(url, download_folder, progress_cb=ig_progress)
            job["state"] = "done"
            job["title"] = result["title"]
            job["file_path"] = result["file_path"]
            job["percent"] = 100

            _add_to_history({
                "title": result["title"],
                "platform": "Instagram",
                "format": fmt,
                "timestamp": datetime.now().isoformat(),
                "file_path": result["file_path"],
            })
            return
        except Exception as e:
            # Fall through to yt-dlp as last resort
            job["error"] = None
            job["state"] = "downloading"

    fmt_opts = FORMAT_OPTIONS.get(fmt, FORMAT_OPTIONS["best"])

    def progress_hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                job["percent"] = round(downloaded / total * 100, 1)
            speed = d.get("speed")
            job["speed"] = f"{speed / 1024 / 1024:.1f} MB/s" if speed else None
            eta = d.get("eta")
            job["eta"] = f"{eta}s" if eta else None
        elif d["status"] == "finished":
            job["percent"] = 100
            job["speed"] = None
            job["eta"] = None

    ydl_opts = {
        "outtmpl": os.path.join(download_folder, "%(title)s [%(id)s].%(ext)s"),
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        **{k: v for k, v in fmt_opts.items() if k != "postprocessors"},
    }

    if "postprocessors" in fmt_opts:
        ydl_opts["postprocessors"] = fmt_opts["postprocessors"]

    _add_cookies(ydl_opts, url, cookies_browser)

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Unknown")
            job["title"] = title

            # Determine final file path
            if fmt == "mp3":
                filename = ydl.prepare_filename(info)
                file_path = os.path.splitext(filename)[0] + ".mp3"
            else:
                file_path = ydl.prepare_filename(info)
                # merge_output_format changes extension
                if "merge_output_format" in fmt_opts:
                    file_path = os.path.splitext(file_path)[0] + ".mp4"

            job["state"] = "done"
            job["file_path"] = file_path
            job["percent"] = 100

            # Save to history
            _add_to_history({
                "title": title,
                "platform": _detect_platform(info),
                "format": fmt,
                "timestamp": datetime.now().isoformat(),
                "file_path": file_path,
            })

    except Exception as e:
        job["state"] = "error"
        job["error"] = str(e)


def _detect_platform(info: dict) -> str:
    extractor = (info.get("extractor") or info.get("extractor_key") or "").lower()
    if "youtube" in extractor:
        return "YouTube"
    elif "tiktok" in extractor:
        return "TikTok"
    elif "instagram" in extractor:
        return "Instagram"
    elif "facebook" in extractor:
        return "Facebook"
    return info.get("extractor_key", "Unknown")


def get_job(job_id: str) -> dict | None:
    return jobs.get(job_id)


def get_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    with open(HISTORY_PATH) as f:
        return json.load(f)


def _add_to_history(entry: dict):
    history = get_history()
    history.insert(0, entry)
    # Keep last 200 entries
    history = history[:200]
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)
