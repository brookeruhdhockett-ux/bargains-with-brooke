"""
amazon_linker.py — Search Amazon for products and generate affiliate links.

Uses PA-API 5.0 when credentials are available, otherwise falls back to
generating a tagged search URL.

Environment variables:
    AMAZON_ACCESS_KEY   — PA-API access key
    AMAZON_SECRET_KEY   — PA-API secret key
    AMAZON_PARTNER_TAG  — Affiliate tag (default: brookehockett-20)
"""

import os
import re
import json
import hashlib
import hmac
import datetime
from typing import Optional
from urllib.parse import quote, quote_plus

try:
    import requests
except ImportError:
    requests = None

PARTNER_TAG = os.environ.get("AMAZON_PARTNER_TAG", "brookehockett-20")
ACCESS_KEY = os.environ.get("AMAZON_ACCESS_KEY", "")
SECRET_KEY = os.environ.get("AMAZON_SECRET_KEY", "")
PA_API_HOST = "webservices.amazon.com"
PA_API_REGION = "us-east-1"
PA_API_PATH = "/paapi5/searchitems"

# Common filler words to strip from search queries
STOP_WORDS = {
    "i", "me", "my", "the", "a", "an", "is", "was", "are", "this", "that",
    "it", "its", "for", "and", "or", "but", "in", "on", "at", "to", "of",
    "so", "if", "do", "did", "just", "got", "get", "had", "has", "have",
    "been", "be", "can", "will", "would", "could", "should", "from", "with",
    "you", "your", "they", "them", "her", "his", "she", "he", "we", "our",
    "not", "no", "all", "any", "some", "very", "really", "actually", "too",
    "also", "more", "most", "like", "love", "need", "want", "thing", "things",
    "here", "there", "when", "what", "how", "who", "which", "these", "those",
    "about", "up", "out", "one", "two", "every", "each", "much", "many",
    "such", "than", "then", "now", "way", "even", "still", "back", "only",
    "said", "says", "say", "come", "go", "going", "make", "made", "use",
    "using", "best", "good", "great", "new", "found", "find", "never",
    "ever", "omg", "wow", "literally", "obsessed", "run", "linked",
    "link", "bio", "comment", "below", "check", "ad", "sponsored",
}


def extract_keywords(caption: str) -> str:
    """
    Extract meaningful product keywords from a social media caption.

    Strips hashtags, mentions, URLs, emojis, and filler words.
    Returns a clean search query string.

    Args:
        caption: Raw caption/description text

    Returns:
        Clean keyword string for product search
    """
    if not caption:
        return ""

    text = caption.lower()

    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove hashtags
    text = re.sub(r"#\w+", "", text)
    # Remove @mentions
    text = re.sub(r"@\w+", "", text)
    # Remove emojis and special characters, keep letters/numbers/spaces
    text = re.sub(r"[^\w\s]", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Remove stop words
    words = [w for w in text.split() if w not in STOP_WORDS and len(w) > 1]

    # Take the first ~8 meaningful words to keep the query focused
    keywords = " ".join(words[:8])
    return keywords


def generate_search_url(query: str, tag: str = None) -> str:
    """
    Generate a tagged Amazon search URL.

    This is the fallback when PA-API credentials aren't available.

    Args:
        query: Search terms
        tag: Affiliate tag (defaults to PARTNER_TAG)

    Returns:
        Amazon search URL with affiliate tag
    """
    tag = tag or PARTNER_TAG
    encoded_query = quote_plus(query)
    return f"https://www.amazon.com/s?k={encoded_query}&tag={tag}"


def search_amazon_paapi(query: str, tag: str = None) -> Optional[dict]:
    """
    Search Amazon using PA-API 5.0 (Product Advertising API).

    Requires AMAZON_ACCESS_KEY and AMAZON_SECRET_KEY env vars.

    Args:
        query: Search terms
        tag: Affiliate tag (defaults to PARTNER_TAG)

    Returns:
        dict with title, price, image_url, affiliate_link, asin
        or None if the API call fails
    """
    if not ACCESS_KEY or not SECRET_KEY:
        return None

    if requests is None:
        print("[amazon_linker] requests library not available")
        return None

    tag = tag or PARTNER_TAG
    now = datetime.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    payload = json.dumps({
        "Keywords": query,
        "SearchIndex": "All",
        "ItemCount": 1,
        "Resources": [
            "ItemInfo.Title",
            "Offers.Listings.Price",
            "Images.Primary.Large",
        ],
        "PartnerTag": tag,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.com",
    })

    # AWS Signature V4 signing
    content_type = "application/json; charset=utf-8"
    amz_target = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"

    headers_to_sign = {
        "content-encoding": "amz-1.0",
        "content-type": content_type,
        "host": PA_API_HOST,
        "x-amz-date": amz_date,
        "x-amz-target": amz_target,
    }

    signed_headers_str = ";".join(sorted(headers_to_sign.keys()))
    canonical_headers = "".join(
        f"{k}:{v}\n" for k, v in sorted(headers_to_sign.items())
    )

    payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    canonical_request = "\n".join([
        "POST",
        PA_API_PATH,
        "",  # query string
        canonical_headers,
        signed_headers_str,
        payload_hash,
    ])

    credential_scope = f"{date_stamp}/{PA_API_REGION}/ProductAdvertisingAPI/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])

    def _sign(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    signing_key = _sign(
        _sign(
            _sign(
                _sign(("AWS4" + SECRET_KEY).encode("utf-8"), date_stamp),
                PA_API_REGION,
            ),
            "ProductAdvertisingAPI",
        ),
        "aws4_request",
    )

    signature = hmac.new(
        signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    auth_header = (
        f"AWS4-HMAC-SHA256 Credential={ACCESS_KEY}/{credential_scope}, "
        f"SignedHeaders={signed_headers_str}, Signature={signature}"
    )

    request_headers = {
        "Content-Type": content_type,
        "Content-Encoding": "amz-1.0",
        "Host": PA_API_HOST,
        "X-Amz-Date": amz_date,
        "X-Amz-Target": amz_target,
        "Authorization": auth_header,
    }

    try:
        resp = requests.post(
            f"https://{PA_API_HOST}{PA_API_PATH}",
            headers=request_headers,
            data=payload,
            timeout=10,
        )
        if not resp.ok:
            print(f"[amazon_linker] PA-API error {resp.status_code}: {resp.text[:200]}")
            return None

        data = resp.json()
        items = data.get("SearchResult", {}).get("Items", [])
        if not items:
            return None

        item = items[0]
        title = item.get("ItemInfo", {}).get("Title", {}).get("DisplayValue", query)
        asin = item.get("ASIN", "")
        detail_url = item.get("DetailPageURL", "")

        # Price
        price = ""
        listings = item.get("Offers", {}).get("Listings", [])
        if listings:
            price_info = listings[0].get("Price", {})
            price = price_info.get("DisplayAmount", "")

        # Image
        image_url = ""
        primary = item.get("Images", {}).get("Primary", {})
        large = primary.get("Large", {})
        image_url = large.get("URL", "")

        return {
            "title": title,
            "price": price,
            "image_url": image_url,
            "affiliate_link": detail_url,
            "asin": asin,
        }

    except Exception as e:
        print(f"[amazon_linker] PA-API request failed: {e}")
        return None


def search_product(caption_or_title: str, tag: str = None) -> dict:
    """
    Main entry point: search for a product on Amazon.

    Tries PA-API first, then falls back to a tagged search URL.

    Args:
        caption_or_title: Product caption or title text
        tag: Affiliate tag (defaults to brookehockett-20)

    Returns:
        dict with: title, price, image_url, affiliate_link, search_query, method
    """
    tag = tag or PARTNER_TAG
    keywords = extract_keywords(caption_or_title)

    if not keywords:
        keywords = caption_or_title[:60]

    # Try PA-API first
    result = search_amazon_paapi(keywords, tag)
    if result:
        result["search_query"] = keywords
        result["method"] = "pa-api"
        return result

    # Fallback: generate search URL
    search_url = generate_search_url(keywords, tag)
    return {
        "title": keywords.title(),
        "price": "",
        "image_url": "",
        "affiliate_link": search_url,
        "asin": "",
        "search_query": keywords,
        "method": "search-url",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python amazon_linker.py '<product caption or description>'")
        print("\nExample:")
        print("  python amazon_linker.py 'Stanley Quencher 40oz Tumbler'")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    result = search_product(query)
    print(json.dumps(result, indent=2))
