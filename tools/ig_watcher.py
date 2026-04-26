"""
ig_watcher.py — Watch @hellomrshockett Instagram for new Reels and run the blog pipeline.

Flow:
1. Fetch recent posts from Instagram via oembed/public endpoints
2. Compare against already-processed posts (tracked in processed.json)
3. For new Reels, run the pipeline: download video, generate Amazon link, build blog post
4. Return a summary for Telegram approval

Usage:
    python ig_watcher.py                  # Check for new posts
    python ig_watcher.py --list           # Show processed history
    python ig_watcher.py --reset          # Clear processed history
"""

import json
import os
import re
import sys
import hashlib
from pathlib import Path
from typing import Optional
from urllib.parse import quote

try:
    import requests
except ImportError:
    requests = None

from amazon_linker import search_product, extract_keywords
from blog_post_builder import build_blog_post

TOOLS_DIR = Path(__file__).resolve().parent
PROCESSED_FILE = TOOLS_DIR / "processed.json"
ASSETS_DIR = TOOLS_DIR.parent / "assets" / "videos"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

INSTAGRAM_USERNAME = "hellomrshockett"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def load_processed() -> dict:
    """Load the set of already-processed post IDs/URLs."""
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE) as f:
            return json.load(f)
    return {"posts": {}}


def save_processed(data: dict):
    """Save processed post tracking data."""
    with open(PROCESSED_FILE, "w") as f:
        json.dump(data, f, indent=2)


def mark_processed(url: str, status: str = "pending", blog_post: str = "", amazon_link: str = ""):
    """Mark a post URL as processed."""
    data = load_processed()
    post_id = hashlib.md5(url.encode()).hexdigest()[:12]
    data["posts"][post_id] = {
        "url": url,
        "status": status,
        "blog_post": blog_post,
        "amazon_link": amazon_link,
    }
    save_processed(data)


def is_processed(url: str) -> bool:
    """Check if a post URL has already been processed."""
    data = load_processed()
    post_id = hashlib.md5(url.encode()).hexdigest()[:12]
    return post_id in data["posts"]


def fetch_recent_reels(username: str = INSTAGRAM_USERNAME, count: int = 12) -> list:
    """
    Fetch recent Reels/posts from an Instagram profile.

    Uses multiple strategies:
    1. Instagram Graph API (if access token available)
    2. Public profile page scraping for post URLs
    3. Third-party embed APIs

    Returns:
        List of dicts with: url, caption, thumbnail_url
    """
    posts = []

    # Strategy 1: Instagram Graph API (best, requires token)
    ig_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    ig_user_id = os.environ.get("INSTAGRAM_USER_ID")

    if ig_token and ig_user_id:
        posts = _fetch_via_graph_api(ig_user_id, ig_token, count)
        if posts:
            return posts

    # Strategy 2: Public page scraping
    posts = _fetch_via_page_scrape(username, count)
    if posts:
        return posts

    # Strategy 3: Try rapid API or similar
    posts = _fetch_via_embed_api(username, count)

    return posts


def _fetch_via_graph_api(user_id: str, token: str, count: int) -> list:
    """Fetch recent media via Instagram Graph API."""
    posts = []
    try:
        url = f"https://graph.instagram.com/{user_id}/media"
        params = {
            "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp",
            "limit": count,
            "access_token": token,
        }
        resp = requests.get(url, params=params, timeout=15)
        if resp.ok:
            data = resp.json()
            for item in data.get("data", []):
                if item.get("media_type") in ("VIDEO", "REELS"):
                    posts.append({
                        "url": item.get("permalink", ""),
                        "caption": item.get("caption", ""),
                        "thumbnail_url": item.get("thumbnail_url", ""),
                        "media_url": item.get("media_url", ""),
                        "timestamp": item.get("timestamp", ""),
                        "ig_id": item.get("id", ""),
                    })
    except Exception as e:
        print(f"[ig_watcher] Graph API error: {e}")
    return posts


def _fetch_via_page_scrape(username: str, count: int) -> list:
    """Try to scrape post URLs from the public Instagram profile page."""
    posts = []
    try:
        profile_url = f"https://www.instagram.com/{username}/"
        resp = requests.get(profile_url, headers=BROWSER_HEADERS, timeout=15)
        if resp.ok:
            # Look for shortcode links in the page HTML
            shortcodes = re.findall(r'/reel/([A-Za-z0-9_-]+)/', resp.text)
            if not shortcodes:
                shortcodes = re.findall(r'/p/([A-Za-z0-9_-]+)/', resp.text)

            seen = set()
            for sc in shortcodes[:count]:
                if sc not in seen:
                    seen.add(sc)
                    post_url = f"https://www.instagram.com/reel/{sc}/"
                    # Get caption via oembed
                    caption = ""
                    thumb = ""
                    try:
                        oembed = requests.get(
                            f"https://api.instagram.com/oembed/?url={quote(post_url, safe='')}",
                            headers=BROWSER_HEADERS,
                            timeout=8,
                        )
                        if oembed.ok:
                            odata = oembed.json()
                            caption = odata.get("title", "")
                            thumb = odata.get("thumbnail_url", "")
                    except Exception:
                        pass

                    posts.append({
                        "url": post_url,
                        "caption": caption,
                        "thumbnail_url": thumb,
                    })
    except Exception as e:
        print(f"[ig_watcher] Page scrape error: {e}")
    return posts


def _fetch_via_embed_api(username: str, count: int) -> list:
    """Fallback: try embed-based approach for recent posts."""
    # This is a placeholder for future API integrations
    # (RapidAPI Instagram scrapers, Apify, etc.)
    print(f"[ig_watcher] No posts found via scraping. Consider setting INSTAGRAM_ACCESS_TOKEN.")
    return []


def process_new_reels(dry_run: bool = False) -> list:
    """
    Check for new Reels and process them through the blog pipeline.

    Args:
        dry_run: If True, don't actually build blog posts

    Returns:
        List of result dicts for new posts (ready for Telegram approval)
    """
    print(f"Checking @{INSTAGRAM_USERNAME} for new Reels...")
    reels = fetch_recent_reels()

    if not reels:
        print("No Reels found. You may need to set INSTAGRAM_ACCESS_TOKEN for reliable access.")
        return []

    print(f"Found {len(reels)} recent Reels.")

    new_results = []
    for reel in reels:
        url = reel["url"]
        if is_processed(url):
            continue

        caption = reel.get("caption", "")
        keywords = extract_keywords(caption)

        print(f"\nNew Reel: {url}")
        print(f"  Caption: {caption[:80]}..." if len(caption) > 80 else f"  Caption: {caption}")
        print(f"  Keywords: {keywords}")

        if dry_run:
            print("  [dry run — skipping pipeline]")
            mark_processed(url, status="dry-run")
            new_results.append({
                "url": url,
                "caption": caption,
                "keywords": keywords,
                "status": "dry-run",
            })
            continue

        # Run the Amazon linker
        amazon_result = search_product(caption)
        print(f"  Amazon: {amazon_result['affiliate_link'][:60]}...")

        # Build blog post
        post_result = build_blog_post(
            video_path=None,  # Will embed from IG or download later
            product_title=keywords.title() if keywords else "featured find",
            product_description=caption,
            amazon_link=amazon_result["affiliate_link"],
            tiktok_shop_link="",
            mavely_link="",
            thumbnail_url=reel.get("thumbnail_url", ""),
            caption=caption,
            category="deal",
            source_platform="instagram",
            source_url=url,
        )
        print(f"  Blog post: {post_result['file_path']}")

        mark_processed(
            url,
            status="pending-approval",
            blog_post=post_result["file_path"],
            amazon_link=amazon_result["affiliate_link"],
        )

        new_results.append({
            "url": url,
            "caption": caption,
            "keywords": keywords,
            "amazon_link": amazon_result["affiliate_link"],
            "amazon_title": amazon_result.get("title", ""),
            "blog_post": post_result["file_path"],
            "blog_url": post_result["url"],
            "status": "pending-approval",
        })

    if not new_results:
        print("\nNo new Reels to process.")
    else:
        print(f"\n{len(new_results)} new blog posts ready for approval.")

    return new_results


def format_telegram_summary(results: list) -> str:
    """Format pipeline results into a Telegram-friendly message for Brooke."""
    if not results:
        return "no new reels found on @hellomrshockett"

    lines = [f"{len(results)} new video(s) ready for the blog:\n"]

    for i, r in enumerate(results, 1):
        title = r.get("keywords", "").title() or "untitled"
        amazon = r.get("amazon_link", "")
        caption_preview = r.get("caption", "")[:60]

        lines.append(f"{i}. {title}")
        if caption_preview:
            lines.append(f"   \"{caption_preview}...\"")
        if amazon:
            lines.append(f"   amazon: {amazon[:60]}...")
        lines.append("")

    lines.append("reply with which ones to publish (e.g. 'all' or '1, 3') or 'skip' to skip")
    return "\n".join(lines)


if __name__ == "__main__":
    if "--list" in sys.argv:
        data = load_processed()
        if not data["posts"]:
            print("No processed posts yet.")
        else:
            for pid, info in data["posts"].items():
                print(f"  {pid}: {info['status']} — {info['url']}")
        sys.exit(0)

    if "--reset" in sys.argv:
        save_processed({"posts": {}})
        print("Processed history cleared.")
        sys.exit(0)

    dry_run = "--dry-run" in sys.argv
    results = process_new_reels(dry_run=dry_run)

    if results:
        print("\n" + "=" * 60)
        print("TELEGRAM MESSAGE:")
        print("=" * 60)
        print(format_telegram_summary(results))
