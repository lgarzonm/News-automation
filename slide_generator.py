"""
TikTok carousel slide generator
────────────────────────────────
Renders news articles into branded HTML slides and screenshots them
to PNG using Playwright.

Format: 1080 × 1350 px  (4:5 ratio)
  – Best for text-heavy TikTok carousels
  – Caption sits below the image → no UI overlay on content
  – Safe for mobile: all font sizes tuned for phone screens
    (1080 canvas ÷ ~2.88 device-pixel-ratio ≈ 375 CSS px)

Hierarchy:
  TITLE / HOOK  →  huge, bold, the scroll-stopper
  BODY CONTENT  →  ~90 words, comfortable reading size
"""

from __future__ import annotations

import html
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Literal

# ──────────────────────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────────────────────

# TikTok carousel – 4:5 ratio, text-safe (caption below image)
WIDTH, HEIGHT = 1080, 1350

CATEGORY_ICONS: dict[str, str] = {
    "Stocks": "📈", "Fiats": "💱", "Indexes": "📊", "Regional": "🌏",
    "Country Credit": "🏦", "Alternative Lending": "🤝", "Fintech": "💳",
    "Start-up": "🚀", "Sustainable Finance": "🌿", "Marketing": "📣",
    "Entertainment": "🎬",
}

CATEGORY_ACCENTS: dict[str, str] = {
    "Stocks": "#10b981", "Fiats": "#f59e0b", "Indexes": "#6366f1",
    "Regional": "#ec4899", "Country Credit": "#8b5cf6",
    "Alternative Lending": "#14b8a6", "Fintech": "#3b82f6",
    "Start-up": "#f97316", "Sustainable Finance": "#22c55e",
    "Marketing": "#e11d48", "Entertainment": "#a855f7",
}

VERIFY_HIGH = 75

# Font sizes tuned for mobile (÷2.88 ≈ screen px)
# Hook/title : 78px → ~27px on screen  (bold, punchy)
# Body       : 36px → ~12.5px on screen (comfortable read)
# Source     : 30px → ~10px on screen
# Meta/brand : 24px → ~8px on screen

HOOK_SIZE = 78
BODY_SIZE = 36
SOURCE_SIZE = 30
META_SIZE = 24
CATEGORY_SIZE = 28
BADGE_SIZE = 22


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _timestamp_label() -> str:
    sgt = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    return sgt.strftime("%d %b %Y  •  %H:%M SGT")


def _verify_badge(score: int, status: str) -> str:
    if status == "skipped" or score < 0:
        return ""
    if score >= VERIFY_HIGH:
        bg, border, fg, icon = "rgba(22,163,74,0.15)", "#22c55e", "#4ade80", "✓"
    elif score >= 45:
        bg, border, fg, icon = "rgba(217,119,6,0.15)", "#f59e0b", "#fbbf24", "~"
    else:
        bg, border, fg, icon = "rgba(220,38,38,0.15)", "#ef4444", "#f87171", "✗"
    return (
        f'<span style="display:inline-flex;align-items:center;gap:6px;'
        f'background:{bg};border:1.5px solid {border};color:{fg};'
        f'font-size:{BADGE_SIZE}px;font-weight:700;padding:6px 16px;'
        f'border-radius:24px;">{icon} {score}%</span>'
    )


def _base_page(body: str) -> str:
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        "<style>"
        "*{margin:0;padding:0;box-sizing:border-box;}"
        f"body{{width:{WIDTH}px;height:{HEIGHT}px;"
        "font-family:'Inter',-apple-system,'SF Pro Display','Segoe UI',Helvetica,Arial,sans-serif;"
        "overflow:hidden;-webkit-font-smoothing:antialiased;"
        "background:#0b1120;color:#f1f5f9;}"
        "</style></head><body>"
        f"{body}"
        "</body></html>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  COVER slide  (slide 1 of carousel)
# ──────────────────────────────────────────────────────────────────────────────

def _cover_slide_html(cats: list[str], total: int) -> str:
    pills = "".join(
        f'<span style="display:inline-block;background:rgba(255,255,255,0.06);'
        f'border:1px solid rgba(255,255,255,0.12);color:#cbd5e1;'
        f'font-size:{CATEGORY_SIZE}px;font-weight:600;padding:10px 24px;'
        f'border-radius:30px;margin:5px;">'
        f'{CATEGORY_ICONS.get(c, "📌")} {_esc(c)}</span>'
        for c in cats
    )

    return _base_page(f"""
    <div style="width:{WIDTH}px;height:{HEIGHT}px;padding:60px 56px;
                display:flex;flex-direction:column;position:relative;
                background:linear-gradient(155deg,#0b1120 0%,#0f1d3a 35%,#162a54 70%,#1e3a6e 100%);">
      <!-- decorative glows -->
      <div style="position:absolute;top:-100px;right:-60px;width:400px;height:400px;
                  border-radius:50%;background:radial-gradient(circle,rgba(59,130,246,0.12),transparent 70%);"></div>
      <div style="position:absolute;bottom:-80px;left:-40px;width:350px;height:350px;
                  border-radius:50%;background:radial-gradient(circle,rgba(139,92,246,0.10),transparent 70%);"></div>
      <!-- top accent bar -->
      <div style="position:absolute;top:0;left:0;right:0;height:6px;
                  background:linear-gradient(90deg,#3b82f6,#8b5cf6,#ec4899);"></div>

      <!-- brand -->
      <div style="display:flex;align-items:center;gap:12px;">
        <div style="width:12px;height:12px;border-radius:50%;background:#3b82f6;"></div>
        <span style="font-size:{META_SIZE}px;font-weight:700;letter-spacing:3px;
                     text-transform:uppercase;color:rgba(148,163,184,0.7);">24H NEWS EXPLORER</span>
      </div>

      <!-- centered content -->
      <div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
                  text-align:center;gap:20px;">
        <div style="font-size:90px;margin-bottom:8px;">📰</div>
        <div style="font-size:{HOOK_SIZE}px;font-weight:900;line-height:1.1;
                    letter-spacing:-2px;
                    background:linear-gradient(135deg,#fff 30%,#93c5fd);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
          Daily News<br>Roundup
        </div>
        <div style="font-size:{SOURCE_SIZE}px;color:#94a3b8;margin-top:4px;">{_timestamp_label()}</div>

        <!-- stats -->
        <div style="display:flex;justify-content:center;gap:56px;margin:28px 0;">
          <div style="text-align:center;">
            <div style="font-size:64px;font-weight:900;color:#60a5fa;">{total}</div>
            <div style="font-size:20px;color:#64748b;text-transform:uppercase;
                        letter-spacing:2px;font-weight:700;">Articles</div>
          </div>
          <div style="text-align:center;">
            <div style="font-size:64px;font-weight:900;color:#a78bfa;">{len(cats)}</div>
            <div style="font-size:20px;color:#64748b;text-transform:uppercase;
                        letter-spacing:2px;font-weight:700;">Categories</div>
          </div>
        </div>

        <!-- category pills -->
        <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:6px;
                    max-width:92%;margin:0 auto;">
          {pills}
        </div>
      </div>

      <!-- footer -->
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:{META_SIZE}px;color:rgba(148,163,184,0.4);letter-spacing:1px;">
          Powered by Claude AI</span>
        <div style="display:flex;gap:8px;">
          <div style="width:10px;height:10px;border-radius:50%;background:#3b82f6;"></div>
          <div style="width:10px;height:10px;border-radius:50%;background:#8b5cf6;"></div>
          <div style="width:10px;height:10px;border-radius:50%;background:#ec4899;"></div>
        </div>
      </div>
    </div>""")


# ──────────────────────────────────────────────────────────────────────────────
#  CATEGORY SUMMARY slide
# ──────────────────────────────────────────────────────────────────────────────

def _category_summary_html(cat: str, articles: list[dict]) -> str:
    icon = CATEGORY_ICONS.get(cat, "📌")
    accent = CATEGORY_ACCENTS.get(cat, "#3b82f6")
    shown = articles[:5]

    rows = ""
    for i, art in enumerate(shown, 1):
        t = _esc(_truncate(art.get("title", ""), 80))
        s = _esc(art.get("source", ""))
        v = _verify_badge(art.get("verified_score", -1), art.get("verified_status", "skipped"))
        rows += f"""
        <div style="display:flex;align-items:flex-start;gap:20px;
                    background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);
                    border-radius:18px;padding:24px 28px;border-left:5px solid {accent};">
          <div style="flex-shrink:0;width:52px;height:52px;
                      background:{accent}22;border:2px solid {accent}44;border-radius:14px;
                      display:flex;align-items:center;justify-content:center;
                      font-size:24px;font-weight:900;color:{accent};">{i}</div>
          <div style="flex:1;min-width:0;">
            <div style="font-size:32px;font-weight:700;line-height:1.35;
                        color:#f1f5f9;margin-bottom:10px;">{t}</div>
            <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
              <span style="font-size:{SOURCE_SIZE - 4}px;font-weight:600;color:#94a3b8;">{s}</span>
              {v}
            </div>
          </div>
        </div>"""

    return _base_page(f"""
    <div style="width:{WIDTH}px;height:{HEIGHT}px;padding:60px 56px;
                display:flex;flex-direction:column;position:relative;
                background:linear-gradient(155deg,#0b1120 0%,#0f1d3a 35%,#162a54 70%,#1e3a6e 100%);">
      <!-- decorative glow -->
      <div style="position:absolute;top:-60px;right:-40px;width:320px;height:320px;
                  border-radius:50%;background:radial-gradient(circle,{accent}18,transparent 70%);"></div>
      <!-- top accent -->
      <div style="position:absolute;top:0;left:0;right:0;height:6px;
                  background:linear-gradient(90deg,{accent},transparent);"></div>

      <!-- header -->
      <div style="margin-bottom:36px;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px;">
          <div style="width:12px;height:12px;border-radius:50%;background:{accent};"></div>
          <span style="font-size:{META_SIZE}px;font-weight:700;letter-spacing:3px;
                       text-transform:uppercase;color:rgba(148,163,184,0.6);">24H NEWS EXPLORER</span>
        </div>
        <div style="display:flex;align-items:center;gap:18px;">
          <span style="font-size:44px;font-weight:900;color:#f1f5f9;letter-spacing:-0.5px;">
            {icon} {_esc(cat)}</span>
          <span style="font-size:22px;padding:7px 18px;border-radius:24px;
                       background:{accent}22;border:1.5px solid {accent}44;
                       color:{accent};font-weight:700;">
            {len(shown)} {'story' if len(shown)==1 else 'stories'}</span>
        </div>
      </div>

      <!-- article rows -->
      <div style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:16px;">
        {rows}
      </div>

      <!-- footer -->
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:28px;">
        <span style="font-size:{META_SIZE}px;color:#64748b;">🕐 {_timestamp_label()}</span>
        <span style="font-size:{META_SIZE - 4}px;color:rgba(148,163,184,0.35);
                     letter-spacing:1px;">Powered by Claude AI</span>
      </div>
    </div>""")


# ──────────────────────────────────────────────────────────────────────────────
#  ARTICLE slide  (hook title + ~90-word body)
# ──────────────────────────────────────────────────────────────────────────────

def _article_slide_html(article: dict, cat: str) -> str:
    icon = CATEGORY_ICONS.get(cat, "📌")
    accent = CATEGORY_ACCENTS.get(cat, "#3b82f6")

    title   = _esc(article.get("title", ""))
    source  = _esc(article.get("source", ""))
    summary = _esc(article.get("summary", ""))

    v = _verify_badge(
        article.get("verified_score", -1),
        article.get("verified_status", "skipped"),
    )

    return _base_page(f"""
    <div style="width:{WIDTH}px;height:{HEIGHT}px;padding:60px 56px;
                display:flex;flex-direction:column;position:relative;
                background:linear-gradient(155deg,#0b1120 0%,#0f1d3a 35%,#162a54 70%,#1e3a6e 100%);">
      <!-- decorative glows -->
      <div style="position:absolute;top:-60px;right:-50px;width:360px;height:360px;
                  border-radius:50%;background:radial-gradient(circle,{accent}15,transparent 70%);"></div>
      <div style="position:absolute;bottom:80px;left:-80px;width:280px;height:280px;
                  border-radius:50%;background:radial-gradient(circle,rgba(139,92,246,0.08),transparent 70%);"></div>
      <!-- top accent -->
      <div style="position:absolute;top:0;left:0;right:0;height:6px;
                  background:linear-gradient(90deg,{accent},transparent);"></div>

      <!-- brand + category -->
      <div style="margin-bottom:16px;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
          <div style="width:12px;height:12px;border-radius:50%;background:{accent};"></div>
          <span style="font-size:{META_SIZE}px;font-weight:700;letter-spacing:3px;
                       text-transform:uppercase;color:rgba(148,163,184,0.6);">24H NEWS EXPLORER</span>
        </div>
        <span style="display:inline-block;font-size:{CATEGORY_SIZE}px;font-weight:700;
                     padding:8px 22px;border-radius:28px;
                     background:{accent}15;border:1.5px solid {accent}40;
                     color:{accent};">{icon} {_esc(cat)}</span>
      </div>

      <!-- HOOK / TITLE  — the scroll-stopper -->
      <div style="margin:auto 0 0 0;padding-bottom:8px;">
        <div style="font-size:{HOOK_SIZE}px;font-weight:900;line-height:1.15;
                    letter-spacing:-1.5px;color:#f8fafc;
                    max-width:96%;">{title}</div>
      </div>

      <!-- source + badge -->
      <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;
                  padding:20px 0;border-top:2px solid rgba(255,255,255,0.06);">
        <div style="display:flex;align-items:center;gap:10px;">
          <div style="width:8px;height:8px;border-radius:50%;background:{accent};"></div>
          <span style="font-size:{SOURCE_SIZE}px;font-weight:700;color:#cbd5e1;">{source}</span>
        </div>
        {v}
      </div>

      <!-- BODY CONTENT — ~90 words, comfortable mobile reading -->
      <div style="flex:1;display:flex;align-items:flex-start;">
        <div style="font-size:{BODY_SIZE}px;font-weight:400;line-height:1.7;
                    color:#94a3b8;max-width:96%;">{summary}</div>
      </div>

      <!-- footer -->
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:20px;">
        <span style="font-size:{META_SIZE}px;color:#64748b;">🕐 {_timestamp_label()}</span>
        <div style="display:flex;align-items:center;gap:8px;">
          <div style="width:10px;height:10px;border-radius:50%;background:{accent};"></div>
          <span style="font-size:{META_SIZE - 4}px;color:rgba(148,163,184,0.35);
                       letter-spacing:1px;">Powered by Claude AI</span>
        </div>
      </div>
    </div>""")


# ──────────────────────────────────────────────────────────────────────────────
#  Screenshot engine (Playwright)
# ──────────────────────────────────────────────────────────────────────────────

def _find_chromium_executable() -> str | None:
    cache_dir = Path.home() / ".cache" / "ms-playwright"
    if not cache_dir.exists():
        return None
    for pattern in ("chromium_headless_shell-*/chrome-linux/headless_shell",
                    "chromium-*/chrome-linux/chrome"):
        matches = sorted(cache_dir.glob(pattern))
        if matches:
            return str(matches[-1])
    return None


async def _screenshot_html(html_content: str) -> bytes:
    from playwright.async_api import async_playwright
    exe = _find_chromium_executable()
    kw: dict = {}
    if exe:
        kw["executable_path"] = exe
    async with async_playwright() as p:
        browser = await p.chromium.launch(**kw)
        page = await browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        await page.set_content(html_content, wait_until="networkidle")
        png = await page.screenshot(type="png")
        await browser.close()
    return png


def render_slide(html_content: str) -> bytes:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _screenshot_html(html_content))
            return future.result(timeout=30)
    else:
        return asyncio.run(_screenshot_html(html_content))


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

def generate_cover_slide(cats: list[str], total: int) -> bytes:
    return render_slide(_cover_slide_html(cats, total))


def generate_category_slide(cat: str, articles: list[dict]) -> bytes:
    return render_slide(_category_summary_html(cat, articles))


def generate_article_slide(article: dict, cat: str) -> bytes:
    return render_slide(_article_slide_html(article, cat))


def generate_all_slides(
    raw_articles: dict[str, list[dict]],
    mode: Literal["summary", "individual", "both"] = "summary",
) -> list[tuple[str, bytes]]:
    slides: list[tuple[str, bytes]] = []
    all_cats = [c for c in raw_articles if raw_articles[c]]
    total = sum(len(a) for a in raw_articles.values())

    if mode in ("summary", "both"):
        slides.append(("00_cover.png", generate_cover_slide(all_cats, total)))

    if mode in ("summary", "both"):
        for i, (cat, arts) in enumerate(raw_articles.items(), 1):
            if not arts:
                continue
            safe = cat.lower().replace(" ", "_")
            slides.append((f"{i:02d}_{safe}_summary.png",
                           generate_category_slide(cat, arts)))

    if mode in ("individual", "both"):
        idx = len(slides)
        for cat, arts in raw_articles.items():
            for art in arts:
                idx += 1
                safe = art.get("title", "article")[:40].replace(" ", "_")
                safe = "".join(c for c in safe if c.isalnum() or c == "_")
                slides.append((f"{idx:02d}_{safe}.png",
                               generate_article_slide(art, cat)))

    return slides
