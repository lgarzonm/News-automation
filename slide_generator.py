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
from datetime import datetime, timezone, timedelta
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


def _verify_badge(score: int, status: str, sz: int = 18) -> str:
    if status == "skipped" or score < 0:
        return ""
    if score >= VERIFY_HIGH:
        bg, border, fg, icon = "rgba(22,163,74,0.2)", "#22c55e", "#4ade80", "✓"
    elif score >= 45:
        bg, border, fg, icon = "rgba(217,119,6,0.2)", "#f59e0b", "#fbbf24", "~"
    else:
        bg, border, fg, icon = "rgba(220,38,38,0.2)", "#ef4444", "#f87171", "✗"
    return (
        f'<span style="display:inline-flex;align-items:center;gap:5px;'
        f'background:{bg};border:1.5px solid {border};color:{fg};'
        f'font-size:{sz}px;font-weight:700;padding:4px 14px;'
        f'border-radius:20px;">{icon} {score}%</span>'
    )


def _base_page(body: str, w: int, h: int) -> str:
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        "<style>"
        "*{margin:0;padding:0;box-sizing:border-box;}"
        f"body{{width:{w}px;height:{h}px;"
        "font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;"
        "overflow:hidden;-webkit-font-smoothing:antialiased;"
        "background:#0b1120;color:#f1f5f9;}"
        "</style></head><body>"
        f"{body}"
        "</body></html>"
    )


# ──────────────────────────────────────────────────────────────────────────────
#  COVER slide
# ──────────────────────────────────────────────────────────────────────────────

def _cover_slide_html(cats: list[str], total: int, fmt: SlideFormat) -> str:
    w, h = DIMENSIONS[fmt]
    S = fmt == "story"
    L = fmt == "linkedin"

    title_sz = 62 if S else (42 if L else 56)
    sub_sz   = 24 if S else (18 if L else 22)
    stat_sz  = 52 if S else (36 if L else 46)
    stat_lb  = 16 if S else (13 if L else 15)
    pill_sz  = 17 if S else (14 if L else 16)
    pill_pad = "8px 20px" if S else ("5px 14px" if L else "7px 18px")
    pad      = "60px 50px" if S else ("36px 50px" if L else "56px")

    pills = "".join(
        f'<span style="display:inline-block;background:rgba(255,255,255,0.06);'
        f'border:1px solid rgba(255,255,255,0.12);color:#cbd5e1;'
        f'font-size:{pill_sz}px;font-weight:600;padding:{pill_pad};'
        f'border-radius:30px;margin:4px;">'
        f'{CATEGORY_ICONS.get(c, "📌")} {_esc(c)}</span>'
        for c in cats
    )

    return _base_page(f"""
    <div style="width:{w}px;height:{h}px;padding:{pad};
                display:flex;flex-direction:column;position:relative;
                background:linear-gradient(155deg,#0b1120 0%,#0f1d3a 35%,#162a54 70%,#1e3a6e 100%);">
      <div style="position:absolute;top:-120px;right:-80px;width:400px;height:400px;
                  border-radius:50%;background:radial-gradient(circle,rgba(59,130,246,0.12),transparent 70%);"></div>
      <div style="position:absolute;bottom:-100px;left:-60px;width:350px;height:350px;
                  border-radius:50%;background:radial-gradient(circle,rgba(139,92,246,0.10),transparent 70%);"></div>
      <div style="position:absolute;top:0;left:0;right:0;height:5px;
                  background:linear-gradient(90deg,#3b82f6,#8b5cf6,#ec4899);"></div>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:auto;">
        <div style="width:10px;height:10px;border-radius:50%;background:#3b82f6;"></div>
        <span style="font-size:15px;font-weight:700;letter-spacing:3px;
                     text-transform:uppercase;color:rgba(148,163,184,0.7);">24H NEWS EXPLORER</span>
      </div>
      <div style="text-align:center;margin:auto 0;">
        <div style="font-size:80px;margin-bottom:24px;">📰</div>
        <div style="font-size:{title_sz}px;font-weight:800;line-height:1.15;
                    letter-spacing:-1.5px;margin-bottom:16px;
                    background:linear-gradient(135deg,#fff,#93c5fd);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
          Daily News<br>Roundup
        </div>
        <div style="font-size:{sub_sz}px;color:#94a3b8;margin-bottom:36px;">{_timestamp_label()}</div>
        <div style="display:flex;justify-content:center;gap:48px;margin-bottom:40px;">
          <div style="text-align:center;">
            <div style="font-size:{stat_sz}px;font-weight:800;color:#60a5fa;">{total}</div>
            <div style="font-size:{stat_lb}px;color:#64748b;text-transform:uppercase;
                        letter-spacing:1.5px;font-weight:600;">Articles</div>
          </div>
          <div style="text-align:center;">
            <div style="font-size:{stat_sz}px;font-weight:800;color:#a78bfa;">{len(cats)}</div>
            <div style="font-size:{stat_lb}px;color:#64748b;text-transform:uppercase;
                        letter-spacing:1.5px;font-weight:600;">Categories</div>
          </div>
        </div>
        <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:4px;max-width:90%;margin:0 auto;">
          {pills}
        </div>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:auto;">
        <span style="font-size:13px;color:rgba(148,163,184,0.4);letter-spacing:1px;">Powered by Claude AI</span>
        <div style="display:flex;gap:6px;">
          <div style="width:8px;height:8px;border-radius:50%;background:#3b82f6;"></div>
          <div style="width:8px;height:8px;border-radius:50%;background:#8b5cf6;"></div>
          <div style="width:8px;height:8px;border-radius:50%;background:#ec4899;"></div>
        </div>
      </div>
    </div>""", w, h)


# ──────────────────────────────────────────────────────────────────────────────
#  CATEGORY SUMMARY slide
# ──────────────────────────────────────────────────────────────────────────────

def _category_summary_html(cat: str, articles: list[dict], fmt: SlideFormat) -> str:
    w, h = DIMENSIONS[fmt]
    icon = CATEGORY_ICONS.get(cat, "📌")
    accent = CATEGORY_ACCENTS.get(cat, "#3b82f6")
    S = fmt == "story"
    L = fmt == "linkedin"

    max_n    = 4 if not S else 6
    if L:
        max_n = 3
    shown    = articles[:max_n]
    cat_sz   = 34 if S else (22 if L else 28)
    title_sz = 26 if S else (19 if L else 23)
    src_sz   = 16 if S else (13 if L else 15)
    num_w    = 44 if S else (32 if L else 40)
    num_sz   = 20 if S else (15 if L else 18)
    badge_sz = 15 if S else (12 if L else 14)
    row_pad  = "22px 26px" if S else ("14px 18px" if L else "18px 24px")
    row_gap  = "14px" if S else ("8px" if L else "12px")
    pad      = "56px 50px" if S else ("32px 44px" if L else "50px")

    rows = ""
    for i, art in enumerate(shown, 1):
        t = _esc(_truncate(art.get("title", ""), 90))
        s = _esc(art.get("source", ""))
        v = _verify_badge(art.get("verified_score", -1), art.get("verified_status", "skipped"), badge_sz)
        rows += f"""
        <div style="display:flex;align-items:flex-start;gap:18px;
                    background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);
                    border-radius:16px;padding:{row_pad};border-left:4px solid {accent};">
          <div style="flex-shrink:0;width:{num_w}px;height:{num_w}px;
                      background:{accent}22;border:2px solid {accent}44;border-radius:12px;
                      display:flex;align-items:center;justify-content:center;
                      font-size:{num_sz}px;font-weight:800;color:{accent};">{i}</div>
          <div style="flex:1;min-width:0;">
            <div style="font-size:{title_sz}px;font-weight:700;line-height:1.35;
                        color:#f1f5f9;margin-bottom:8px;">{t}</div>
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
              <span style="font-size:{src_sz}px;font-weight:600;color:#94a3b8;">{s}</span>
              {v}
            </div>
          </div>
        </div>"""

    return _base_page(f"""
    <div style="width:{w}px;height:{h}px;padding:{pad};
                display:flex;flex-direction:column;position:relative;
                background:linear-gradient(155deg,#0b1120 0%,#0f1d3a 35%,#162a54 70%,#1e3a6e 100%);">
      <div style="position:absolute;top:-60px;right:-40px;width:300px;height:300px;
                  border-radius:50%;background:radial-gradient(circle,{accent}18,transparent 70%);"></div>
      <div style="position:absolute;top:0;left:0;right:0;height:5px;
                  background:linear-gradient(90deg,{accent},transparent);"></div>
      <div style="margin-bottom:{'32px' if S else ('16px' if L else '28px')};">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">
          <div style="width:10px;height:10px;border-radius:50%;background:{accent};"></div>
          <span style="font-size:14px;font-weight:700;letter-spacing:3px;
                       text-transform:uppercase;color:rgba(148,163,184,0.6);">24H NEWS EXPLORER</span>
        </div>
        <div style="display:flex;align-items:center;gap:16px;">
          <span style="font-size:{cat_sz}px;font-weight:800;color:#f1f5f9;letter-spacing:-0.5px;">
            {icon} {_esc(cat)}</span>
          <span style="font-size:15px;padding:5px 14px;border-radius:20px;
                       background:{accent}22;border:1px solid {accent}44;
                       color:{accent};font-weight:700;">{len(shown)} {'story' if len(shown)==1 else 'stories'}</span>
        </div>
      </div>
      <div style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:{row_gap};">
        {rows}
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;
                  margin-top:{'28px' if S else ('12px' if L else '20px')};">
        <span style="font-size:14px;color:#64748b;">🕐 {_timestamp_label()}</span>
        <span style="font-size:12px;color:rgba(148,163,184,0.35);letter-spacing:1px;">Powered by Claude AI</span>
      </div>
    </div>""", w, h)


# ──────────────────────────────────────────────────────────────────────────────
#  SINGLE ARTICLE slide
# ──────────────────────────────────────────────────────────────────────────────

def _single_article_html(article: dict, cat: str, fmt: SlideFormat) -> str:
    w, h = DIMENSIONS[fmt]
    icon = CATEGORY_ICONS.get(cat, "📌")
    accent = CATEGORY_ACCENTS.get(cat, "#3b82f6")
    S = fmt == "story"
    L = fmt == "linkedin"

    title   = _esc(article.get("title", ""))
    source  = _esc(article.get("source", ""))
    summary = _esc(_truncate(article.get("summary", ""), 300))

    title_sz   = 42 if S else (30 if L else 38)
    summary_sz = 22 if S else (17 if L else 20)
    src_sz     = 20 if S else (16 if L else 18)
    cat_lb_sz  = 16 if S else (13 if L else 15)
    badge_sz   = 20 if S else (15 if L else 17)
    pad        = "60px 54px" if S else ("36px 48px" if L else "54px")
    quote_sz   = 120 if S else (80 if L else 100)

    v = _verify_badge(article.get("verified_score", -1), article.get("verified_status", "skipped"), badge_sz)

    return _base_page(f"""
    <div style="width:{w}px;height:{h}px;padding:{pad};
                display:flex;flex-direction:column;position:relative;
                background:linear-gradient(155deg,#0b1120 0%,#0f1d3a 35%,#162a54 70%,#1e3a6e 100%);">
      <div style="position:absolute;top:-80px;right:-60px;width:350px;height:350px;
                  border-radius:50%;background:radial-gradient(circle,{accent}15,transparent 70%);"></div>
      <div style="position:absolute;bottom:100px;left:-100px;width:250px;height:250px;
                  border-radius:50%;background:radial-gradient(circle,rgba(139,92,246,0.08),transparent 70%);"></div>
      <div style="position:absolute;top:0;left:0;right:0;height:5px;
                  background:linear-gradient(90deg,{accent},transparent);"></div>
      <div style="position:absolute;top:{'220px' if S else ('60px' if L else '140px')};
                  right:50px;font-size:{quote_sz}px;color:rgba(255,255,255,0.03);
                  font-weight:900;line-height:1;">&#10077;</div>
      <div style="margin-bottom:auto;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
          <div style="width:10px;height:10px;border-radius:50%;background:{accent};"></div>
          <span style="font-size:14px;font-weight:700;letter-spacing:3px;
                       text-transform:uppercase;color:rgba(148,163,184,0.6);">24H NEWS EXPLORER</span>
        </div>
        <span style="display:inline-block;font-size:{cat_lb_sz}px;font-weight:700;
                     padding:6px 18px;border-radius:24px;
                     background:{accent}18;border:1.5px solid {accent}40;
                     color:{accent};">{icon} {_esc(cat)}</span>
      </div>
      <div style="margin:auto 0;max-width:92%;">
        <div style="font-size:{title_sz}px;font-weight:800;line-height:1.25;
                    letter-spacing:-0.8px;color:#f8fafc;margin-bottom:24px;">{title}</div>
        <div style="display:flex;align-items:center;gap:14px;margin-bottom:28px;flex-wrap:wrap;">
          <div style="display:flex;align-items:center;gap:8px;">
            <div style="width:6px;height:6px;border-radius:50%;background:{accent};"></div>
            <span style="font-size:{src_sz}px;font-weight:700;color:#cbd5e1;">{source}</span>
          </div>
          {v}
        </div>
        <div style="width:60px;height:4px;background:{accent};border-radius:2px;margin-bottom:24px;"></div>
        <div style="font-size:{summary_sz}px;line-height:1.65;color:#94a3b8;">{summary}</div>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:auto;">
        <span style="font-size:14px;color:#64748b;">🕐 {_timestamp_label()}</span>
        <div style="display:flex;align-items:center;gap:8px;">
          <div style="width:8px;height:8px;border-radius:50%;background:{accent};"></div>
          <span style="font-size:12px;color:rgba(148,163,184,0.35);letter-spacing:1px;">Powered by Claude AI</span>
        </div>
      </div>
    </div>""", w, h)


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


async def _screenshot_html(html_content: str, width: int, height: int) -> bytes:
    from playwright.async_api import async_playwright
    exe = _find_chromium_executable()
    kw: dict = {}
    if exe:
        kw["executable_path"] = exe
    async with async_playwright() as p:
        browser = await p.chromium.launch(**kw)
        page = await browser.new_page(viewport={"width": width, "height": height})
        await page.set_content(html_content, wait_until="networkidle")
        png = await page.screenshot(type="png")
        await browser.close()
    return png


def render_slide(html_content: str, width: int, height: int) -> bytes:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _screenshot_html(html_content, width, height))
            return future.result(timeout=30)
    else:
        return asyncio.run(_screenshot_html(html_content, width, height))


# ──────────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────────

def generate_cover_slide(cats: list[str], total: int, fmt: SlideFormat = "instagram") -> bytes:
    w, h = DIMENSIONS[fmt]
    return render_slide(_cover_slide_html(cats, total, fmt), w, h)


def generate_category_slide(cat: str, articles: list[dict], fmt: SlideFormat = "instagram") -> bytes:
    w, h = DIMENSIONS[fmt]
    return render_slide(_category_summary_html(cat, articles, fmt), w, h)


def generate_article_slide(article: dict, cat: str, fmt: SlideFormat = "instagram") -> bytes:
    w, h = DIMENSIONS[fmt]
    return render_slide(_single_article_html(article, cat, fmt), w, h)


def generate_all_slides(
    raw_articles: dict[str, list[dict]],
    fmt: SlideFormat = "instagram",
    mode: Literal["summary", "individual", "both"] = "summary",
) -> list[tuple[str, bytes]]:
    slides: list[tuple[str, bytes]] = []
    all_cats = [c for c in raw_articles if raw_articles[c]]
    total = sum(len(a) for a in raw_articles.values())

    if mode in ("summary", "both"):
        slides.append(("00_cover.png", generate_cover_slide(all_cats, total, fmt)))

    if mode in ("summary", "both"):
        for i, (cat, arts) in enumerate(raw_articles.items(), 1):
            if not arts:
                continue
            safe = cat.lower().replace(" ", "_")
            slides.append((f"{i:02d}_{safe}_summary.png", generate_category_slide(cat, arts, fmt)))

    if mode in ("individual", "both"):
        idx = len(slides)
        for cat, arts in raw_articles.items():
            for art in arts:
                idx += 1
                safe = art.get("title", "article")[:40].replace(" ", "_")
                safe = "".join(c for c in safe if c.isalnum() or c == "_")
                slides.append((f"{idx:02d}_{safe}.png", generate_article_slide(art, cat, fmt)))

    return slides
