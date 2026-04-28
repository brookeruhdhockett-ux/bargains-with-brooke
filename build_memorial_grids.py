#!/usr/bin/env python3
"""Build 3 Memorial Day deal grids for Bargains with Brooke blog.
Fetches real Target product photos via Redsky API, removes white backgrounds,
and composites into editorial-style grids using Pillow."""

import os
import json
import urllib.request
import urllib.parse
from PIL import Image, ImageDraw, ImageFont

# --- Paths ---
BASE = "/Users/brookehockett/.openclaw/workspace/blog"
PRODUCTS_DIR = os.path.join(BASE, "assets/images/products")
OUTPUT_DIR = os.path.join(BASE, "assets/images")
os.makedirs(PRODUCTS_DIR, exist_ok=True)

# --- Grid specs ---
CANVAS_W = 1000
CANVAS_H = 1200
BG_COLOR = (248, 244, 237)
HEADER_COLOR = (180, 50, 50)
HEADER_TEXT_COLOR = (240, 236, 228)
DIVIDER_COLOR = (220, 215, 208)
PRODUCT_NAME_COLOR = (120, 100, 80)
PRICE_COLOR = (180, 50, 50)
FOOTER_COLOR = (120, 100, 80)

# --- Fonts ---
def load_font(name, size):
    paths = {
        "didot": "/System/Library/Fonts/Supplemental/Didot.ttc",
        "georgia": "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "georgia_bold": "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    }
    path = paths.get(name)
    if path and os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except:
            pass
    # Fallbacks
    for p in ["/System/Library/Fonts/Supplemental/Georgia.ttf",
              "/System/Library/Fonts/Supplemental/Didot.ttc",
              "/System/Library/Fonts/Helvetica.ttc"]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except:
                pass
    return ImageFont.load_default()

FONT_SMALL = load_font("georgia", 28)
FONT_TITLE = load_font("didot", 42)
FONT_PRODUCT_NAME = load_font("didot", 18)
FONT_PRICE = load_font("georgia", 22)
FONT_FOOTER = load_font("georgia", 20)
FONT_AD = load_font("georgia", 14)

# --- Target API ---
def search_target(query):
    """Search Target Redsky API, return (title, price, image_url) or None."""
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
        title = item.get("item", {}).get("product_description", {}).get("title", query)
        # Price
        price_info = item.get("price", {})
        current = price_info.get("formatted_current_price", "")
        reg = price_info.get("formatted_current_price_default_message", "")
        price_str = current or reg or ""
        # Image
        img_url = item.get("item", {}).get("enrichment", {}).get("images", {}).get("primary_image_url", "")
        if not img_url:
            # Try alternate path
            try:
                img_url = item["item"]["enrichment"]["image_info"]["primary_image"]["url"]
            except:
                pass
        return {"title": title, "price": price_str, "image_url": img_url}
    except Exception as e:
        print(f"  API error for '{query}': {e}")
        return None


def download_image(url, filename):
    """Download image to PRODUCTS_DIR, return local path."""
    path = os.path.join(PRODUCTS_DIR, filename)
    if os.path.exists(path):
        print(f"  Already have: {filename}")
        return path
    if not url:
        return None
    # Ensure full URL
    if url.startswith("//"):
        url = "https:" + url
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            with open(path, 'wb') as f:
                f.write(resp.read())
        print(f"  Downloaded: {filename}")
        return path
    except Exception as e:
        print(f"  Download error for {filename}: {e}")
        return None


def remove_white_bg(img):
    """Remove white background (threshold > 230 RGB) and return RGBA image."""
    img = img.convert("RGBA")
    data = img.getdata()
    new_data = []
    for r, g, b, a in data:
        if r > 230 and g > 230 and b > 230:
            new_data.append((r, g, b, 0))
        else:
            new_data.append((r, g, b, a))
    img.putdata(new_data)
    return img


def build_grid(subtitle, title, products_data, output_filename):
    """Build one Memorial Day grid image."""
    print(f"\n=== Building: {title} ===")

    # Fetch products
    products = []
    for query_list in products_data:
        if isinstance(query_list, str):
            query_list = [query_list]
        found = None
        for q in query_list:
            result = search_target(q)
            if result and result["image_url"]:
                found = result
                found["query"] = q
                break
            else:
                print(f"  No result for '{q}', trying next...")
        if found:
            safe_name = found["query"].replace(" ", "_").replace("/", "_") + ".jpg"
            local_path = download_image(found["image_url"], safe_name)
            found["local_path"] = local_path
            products.append(found)
            print(f"  Found: {found['title'][:50]}... @ {found['price']}")
        else:
            print(f"  WARNING: Could not find product for {query_list}")
            products.append({"title": str(query_list[0]), "price": "", "local_path": None, "query": query_list[0]})

    # --- Build canvas ---
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    # Header banner
    header_h = 140
    draw.rectangle([0, 0, CANVAS_W, header_h], fill=HEADER_COLOR)

    # Subtitle (e.g. "memorial day")
    sub_bb = draw.textbbox((0, 0), subtitle, font=FONT_SMALL)
    sub_w = sub_bb[2] - sub_bb[0]
    draw.text(((CANVAS_W - sub_w) // 2, 25), subtitle, fill=HEADER_TEXT_COLOR, font=FONT_SMALL)

    # Title (e.g. "OUTDOOR ENTERTAINING")
    title_bb = draw.textbbox((0, 0), title, font=FONT_TITLE)
    title_w = title_bb[2] - title_bb[0]
    draw.text(((CANVAS_W - title_w) // 2, 70), title, fill=HEADER_TEXT_COLOR, font=FONT_TITLE)

    # #ad in top right
    draw.text((CANVAS_W - 50, 10), "#ad", fill=HEADER_TEXT_COLOR, font=FONT_AD)

    # 3x2 product grid
    grid_top = header_h + 20
    grid_bottom = CANVAS_H - 60  # leave room for footer
    avail_h = grid_bottom - grid_top
    avail_w = CANVAS_W - 40  # 20px margin each side

    cols = 3
    rows = 2
    cell_w = avail_w // cols
    cell_h = avail_h // rows
    img_area_h = cell_h - 55  # room for name + price below image

    for i, prod in enumerate(products[:6]):
        col = i % cols
        row = i // cols
        x = 20 + col * cell_w
        y = grid_top + row * cell_h

        # Draw divider lines
        if col > 0:
            line_x = x
            draw.line([(line_x, grid_top), (line_x, grid_bottom)], fill=DIVIDER_COLOR, width=1)
        if row > 0 and col == 0:
            line_y = y
            draw.line([(20, line_y), (CANVAS_W - 20, line_y)], fill=DIVIDER_COLOR, width=1)

        # Product image
        if prod.get("local_path") and os.path.exists(prod["local_path"]):
            try:
                pimg = Image.open(prod["local_path"])
                pimg = remove_white_bg(pimg)
                # Fit into cell
                max_w = cell_w - 30
                max_h = img_area_h - 20
                pimg.thumbnail((max_w, max_h), Image.LANCZOS)
                pw, ph = pimg.size
                px = x + (cell_w - pw) // 2
                py = y + (img_area_h - ph) // 2 + 5
                # Paste with transparency
                canvas.paste(pimg, (px, py), pimg)
            except Exception as e:
                print(f"  Image error: {e}")

        # Product name (uppercase, centered)
        name = prod.get("title", "")
        # Truncate for display
        if len(name) > 28:
            name = name[:26] + "..."
        name = name.upper()
        name_bb = draw.textbbox((0, 0), name, font=FONT_PRODUCT_NAME)
        name_w = name_bb[2] - name_bb[0]
        name_x = x + (cell_w - name_w) // 2
        name_y = y + img_area_h
        draw.text((name_x, name_y), name, fill=PRODUCT_NAME_COLOR, font=FONT_PRODUCT_NAME)

        # Price
        price = prod.get("price", "")
        if price:
            price_bb = draw.textbbox((0, 0), price, font=FONT_PRICE)
            price_w = price_bb[2] - price_bb[0]
            price_x = x + (cell_w - price_w) // 2
            price_y = name_y + 22
            draw.text((price_x, price_y), price, fill=PRICE_COLOR, font=FONT_PRICE)

    # Footer
    footer_text = "bargains with brooke"
    ft_bb = draw.textbbox((0, 0), footer_text, font=FONT_FOOTER)
    ft_w = ft_bb[2] - ft_bb[0]
    draw.text(((CANVAS_W - ft_w) // 2, CANVAS_H - 40), footer_text, fill=FOOTER_COLOR, font=FONT_FOOTER)

    # Save
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    canvas.save(output_path, "JPEG", quality=92)
    print(f"  Saved: {output_path} ({CANVAS_W}x{CANVAS_H})")
    return output_path


# --- Grid definitions ---
grids = [
    {
        "subtitle": "memorial day",
        "title": "OUTDOOR ENTERTAINING",
        "filename": "grid_memorial_outdoor.jpg",
        "products": [
            ["string lights outdoor", "outdoor string lights patio"],
            ["bluetooth outdoor speaker", "portable bluetooth speaker"],
            ["igloo cooler", "cooler igloo 48 quart"],
            ["cornhole game set", "cornhole outdoor game"],
            ["melamine serving platter", "melamine platter outdoor"],
            ["citronella candle outdoor", "citronella torch candle"],
        ]
    },
    {
        "subtitle": "memorial day",
        "title": "SUMMER CLOTHING DEALS",
        "filename": "grid_memorial_clothing.jpg",
        "products": [
            ["mens swim trunks", "mens board shorts swim"],
            ["womens sundress", "womens summer dress casual"],
            ["girls swimsuit", "girls one piece swimsuit"],
            ["womens sandals flat", "womens slide sandals"],
            ["sun hat wide brim", "womens sun hat straw"],
            ["swim cover up", "womens swim coverup"],
        ]
    },
    {
        "subtitle": "memorial day",
        "title": "GRILLING DEALS",
        "filename": "grid_memorial_grilling.jpg",
        "products": [
            ["portable charcoal grill", "charcoal grill portable"],
            ["kingsford charcoal", "charcoal briquets kingsford"],
            ["grill brush", "grill cleaning brush"],
            ["burger press", "hamburger press patty"],
            ["corn holders set", "corn on cob holders"],
            ["cooler bag lunch", "insulated cooler bag"],
        ]
    },
]

if __name__ == "__main__":
    for grid in grids:
        build_grid(grid["subtitle"], grid["title"], grid["products"], grid["filename"])
    print("\n✓ All 3 Memorial Day grids built!")
