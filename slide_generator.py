"""
Social-media slide generator
─────────────────────────────
Renders news articles into branded HTML slides and screenshots them
to PNG using Playwright.

Supported formats:
  • instagram  – 1080 × 1080 px  (feed post / carousel)
  • story      – 1080 × 1920 px  (IG / TikTok story)
  • linkedin   – 1200 × 627 px   (LinkedIn post)
"""

from __future__ import annotations

import html
import asyncio
import tempfile
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path
from typing import Literal

# ──────────────────────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────────────────────

SlideFormat = Literal["instagram", "story", "linkedin"]

DIMENSIONS: dict[SlideFormat, tuple[int, int]] = {
    "instagram": (1080, 1080),
    "story":     (1080, 1920),
    "linkedin":  (1200, 627),
}

# Brand colours (mirrors the Streamlit theme)
NAVY      = "#1a3a6e"
NAVY_DARK = "#0d2150"
NAVY_BG   = "#0a1628"
ACCENT    = "#2e6db4"
WHITE     = "#ffffff"
LIGHT_BG  = "#f0f2f6"
GREY_TEXT = "#b8c9e8"

CATEGORY_ICONS: dict[str, str] = {
    "Stocks": "📈", "Fiats": "💱", "Indexes": "📊", "Regional": "🌏",
    "Country Credit": "🏦", "Alternative Lending": "🤝", "Fintech": "💳",
    "Start-up": "🚀", "Sustainable Finance": "🌿", "Marketing": "📣",
    "Entertainment": "🎬",
}

VERIFY_HIGH = 75


# ──────────────────────────────────────────────────────────────────────────────
#  HTML helpers
# ──────────────────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """HTML-escape user-supplied text."""
    return html.escape(str(text), quote=True)


def _verification_pill(score: int, status: str) -> str:
    if status == "skipped" or score < 0:
        return ""
    if score >= VERIFY_HIGH:
        bg, fg = "#16a34a", WHITE
        label = f"✅ {score}%"
    elif score >= 45:
        bg, fg = "#d97706", WHITE
        label = f"⚠️ {score}%"
    else:
        bg, fg = "#dc2626", WHITE
        label = f"❌ {score}%"
    return (
        f'<span style="background:{bg};color:{fg};font-size:13px;'
        f'padding:3px 10px;border-radius:12px;font-weight:600;">{label}</span>'
    )


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _timestamp_label() -> str:
    sgt = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    return sgt.strftime("%d %b %Y · %H:%M SGT")


# ──────────────────────────────────────────────────────────────────────────────
#  HTML templates
# ──────────────────────────────────────────────────────────────────────────────

def _base_page(body_html: str, width: int, height: int) -> str:
    """Wrap body HTML in a full-page container with brand styling."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    width: {width}px; height: {height}px;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: linear-gradient(160deg, {NAVY_BG} 0%, {NAVY_DARK} 40%, {NAVY} 100%);
    color: {WHITE};
    overflow: hidden;
    -webkit-font-smoothing: antialiased;
  }}

  .slide {{
    width: {width}px; height: {height}px;
    padding: 56px;
    display: flex; flex-direction: column;
    position: relative;
  }}

  /* Decorative accent bar */
  .slide::before {{
    content: '';
    position: absolute; top: 0; left: 0; right: 0;
    height: 6px;
    background: linear-gradient(90deg, {ACCENT}, #60a5fa, {ACCENT});
  }}

  .brand {{
    font-size: 14px; font-weight: 700; letter-spacing: 2px;
    text-transform: uppercase; color: {GREY_TEXT};
    margin-bottom: 8px;
  }}

  .category-label {{
    display: inline-block;
    background: rgba(46,109,180,0.25);
    border: 1px solid rgba(96,165,250,0.3);
    color: #93c5fd;
    font-size: 15px; font-weight: 700;
    padding: 6px 16px; border-radius: 8px;
    letter-spacing: 0.5px;
    margin-bottom: 20px;
  }}

  .timestamp {{
    font-size: 13px; color: {GREY_TEXT}; margin-top: auto;
    letter-spacing: 0.3px;
  }}

  .headline {{
    font-size: 22px; font-weight: 700; line-height: 1.45;
    color: {WHITE}; margin-bottom: 6px;
  }}

  .source {{
    font-size: 13px; font-weight: 600; color: #93c5fd;
  }}

  .summary {{
    font-size: 15px; line-height: 1.55; color: #cbd5e1;
  }}

  .divider {{
    width: 100%; height: 1px;
    background: rgba(148,163,184,0.15);
    margin: 14px 0;
  }}

  .article-row {{
    display: flex; align-items: flex-start; gap: 14px;
  }}

  .article-num {{
    flex-shrink: 0;
    width: 34px; height: 34px;
    background: rgba(46,109,180,0.3);
    border: 1px solid rgba(96,165,250,0.25);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 15px; font-weight: 800; color: #93c5fd;
    margin-top: 2px;
  }}

  .article-body {{ flex: 1; }}

  .footer-bar {{
    display: flex; justify-content: space-between; align-items: center;
    margin-top: auto; padding-top: 20px;
  }}

  .watermark {{
    font-size: 11px; color: rgba(148,163,184,0.4);
    letter-spacing: 1px;
  }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""


# ─── Category summary slide (multi-headline) ────────────────────────────────

def _category_summary_html(
    category: str,
    articles: list[dict],
    fmt: SlideFormat,
) -> str:
    w, h = DIMENSIONS[fmt]
    icon = CATEGORY_ICONS.get(category, "📌")

    # Decide how many articles to show based on format
    max_articles = {"instagram": 5, "story": 7, "linkedin": 3}[fmt]
    shown = articles[:max_articles]

    rows = ""
    for i, art in enumerate(shown, 1):
        title = _esc(_truncate(art.get("title", ""), 100))
        source = _esc(art.get("source", ""))
        v_pill = _verification_pill(
            art.get("verified_score", -1),
            art.get("verified_status", "skipped"),
        )
        rows += f"""
        <div class="article-row">
            <div class="article-num">{i}</div>
            <div class="article-body">
                <div class="headline" style="font-size:{'20px' if len(shown) > 4 else '22px'};">{title}</div>
                <div style="display:flex;align-items:center;gap:10px;margin-top:4px;">
                    <span class="source">🗞️ {source}</span>
                    {v_pill}
                </div>
            </div>
        </div>
        {'<div class="divider"></div>' if i < len(shown) else ''}
        """

    body = f"""
    <div class="slide">
        <div class="brand">📰 24H NEWS EXPLORER</div>
        <div class="category-label">{icon} {_esc(category)}</div>
        <div style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:4px;">
            {rows}
        </div>
        <div class="footer-bar">
            <div class="timestamp">🕐 {_timestamp_label()}</div>
            <div class="watermark">Powered by Claude AI</div>
        </div>
    </div>"""

    return _base_page(body, w, h)


# ─── Single article highlight slide ─────────────────────────────────────────

def _single_article_html(
    article: dict,
    category: str,
    fmt: SlideFormat,
) -> str:
    w, h = DIMENSIONS[fmt]
    icon = CATEGORY_ICONS.get(category, "📌")

    title = _esc(article.get("title", ""))
    source = _esc(article.get("source", ""))
    summary = _esc(_truncate(article.get("summary", ""), 280))
    v_score = article.get("verified_score", -1)
    v_status = article.get("verified_status", "skipped")
    v_pill = _verification_pill(v_score, v_status)

    # Larger title for single-article
    title_size = "32px" if fmt == "story" else "28px"
    summary_size = "18px" if fmt == "story" else "16px"

    body = f"""
    <div class="slide">
        <div class="brand">📰 24H NEWS EXPLORER</div>
        <div class="category-label">{icon} {_esc(category)}</div>

        <div style="flex:1;display:flex;flex-direction:column;justify-content:center;">
            <div class="headline" style="font-size:{title_size};margin-bottom:20px;line-height:1.4;">
                {title}
            </div>

            <div style="display:flex;align-items:center;gap:12px;margin-bottom:24px;">
                <span class="source" style="font-size:15px;">🗞️ {source}</span>
                {v_pill}
            </div>

            <div class="summary" style="font-size:{summary_size};">
                {summary}
            </div>
        </div>

        <div class="footer-bar">
            <div class="timestamp">🕐 {_timestamp_label()}</div>
            <div class="watermark">Powered by Claude AI</div>
        </div>
    </div>"""

    return _base_page(body, w, h)


# ─── Cover / title slide ────────────────────────────────────────────────────

def _cover_slide_html(
    categories: list[str],
    total_articles: int,
    fmt: SlideFormat,
) -> str:
    w, h = DIMENSIONS[fmt]

    cat_pills = " ".join(
        f'<span class="category-label" style="margin:4px;">'
        f'{CATEGORY_ICONS.get(c, "📌")} {_esc(c)}</span>'
        for c in categories
    )

    title_size = "44px" if fmt == "story" else "40px"

    body = f"""
    <div class="slide" style="align-items:center;text-align:center;">
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;">
            <div style="font-size:64px;margin-bottom:20px;">📰</div>
            <div class="headline" style="font-size:{title_size};margin-bottom:12px;">
                24h News Roundup
            </div>
            <div class="summary" style="font-size:20px;margin-bottom:32px;">
                {total_articles} verified articles across {len(categories)} categories
            </div>
            <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:4px;max-width:90%;">
                {cat_pills}
            </div>
        </div>
        <div class="footer-bar" style="width:100%;">
            <div class="timestamp">🕐 {_timestamp_label()}</div>
            <div class="watermark">Powered by Claude AI</div>
        </div>
    </div>"""

    return _base_page(body, w, h)


# ──────────────────────────────────────────────────────────────────────────────
#  Screenshot engine (Playwright)
# ──────────────────────────────────────────────────────────────────────────────

def _find_chromium_executable() -> str | None:
    """Locate a cached Playwright Chromium executable on disk."""
    cache_dir = Path.home() / ".cache" / "ms-playwright"
    if not cache_dir.exists():
        return None
    # Prefer the headless shell, fall back to full chromium
    for pattern in ("chromium_headless_shell-*/chrome-linux/headless_shell",
                    "chromium-*/chrome-linux/chrome"):
        matches = sorted(cache_dir.glob(pattern))
        if matches:
            return str(matches[-1])  # newest build
    return None


async def _screenshot_html(html_content: str, width: int, height: int) -> bytes:
    """Render HTML to PNG bytes using Playwright Chromium."""
    from playwright.async_api import async_playwright

    exe = _find_chromium_executable()
    launch_kwargs: dict = {}
    if exe:
        launch_kwargs["executable_path"] = exe

    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_kwargs)
        page = await browser.new_page(viewport={"width": width, "height": height})
        await page.set_content(html_content, wait_until="networkidle")
        png_bytes = await page.screenshot(type="png")
        await browser.close()

    return png_bytes


def render_slide(html_content: str, width: int, height: int) -> bytes:
    """Synchronous wrapper for screenshot rendering."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Inside an already-running event loop (e.g. Streamlit)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _screenshot_html(html_content, width, height))
            return future.result(timeout=30)
    else:
        return asyncio.run(_screenshot_html(html_content, width, height))


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

def generate_cover_slide(
    categories: list[str],
    total_articles: int,
    fmt: SlideFormat = "instagram",
) -> bytes:
    """Generate a cover/title slide as PNG bytes."""
    w, h = DIMENSIONS[fmt]
    html_content = _cover_slide_html(categories, total_articles, fmt)
    return render_slide(html_content, w, h)


def generate_category_slide(
    category: str,
    articles: list[dict],
    fmt: SlideFormat = "instagram",
) -> bytes:
    """Generate a category summary slide as PNG bytes."""
    w, h = DIMENSIONS[fmt]
    html_content = _category_summary_html(category, articles, fmt)
    return render_slide(html_content, w, h)


def generate_article_slide(
    article: dict,
    category: str,
    fmt: SlideFormat = "instagram",
) -> bytes:
    """Generate a single-article highlight slide as PNG bytes."""
    w, h = DIMENSIONS[fmt]
    html_content = _single_article_html(article, category, fmt)
    return render_slide(html_content, w, h)


def generate_all_slides(
    raw_articles: dict[str, list[dict]],
    fmt: SlideFormat = "instagram",
    mode: Literal["summary", "individual", "both"] = "summary",
) -> list[tuple[str, bytes]]:
    """
    Generate a full set of slides and return as a list of (filename, png_bytes).

    Modes:
      • summary    – one cover slide + one slide per category
      • individual – one slide per article
      • both       – cover + per-category + per-article
    """
    slides: list[tuple[str, bytes]] = []
    all_cats = [c for c in raw_articles if raw_articles[c]]
    total = sum(len(arts) for arts in raw_articles.values())

    # Cover slide
    if mode in ("summary", "both"):
        png = generate_cover_slide(all_cats, total, fmt)
        slides.append(("00_cover.png", png))

    # Per-category slides
    if mode in ("summary", "both"):
        for i, (cat, arts) in enumerate(raw_articles.items(), 1):
            if not arts:
                continue
            png = generate_category_slide(cat, arts, fmt)
            safe_cat = cat.lower().replace(" ", "_")
            slides.append((f"{i:02d}_{safe_cat}_summary.png", png))

    # Per-article slides
    if mode in ("individual", "both"):
        idx = len(slides)
        for cat, arts in raw_articles.items():
            for art in arts:
                idx += 1
                png = generate_article_slide(art, cat, fmt)
                safe_title = art.get("title", "article")[:40].replace(" ", "_")
                safe_title = "".join(c for c in safe_title if c.isalnum() or c == "_")
                slides.append((f"{idx:02d}_{safe_title}.png", png))

    return slides
