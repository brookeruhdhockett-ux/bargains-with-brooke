"""
video_downloader.py — Download videos from Instagram Reels and TikTok (watermark-free).

Saves videos to blog/assets/videos/ and returns local path + metadata.
"""

import os
import re
import json
import hashlib
import requests
from typing import Optional
from pathlib import Path
from urllib.parse import urlparse, quote

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "videos"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Common headers to avoid bot detection
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _slug_from_url(url: str) -> str:
    """Generate a short filename slug from a URL."""
    h = hashlib.md5(url.encode()).hexdigest()[:10]
    return h


def download_instagram_reel(url: str) -> dict:
    """
    Download an Instagram Reel video.

    Strategy:
    1. Try the Instagram oembed API to get metadata (caption, thumbnail).
    2. Fetch the page HTML and extract the video URL from og:video or
       embedded JSON data.
    3. Fall back to a third-party service (saveig-style) if direct scraping
       fails.

    Returns:
        dict with keys: video_path, caption, thumbnail_url, source_url, platform
    """
    url = _normalize_instagram_url(url)
    slug = _slug_from_url(url)
    video_path = ASSETS_DIR / f"ig_{slug}.mp4"

    caption = ""
    thumbnail_url = ""

    # Step 1: Get metadata via oembed
    try:
        oembed_url = f"https://api.instagram.com/oembed/?url={quote(url, safe='')}"
        resp = requests.get(oembed_url, headers=BROWSER_HEADERS, timeout=10)
        if resp.ok:
            data = resp.json()
            caption = data.get("title", "")
            thumbnail_url = data.get("thumbnail_url", "")
    except Exception:
        pass

    # Step 2: Try scraping the page for og:video
    video_url = None
    try:
        page = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
        # Look for og:video meta tag
        match = re.search(r'<meta\s+property="og:video"\s+content="([^"]+)"', page.text)
        if match:
            video_url = match.group(1)

        # Also try to find video URL in embedded JSON
        if not video_url:
            match = re.search(r'"video_url"\s*:\s*"([^"]+)"', page.text)
            if match:
                video_url = match.group(1).replace("\\u0026", "&")

        # Get caption from og:description if we don't have it
        if not caption:
            match = re.search(r'<meta\s+property="og:description"\s+content="([^"]*)"', page.text)
            if match:
                caption = match.group(1)

    except Exception:
        pass

    # Step 3: Try third-party download service as fallback
    if not video_url:
        try:
            video_url = _try_third_party_instagram(url)
        except Exception:
            pass

    # Download the video if we found a URL
    if video_url:
        _download_file(video_url, video_path)
    else:
        # Save a placeholder note so the pipeline doesn't crash
        video_path = None
        print(f"[video_downloader] Could not extract video URL from {url}")
        print("[video_downloader] You may need to download manually and place in blog/assets/videos/")

    return {
        "video_path": str(video_path) if video_path and video_path.exists() else None,
        "caption": caption,
        "thumbnail_url": thumbnail_url,
        "source_url": url,
        "platform": "instagram",
    }


def download_tiktok_video(url: str) -> dict:
    """
    Download a TikTok video watermark-free.

    Strategy:
    1. Try tikwm.com API (free, watermark-free).
    2. Try TikTok oembed for metadata.
    3. Fall back gracefully if neither works.

    Returns:
        dict with keys: video_path, caption, thumbnail_url, source_url, platform
    """
    url = _normalize_tiktok_url(url)
    slug = _slug_from_url(url)
    video_path = ASSETS_DIR / f"tt_{slug}.mp4"

    caption = ""
    thumbnail_url = ""
    video_url = None

    # Step 1: TikTok oembed for metadata
    try:
        oembed_url = f"https://www.tiktok.com/oembed?url={quote(url, safe='')}"
        resp = requests.get(oembed_url, headers=BROWSER_HEADERS, timeout=10)
        if resp.ok:
            data = resp.json()
            caption = data.get("title", "")
            thumbnail_url = data.get("thumbnail_url", "")
    except Exception:
        pass

    # Step 2: Try tikwm.com API for watermark-free download
    try:
        tikwm_resp = requests.post(
            "https://www.tikwm.com/api/",
            data={"url": url, "hd": 1},
            headers={"User-Agent": BROWSER_HEADERS["User-Agent"]},
            timeout=15,
        )
        if tikwm_resp.ok:
            tikwm_data = tikwm_resp.json()
            if tikwm_data.get("code") == 0:
                play_data = tikwm_data.get("data", {})
                # Prefer HD, fall back to regular
                video_url = play_data.get("hdplay") or play_data.get("play")
                if not caption:
                    caption = play_data.get("title", "")
                if not thumbnail_url:
                    thumbnail_url = play_data.get("cover", "")
    except Exception:
        pass

    # Step 3: Alternative — try tikcdn or similar
    if not video_url:
        try:
            alt_resp = requests.post(
                "https://tikcdn.io/ssstik/video",
                data={"id": url, "locale": "en", "tt": "a"},
                headers=BROWSER_HEADERS,
                timeout=15,
            )
            if alt_resp.ok and "video" in alt_resp.headers.get("content-type", ""):
                with open(video_path, "wb") as f:
                    f.write(alt_resp.content)
        except Exception:
            pass

    # Download video if we got a URL
    if video_url:
        _download_file(video_url, video_path)
    elif not video_path.exists():
        video_path = None
        print(f"[video_downloader] Could not extract video URL from {url}")
        print("[video_downloader] You may need to download manually and place in blog/assets/videos/")

    return {
        "video_path": str(video_path) if video_path and video_path.exists() else None,
        "caption": caption,
        "thumbnail_url": thumbnail_url,
        "source_url": url,
        "platform": "tiktok",
    }


def download_video(url: str) -> dict:
    """
    Auto-detect platform and download video.

    Args:
        url: Instagram or TikTok URL

    Returns:
        dict with video_path, caption, thumbnail_url, source_url, platform
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    if "instagram" in hostname or "instagr.am" in hostname:
        return download_instagram_reel(url)
    elif "tiktok" in hostname or "vm.tiktok.com" in hostname:
        return download_tiktok_video(url)
    else:
        raise ValueError(f"Unsupported platform URL: {url}")


# --- Internal helpers ---

def _normalize_instagram_url(url: str) -> str:
    """Strip tracking params from Instagram URLs."""
    parsed = urlparse(url)
    # Keep just the path
    clean = f"https://www.instagram.com{parsed.path}"
    if not clean.endswith("/"):
        clean += "/"
    return clean


def _normalize_tiktok_url(url: str) -> str:
    """Resolve TikTok short URLs and normalize."""
    parsed = urlparse(url)
    if "vm.tiktok.com" in (parsed.hostname or ""):
        # Resolve the redirect to get the full URL
        try:
            resp = requests.head(url, allow_redirects=True, timeout=10)
            url = resp.url
        except Exception:
            pass
    return url


def _try_third_party_instagram(url: str) -> Optional[str]:
    """Try a third-party Instagram download API."""
    try:
        resp = requests.get(
            "https://igdownloader.app/api/v1/media",
            params={"url": url},
            headers=BROWSER_HEADERS,
            timeout=15,
        )
        if resp.ok:
            data = resp.json()
            videos = [m for m in data.get("media", []) if m.get("type") == "video"]
            if videos:
                return videos[0].get("url")
    except Exception:
        pass
    return None


def _download_file(url: str, dest: Path) -> None:
    """Download a file from URL to local path."""
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, stream=True, timeout=30)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"[video_downloader] Saved: {dest}")
    except Exception as e:
        print(f"[video_downloader] Download failed: {e}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python video_downloader.py <instagram_or_tiktok_url>")
        sys.exit(1)
    result = download_video(sys.argv[1])
    print(json.dumps(result, indent=2))
