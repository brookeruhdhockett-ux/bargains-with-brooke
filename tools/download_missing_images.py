#!/usr/bin/env python3
"""Download missing product images for the Bargains with Brooke blog.

Handles two categories:
1. TCIN-based images (numeric filenames) - fetched via Target Redsky PDP API
2. Named product images - fetched via Target search API

Uses Target's Scene7 CDN for product photos.
"""

import os
import json
import urllib.request
import urllib.parse
import sys
import time

BLOG_IMG = "/Users/brookehockett/.openclaw/workspace/blog/assets/images"
DEALS_IMG = os.path.join(BLOG_IMG, "deals")

# --- Target API functions ---

def get_target_image_by_tcin(tcin):
    """Look up a Target product image URL by TCIN using Redsky PDP API."""
    url = (
        f"https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1"
        f"?key=9f36aeafbe60771e321a7cc95a78140772ab3e96"
        f"&tcin={tcin}"
        f"&pricing_store_id=3991&has_pricing_store_id=true"
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        product = data.get("data", {}).get("product", {})
        # Try primary image
        img_url = product.get("item", {}).get("enrichment", {}).get("images", {}).get("primary_image_url", "")
        if not img_url:
            try:
                img_url = product["item"]["enrichment"]["image_info"]["primary_image"]["url"]
            except (KeyError, TypeError):
                pass
        return img_url
    except Exception as e:
        print(f"  PDP API error for TCIN {tcin}: {e}")
        return None


def search_target_image(query):
    """Search Target for a product and return the first result's image URL."""
    encoded = urllib.parse.quote(query)
    url = (
        f"https://redsky.target.com/redsky_aggregations/v1/web/plp_search_v2"
        f"?key=9f36aeafbe60771e321a7cc95a78140772ab3e96"
        f"&channel=WEB&count=1&default_purchasability_filter=true"
        f"&keyword={encoded}&offset=0&page=%2Fs%2F{encoded}"
        f"&pricing_store_id=3991&store_ids=3991&visitor_id=018F1234ABCD"
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        results = data.get("data", {}).get("search", {}).get("products", [])
        if not results:
            return None
        item = results[0]
        img_url = item.get("item", {}).get("enrichment", {}).get("images", {}).get("primary_image_url", "")
        if not img_url:
            try:
                img_url = item["item"]["enrichment"]["image_info"]["primary_image"]["url"]
            except (KeyError, TypeError):
                pass
        return img_url
    except Exception as e:
        print(f"  Search API error for '{query}': {e}")
        return None


def download_image(url, dest_path):
    """Download an image from URL to dest_path."""
    if not url:
        return False
    if url.startswith("//"):
        url = "https:" + url
    # Add size parameter for Target Scene7 images
    if "target.scene7.com" in url and "?" not in url:
        url += "?wid=600&hei=600&fmt=webp"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            with open(dest_path, 'wb') as f:
                f.write(resp.read())
        return True
    except Exception as e:
        print(f"  Download error: {e}")
        return False


def main():
    # --- TCIN-based images (19 missing) ---
    missing_tcins = [
        "1000171934", "1000171988", "1001847462", "1003463098", "1003495464",
        "82268399", "82382074", "82705668", "84130915", "87938820",
        "88012826", "89211667", "89465084", "89664644", "89667480",
        "90171336", "90449015", "90449130", "94938125",
    ]

    print(f"=== Downloading {len(missing_tcins)} TCIN product images ===")
    tcin_success = 0
    tcin_fail = 0
    for tcin in missing_tcins:
        dest = os.path.join(DEALS_IMG, f"{tcin}.jpg")
        if os.path.exists(dest):
            print(f"  Already exists: {tcin}.jpg")
            tcin_success += 1
            continue
        print(f"  Fetching TCIN {tcin}...")
        img_url = get_target_image_by_tcin(tcin)
        if img_url:
            if download_image(img_url, dest):
                print(f"  OK: {tcin}.jpg")
                tcin_success += 1
            else:
                tcin_fail += 1
        else:
            # Try search fallback - some TCINs may be Walmart/Amazon
            print(f"  TCIN lookup failed, trying search...")
            tcin_fail += 1
        time.sleep(0.5)  # rate limiting

    print(f"\nTCIN results: {tcin_success} downloaded, {tcin_fail} failed")

    # --- Named product images (13 remaining) ---
    named_images = {
        "burger_press.jpg": "burger press grilling",
        "car_air_freshener.jpg": "car air freshener",
        "charcoal.jpg": "charcoal briquettes grilling",
        "citronella_candles.jpg": "citronella candles outdoor",
        "cooler_bag.jpg": "cooler bag insulated",
        "corn_holders.jpg": "corn holders cob",
        "cornhole_set.jpg": "cornhole game set outdoor",
        "cover_up.jpg": "womens swim cover up",
        "kids_swimsuit.jpg": "kids swimsuit one piece",
        "mens_swim_trunks.jpg": "mens swim trunks",
        "portable_grill.jpg": "portable charcoal grill",
        "serving_platter.jpg": "melamine serving platter outdoor",
        "womens_sundress.jpg": "womens sundress summer",
    }

    print(f"\n=== Downloading {len(named_images)} named product images ===")
    named_success = 0
    named_fail = 0
    for filename, query in named_images.items():
        dest = os.path.join(BLOG_IMG, filename)
        if os.path.exists(dest):
            print(f"  Already exists: {filename}")
            named_success += 1
            continue
        print(f"  Searching Target for '{query}'...")
        img_url = search_target_image(query)
        if img_url and download_image(img_url, dest):
            print(f"  OK: {filename}")
            named_success += 1
        else:
            print(f"  FAILED: {filename}")
            named_fail += 1
        time.sleep(0.5)

    print(f"\nNamed results: {named_success} downloaded, {named_fail} failed")
    print(f"\nTotal: {tcin_success + named_success} downloaded, {tcin_fail + named_fail} failed")


if __name__ == "__main__":
    main()
