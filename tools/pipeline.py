"""
pipeline.py — TikTok/Instagram-to-Blog orchestrator.

Main flow:
1. Download video from Instagram Reel or TikTok (watermark-free)
2. Extract product info from the caption
3. Search Amazon and generate affiliate link (tag: brookehockett-20)
4. Build an HTML blog post for bargainswithbrooke.com
5. Return a summary dict for Telegram approval

Usage:
    python pipeline.py <url> [--mavely <mavely_link>] [--tiktok-shop <shop_link>] [--title <override_title>]
"""

import argparse
import json
import sys
from pathlib import Path

from video_downloader import download_video
from amazon_linker import search_product, extract_keywords
from blog_post_builder import build_blog_post


def process_video(
    url: str,
    mavely_link: str = "",
    tiktok_shop_link: str = "",
    title_override: str = "",
    category: str = "deal",
) -> dict:
    """
    Full pipeline: video URL -> blog post.

    Args:
        url: Instagram Reel or TikTok URL
        mavely_link: Optional Mavely affiliate link
        tiktok_shop_link: Optional TikTok Shop link
        title_override: Override auto-detected product title
        category: Blog post category tag (default: "deal")

    Returns:
        Summary dict with all pipeline results:
        - video: download result dict
        - amazon: search result dict
        - blog_post: generated post dict
        - summary: human-readable summary string
    """
    print(f"\n{'='*60}")
    print(f"TikTok-to-Blog Pipeline")
    print(f"{'='*60}")

    # --- Step 1: Download video ---
    print(f"\n[1/4] Downloading video from: {url}")
    video_result = download_video(url)
    print(f"  Platform: {video_result['platform']}")
    print(f"  Video: {video_result['video_path'] or 'not downloaded'}")
    print(f"  Caption: {video_result['caption'][:100]}..." if len(video_result.get('caption', '')) > 100 else f"  Caption: {video_result.get('caption', '(none)')}")

    # --- Step 2: Extract product info ---
    print(f"\n[2/4] Extracting product keywords...")
    caption = video_result.get("caption", "")
    keywords = extract_keywords(caption)
    print(f"  Keywords: {keywords or '(none extracted)'}")

    # Use title override if provided, otherwise use keywords
    product_title = title_override or keywords or "featured deal"
    print(f"  Product title: {product_title}")

    # --- Step 3: Search Amazon ---
    print(f"\n[3/4] Searching Amazon for: {product_title}")
    amazon_result = search_product(product_title)
    print(f"  Method: {amazon_result['method']}")
    print(f"  Link: {amazon_result['affiliate_link'][:80]}...")
    if amazon_result.get("price"):
        print(f"  Price: {amazon_result['price']}")

    # --- Step 4: Build blog post ---
    print(f"\n[4/4] Building blog post...")
    post_result = build_blog_post(
        video_path=video_result.get("video_path"),
        product_title=product_title,
        product_description=caption,
        amazon_link=amazon_result["affiliate_link"],
        tiktok_shop_link=tiktok_shop_link,
        mavely_link=mavely_link,
        thumbnail_url=video_result.get("thumbnail_url", ""),
        caption=caption,
        category=category,
        source_platform=video_result["platform"],
    )
    print(f"  Post: {post_result['file_path']}")
    print(f"  URL: {post_result['url']}")

    # --- Build summary ---
    summary_lines = [
        f"Blog post ready for review:",
        f"",
        f"Title: {product_title}",
        f"File: {post_result['file_path']}",
        f"URL: {post_result['url']}",
        f"",
        f"Links:",
    ]
    if amazon_result["affiliate_link"]:
        summary_lines.append(f"  Amazon: {amazon_result['affiliate_link']}")
    if mavely_link:
        summary_lines.append(f"  Mavely: {mavely_link}")
    if tiktok_shop_link:
        summary_lines.append(f"  TikTok Shop: {tiktok_shop_link}")

    summary_lines.append(f"")
    summary_lines.append(f"Video: {'downloaded' if video_result.get('video_path') else 'manual download needed'}")
    summary_lines.append(f"Source: {video_result['platform']} — {url}")

    summary = "\n".join(summary_lines)

    print(f"\n{'='*60}")
    print(summary)
    print(f"{'='*60}")

    return {
        "video": video_result,
        "amazon": amazon_result,
        "blog_post": post_result,
        "summary": summary,
    }


def main():
    """CLI entry point for testing the pipeline."""
    parser = argparse.ArgumentParser(
        description="TikTok/Instagram-to-Blog Pipeline",
        epilog="Example: python pipeline.py https://www.tiktok.com/@user/video/123 --mavely https://mavely.app.link/abc",
    )
    parser.add_argument(
        "url",
        help="Instagram Reel or TikTok video URL",
    )
    parser.add_argument(
        "--mavely",
        default="",
        help="Mavely affiliate link (optional)",
    )
    parser.add_argument(
        "--tiktok-shop",
        default="",
        help="TikTok Shop link (optional)",
    )
    parser.add_argument(
        "--title",
        default="",
        help="Override auto-detected product title",
    )
    parser.add_argument(
        "--category",
        default="deal",
        help="Blog post category tag (default: deal)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full result as JSON",
    )

    args = parser.parse_args()

    result = process_video(
        url=args.url,
        mavely_link=args.mavely,
        tiktok_shop_link=args.tiktok_shop,
        title_override=args.title,
        category=args.category,
    )

    if args.json:
        print("\n" + json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
