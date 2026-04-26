"""
blog_post_builder.py — Generate HTML blog post pages for bargainswithbrooke.com.

Matches the existing site structure and CSS classes used in posts like
mothers-day-gifts.html. Includes video embed, affiliate buttons, email
signup form, and Pinterest Rich Pin meta tags.
"""

import os
import re
from typing import Optional
from datetime import datetime
from pathlib import Path
from textwrap import dedent

POSTS_DIR = Path(__file__).resolve().parent.parent / "posts"
POSTS_DIR.mkdir(parents=True, exist_ok=True)


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:80]


def build_blog_post(
    video_path: Optional[str] = None,
    product_title: str = "",
    product_description: str = "",
    amazon_link: str = "",
    tiktok_shop_link: str = "",
    mavely_link: str = "",
    thumbnail_url: str = "",
    caption: str = "",
    category: str = "deal",
    source_platform: str = "",
    date_str: str = None,
) -> dict:
    """
    Generate an HTML blog post page.

    Matches the structure of existing posts on bargainswithbrooke.com:
    - nav bar
    - post header with category tag, h1, date
    - video embed (HTML5 <video>)
    - product description
    - affiliate link buttons (only for links that exist)
    - email signup form
    - footer

    Args:
        video_path: Path to local video file (relative to blog root preferred)
        product_title: Product name/title
        product_description: Description paragraph
        amazon_link: Amazon affiliate link
        tiktok_shop_link: TikTok Shop link
        mavely_link: Mavely affiliate link
        thumbnail_url: Thumbnail/poster image URL for the video
        caption: Original caption from social media
        category: Post category tag (default: "deal")
        source_platform: "instagram" or "tiktok"
        date_str: Date string (default: today)

    Returns:
        dict with: file_path, slug, url, title
    """
    if not date_str:
        date_str = datetime.now().strftime("%B %d, %Y").replace(" 0", " ")
        # Lowercase to match existing style
        date_str = date_str.lower()
        # Fix: "april 5, 2026" not "april 05, 2026"

    if not product_title:
        product_title = "untitled deal"

    slug = slugify(product_title)
    filename = f"{slug}.html"
    file_path = POSTS_DIR / filename

    # Build the description text
    description = product_description or caption or f"check out this deal on {product_title}"
    # Clean up for meta description (strip HTML, limit length)
    meta_description = re.sub(r"<[^>]+>", "", description)[:160]

    # Build video path relative to the post
    video_relative = ""
    if video_path:
        video_abs = Path(video_path).resolve()
        try:
            video_relative = os.path.relpath(video_abs, POSTS_DIR)
        except ValueError:
            video_relative = video_path

    # Build affiliate buttons
    buttons_html = _build_affiliate_buttons(
        amazon_link=amazon_link,
        tiktok_shop_link=tiktok_shop_link,
        mavely_link=mavely_link,
    )

    # Source attribution
    source_note = ""
    if source_platform == "tiktok":
        source_note = "as seen on TikTok"
    elif source_platform == "instagram":
        source_note = "as seen on Instagram"

    # Video section
    video_section = ""
    if video_relative:
        poster_attr = f' poster="{thumbnail_url}"' if thumbnail_url else ""
        video_section = dedent(f"""\
          <div class="post-video-wrap">
            <video controls playsinline preload="metadata"{poster_attr} class="post-video">
              <source src="{video_relative}" type="video/mp4">
              your browser does not support the video tag.
            </video>
          </div>
        """)
    elif thumbnail_url:
        video_section = dedent(f"""\
          <img src="{thumbnail_url}" alt="{product_title}" class="post-grid-image">
        """)

    html = dedent(f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>{product_title.lower()} — bargains with brooke</title>
      <meta name="description" content="{meta_description}">
      <meta property="og:title" content="{product_title.lower()} — bargains with brooke">
      <meta property="og:description" content="{meta_description}">
      <meta property="og:type" content="article">
      <meta property="article:published_time" content="{datetime.now().strftime('%Y-%m-%d')}">
      <meta name="pinterest-rich-pin" content="true">
      <meta property="og:site_name" content="bargains with brooke">
    """)

    # Add og:image if we have a thumbnail
    if thumbnail_url:
        html += f'  <meta property="og:image" content="{thumbnail_url}">\n'

    # Add og:video if we have a video
    if video_relative:
        html += f'  <meta property="og:video" content="{video_relative}">\n'
        html += '  <meta property="og:video:type" content="video/mp4">\n'

    html += dedent(f"""\
      <link rel="stylesheet" href="../assets/css/style.css?v=5">
    </head>
    <body>

      <nav>
        <div class="nav-inner">
          <a href="../" class="nav-logo">bargains with brooke</a>
          <ul class="nav-links">
            <li><a href="../">deals</a></li>
            <li><a href="#">gift guides</a></li>
            <li><a href="../about.html">about</a></li>
          </ul>
        </div>
      </nav>

      <div class="post-header">
        <span class="post-category-tag">{category}</span>
        <h1>{product_title.lower()}</h1>
        <div class="post-meta">{date_str}{' · ' + source_note if source_note else ''}</div>
      </div>

    """)

    # Video embed
    html += video_section

    # Product description
    html += dedent(f"""\
      <div class="post-intro">
        <p>{description}</p>
      </div>

    """)

    # Affiliate buttons section
    if buttons_html:
        html += dedent(f"""\
      <div class="products-list">
        <div class="product-card">
          <div class="product-card-body">
            <div class="product-card-name">{product_title}</div>
    {buttons_html}
          </div>
        </div>
      </div>

    """)

    # Email signup form (matches existing posts)
    html += dedent("""\
      <div class="post-email-signup">
        <p>want deals like these in your inbox every week?</p>
        <form action="https://placeholder.us22.list-manage.com/subscribe/post" method="post" target="_blank">
          <input type="email" name="EMAIL" placeholder="your email for weekly deals" required>
          <button type="submit">subscribe</button>
        </form>
      </div>

      <footer>
        <div class="footer-brand">bargains with brooke</div>
        <p><a href="https://instagram.com/brookecohome">@brookecohome</a></p>
        <p class="ad-disclosure">this site contains affiliate links. i may earn a small commission at no extra cost to you. #ad</p>
      </footer>

    </body>
    </html>
    """)

    with open(file_path, "w") as f:
        f.write(html)

    print(f"[blog_post_builder] Created: {file_path}")

    return {
        "file_path": str(file_path),
        "slug": slug,
        "url": f"posts/{filename}",
        "title": product_title,
    }


def _build_affiliate_buttons(
    amazon_link: str = "",
    tiktok_shop_link: str = "",
    mavely_link: str = "",
) -> str:
    """Build HTML for affiliate link buttons. Only includes buttons for links that exist."""
    buttons = []

    if mavely_link:
        buttons.append(
            f'        <a href="{mavely_link}" class="product-card-btn" '
            f'rel="nofollow sponsored">shop this deal</a>'
        )

    if amazon_link:
        buttons.append(
            f'        <a href="{amazon_link}" class="product-card-btn product-card-btn-amazon" '
            f'rel="nofollow sponsored">find on amazon</a>'
        )

    if tiktok_shop_link:
        buttons.append(
            f'        <a href="{tiktok_shop_link}" class="product-card-btn product-card-btn-tiktok" '
            f'rel="nofollow sponsored">shop on tiktok</a>'
        )

    return "\n".join(buttons)


if __name__ == "__main__":
    # Quick test: generate a sample post
    result = build_blog_post(
        product_title="Stanley Quencher 40oz Tumbler",
        product_description="the tumbler that needs no introduction. keeps drinks cold for hours and fits in every cup holder.",
        amazon_link="https://www.amazon.com/s?k=stanley+quencher+40oz&tag=brookehockett-20",
        mavely_link="https://mavely.app.link/example",
        category="deal",
    )
    print(f"\nGenerated: {result['file_path']}")
    print(f"URL: {result['url']}")
