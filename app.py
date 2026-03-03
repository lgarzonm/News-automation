"""
24h News Explorer
─────────────────
Uses Claude with the built-in `web_search` tool (Anthropic API).

Two-pass pipeline:
  Pass 1 – Claude searches the live web for real news (last 24 h).
  Pass 2 – A second independent Claude call re-searches and verifies
            every article before it is shown to the user.

Only ONE API key needed: your Anthropic (Claude) key.
"""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO

import anthropic
import pandas as pd
import streamlit as st

# ──────────────────────────────────────────────────────────────────────────────
#  Page config
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="📰 24h News Explorer",
    page_icon="📰",
    layout="wide",
)

# ──────────────────────────────────────────────────────────────────────────────
#  CSS  –  light / soft-grey theme  +  navy-blue accents
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Global background ── */
    .stApp { background-color: #f0f2f6; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; background-color: #f0f2f6; }

    /* ── App header ── */
    .app-header {
        background: linear-gradient(135deg, #0a1628 0%, #0d2150 50%, #1a3a6e 100%);
        border-radius: 16px; padding: 2rem 2.5rem; margin-bottom: 2rem; text-align: center;
    }
    .app-header h1 { color: #ffffff; font-size: 2.6rem; margin: 0; }
    .app-header p  { color: #b8c9e8; font-size: 1.05rem; margin-top: .5rem; }

    /* ── Metric cards ── */
    .metric-row { display: flex; gap: 1rem; margin-bottom: 1.5rem; }
    .metric-card {
        flex: 1; background: #ffffff; border: 1px solid #d0d9e8;
        border-radius: 12px; padding: 1rem 1.4rem; text-align: center;
        box-shadow: 0 1px 4px rgba(0,0,0,.06);
    }
    .metric-card .value { font-size: 2rem; font-weight: 700; color: #1a3a6e; }
    .metric-card .label { font-size: .85rem; color: #5a6a84; margin-top: .2rem; }

    /* ── News cards ── */
    .news-card {
        background: #ffffff; border: 1px solid #d0d9e8;
        border-left: 4px solid #1a3a6e; border-radius: 10px;
        padding: 1rem 1.3rem; margin-bottom: .9rem;
        box-shadow: 0 1px 4px rgba(0,0,0,.05);
    }
    .news-card:hover { border-left-color: #2e6db4; box-shadow: 0 3px 10px rgba(26,58,110,.12); }
    .news-card.verified-high   { border-left-color: #16a34a; }
    .news-card.verified-medium { border-left-color: #d97706; }
    .news-card.verified-low    { border-left-color: #dc2626; }

    .news-card .headline {
        color: #1a202c; font-size: 1rem; font-weight: 600;
        line-height: 1.45; margin: 0 0 .55rem 0;
    }
    .news-card .meta { display: flex; flex-wrap: wrap; gap: .6rem; align-items: center; }

    /* ── Badges ── */
    .badge { font-size: .72rem; padding: .2rem .6rem; border-radius: 20px; font-weight: 600; }
    .badge-source    { background: #dbeafe; color: #1e40af; }
    .badge-cat       { background: #e0e7ff; color: #3730a3; }
    .badge-time      { background: #dcfce7; color: #166534; }
    .badge-trust-yes { background: #dcfce7; color: #166534; }
    .badge-trust-no  { background: #fef3c7; color: #92400e; }

    /* ── Verification score badges ── */
    .badge-verify-high   { background: #dcfce7; color: #14532d; border: 1px solid #86efac; }
    .badge-verify-medium { background: #fef9c3; color: #713f12; border: 1px solid #fde047; }
    .badge-verify-low    { background: #fee2e2; color: #7f1d1d; border: 1px solid #fca5a5; }
    .badge-verify-skip   { background: #f1f5f9; color: #64748b; border: 1px solid #cbd5e1; }

    /* ── Verification note box ── */
    .verify-note {
        font-size: .78rem; color: #475569; background: #f8fafc;
        border: 1px solid #e2e8f0; border-radius: 6px;
        padding: .4rem .7rem; margin: .5rem 0 .4rem 0;
        font-style: italic;
    }

    /* ── Pass labels ── */
    .pass-label {
        display: inline-block; font-size: .68rem; font-weight: 700;
        padding: .15rem .55rem; border-radius: 4px; letter-spacing: .04em;
        margin-right: .4rem;
    }
    .pass-1 { background: #dbeafe; color: #1e40af; }
    .pass-2 { background: #ede9fe; color: #4c1d95; }

    .news-card a { font-size: .8rem; color: #2563eb; text-decoration: none; }
    .news-card a:hover { text-decoration: underline; }

    /* ── Section titles ── */
    .section-title {
        color: #1a3a6e; font-size: 1.3rem; font-weight: 700;
        border-bottom: 2px solid #1a3a6e; padding-bottom: .4rem; margin-bottom: 1.2rem;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] { background: #eef1f7; }
    [data-testid="stSidebar"] .stMarkdown h3 { color: #1a3a6e !important; }

    /* ── Download button ── */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #1a3a6e, #2e6db4) !important;
        color: white !important; border: none !important; border-radius: 8px !important;
        font-weight: 600 !important; padding: .55rem 1.2rem !important;
    }
    .stDownloadButton > button:hover { opacity: .85 !important; }

    /* ── Search / primary button ── */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #1a3a6e, #2e6db4) !important;
        border: none !important; color: white !important; font-weight: 700 !important;
    }
    .stButton > button[kind="primary"]:hover { opacity: .88 !important; }

    /* ── Powered-by pill ── */
    .pill-claude {
        display: inline-block;
        background: linear-gradient(135deg, #1a3a6e, #2e6db4);
        color: white; font-size: .7rem; font-weight: 700;
        padding: .2rem .8rem; border-radius: 20px; letter-spacing: .05em;
    }

    /* ── Summary ── */
    .summary-text {
        color: #374151; font-size: .875rem; line-height: 1.5;
        margin: .65rem 0 .5rem 0;
        display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
        overflow: hidden;
    }

    /* ── Slider — primary colour handled by config.toml; ── */
    /* belt-and-braces: ensure the filled track is navy, no red dot at min  */
    [data-testid="stSlider"] [data-baseweb="slider"] [class*="Track"] > div:first-child,
    [data-testid="stSlider"] [data-baseweb="slider"] > div > div > div > div:first-child {
        background-color: #1a3a6e !important;
        min-width: 0 !important;   /* collapses the dot when at minimum */
    }
    [data-testid="stSlider"] [data-baseweb="slider"] [class*="Track"] > div:last-child {
        background-color: #d0d9e8 !important;  /* unfilled portion */
    }
    /* Suppress any stray coloured element inside the tick bars */
    [data-testid="stSlider"] [data-testid="stTickBarMin"],
    [data-testid="stSlider"] [data-testid="stTickBarMax"],
    [data-testid="stSlider"] [data-testid="stTickBarMin"] *,
    [data-testid="stSlider"] [data-testid="stTickBarMax"] * {
        background: transparent !important;
        color: #1a3a6e !important;
    }

    /* ── Checkbox ── */
    /*
     * ROOT CAUSE: BaseWeb applies primaryColor as a background to the
     * <label> wrapper when the checkbox is checked/hovered. With a dark
     * navy primaryColor the entire row goes dark. Fix: force the label
     * wrapper to be ALWAYS transparent. The small checkbox box itself
     * gets its colour from config.toml primaryColor — we don't touch it.
     */
    [data-baseweb="checkbox"] label,
    [data-baseweb="checkbox"] label:hover,
    [data-baseweb="checkbox"] label:active,
    [data-baseweb="checkbox"] label:focus,
    [data-baseweb="checkbox"] label:focus-visible {
        background-color: transparent !important;
        background:       transparent !important;
    }
    /* Label text — always dark and readable regardless of check state */
    [data-testid="stCheckbox"] p,
    [data-testid="stCheckbox"] span:not([data-baseweb]) {
        color: #1a202c !important;
        -webkit-text-fill-color: #1a202c !important;
    }

    /* ── Multiselect tags → navy blue ── */
    [data-baseweb="tag"] { background-color: #1a3a6e !important; border-color: #1a3a6e !important; }
    [data-baseweb="tag"] span[data-testid="stMultiSelectTag"] { color: #ffffff !important; }
    [data-baseweb="tag"] span[role="presentation"] svg { fill: #ffffff !important; }
    [data-baseweb="select"] [data-baseweb="tag"]:focus-within { outline-color: #2e6db4 !important; }
    [data-baseweb="menu"] [aria-selected="true"] { background-color: #dbeafe !important; color: #1a3a6e !important; }
    [data-baseweb="select"] > div:focus-within {
        border-color: #2e6db4 !important;
        box-shadow: 0 0 0 2px rgba(46,109,180,.25) !important;
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────────────────────
CATEGORY_ICONS: dict[str, str] = {
    "Stocks":              "📈",
    "Fiats":               "💱",
    "Indexes":             "📊",
    "Regional":            "🌏",
    "Country Credit":      "🏦",
    "Alternative Lending": "🤝",
    "Fintech":             "💳",
    "Start-up":            "🚀",
    "Sustainable Finance": "🌿",
    "Marketing":           "📣",
    "Entertainment":       "🎬",
}

TRUSTED_SOURCES: dict[str, list[str]] = {
    "Stocks": [
        "Bloomberg", "Reuters", "Financial Times", "Wall Street Journal",
        "CNBC", "Nikkei Asia", "South China Morning Post", "The Straits Times",
        "Business Times Singapore", "Business Times", "Seeking Alpha",
        "Investor's Business Daily", "Barron's", "MarketWatch", "Yahoo Finance",
    ],
    "Fiats": [
        "Bloomberg", "Reuters", "Financial Times", "Wall Street Journal",
        "CNBC", "FX Street", "Investopedia", "Nikkei Asia",
        "South China Morning Post", "MAS (Monetary Authority of Singapore)",
        "Barron's", "MarketWatch", "FX Empire",
    ],
    "Indexes": [
        "Bloomberg", "Reuters", "Financial Times", "CNBC",
        "Nikkei Asia", "South China Morning Post", "Business Times Singapore",
        "The Straits Times", "Morningstar", "S&P Global",
        "MarketWatch", "Barron's", "Yahoo Finance",
    ],
    "Regional": [
        "Nikkei Asia", "South China Morning Post", "The Straits Times",
        "Bangkok Post", "The Jakarta Post", "Philippine Daily Inquirer",
        "Vietnam News", "Reuters", "Bloomberg", "Channel NewsAsia (CNA)",
        "The Guardian", "BBC", "Associated Press", "Al Jazeera",
        "Financial Times", "Wall Street Journal",
    ],
    "Country Credit": [
        "Bloomberg", "Reuters", "Financial Times", "Moody's",
        "S&P Global", "Fitch Ratings", "The Straits Times",
        "Nikkei Asia", "South China Morning Post", "Asian Development Bank",
        "Vietnam News", "Bangkok Post", "The Jakarta Post",
    ],
    "Alternative Lending": [
        "Bloomberg", "Reuters", "Financial Times", "Fintech News Singapore", "e27",
        "Deal Street Asia", "Tech in Asia", "The Business Times",
        "Crowdfund Insider", "Lending Times", "AltFi",
        "Private Debt Investor", "Institutional Investor",
    ],
    "Fintech": [
        "Fintech News Singapore", "e27", "Deal Street Asia", "Tech in Asia",
        "TechCrunch", "Bloomberg", "Reuters", "The Business Times",
        "Channel NewsAsia (CNA)", "Fintechnews.sg",
        "Fintech Futures", "Fintech Global", "Finextra", "Payments Dive",
    ],
    "Start-up": [
        "e27", "Tech in Asia", "Deal Street Asia", "TechCrunch",
        "Bloomberg", "Reuters", "Channel NewsAsia (CNA)",
        "The Straits Times", "KrASIA", "Vulcan Post",
        "Yahoo Finance", "Forbes", "Business Insider",
    ],
    "Sustainable Finance": [
        "Bloomberg Green", "Reuters", "Financial Times", "The Straits Times",
        "Channel NewsAsia (CNA)", "Eco-Business", "MAS (Monetary Authority of Singapore)",
        "Asian Development Bank", "Carbon Brief", "GreenBiz",
        "Yahoo Finance", "CNBC", "Wall Street Journal", "S&P Global",
    ],
    "Marketing": [
        "Campaign Asia", "Marketing Interactive", "Mumbrella Asia",
        "The Drum", "Adweek", "South China Morning Post",
        "The Straits Times", "Channel NewsAsia (CNA)",
        "Marketing Week", "Ad Age", "Campaign ME", "Campaign",
    ],
    "Entertainment": [
        "The Straits Times", "CNA", "TODAY", "8Days", "Mothership",
        "Time Out Singapore", "Visit Singapore", "The Smart Local",
        "Variety Asia", "South China Morning Post",
        "Channel NewsAsia (CNA)", "Billboard", "Tatler Asia",
        "Nikkei Asia", "Vulcan Post", "Time Out", "Time Out Singapore",
        "Today Online", "Bandwagon",
    ],
}

CATEGORY_SEARCH_QUERIES: dict[str, str] = {
    "Stocks":              "global stock market equities Wall Street Asia APAC news today",
    "Fiats":               "forex currency exchange rates USD EUR JPY SGD AUD news today",
    "Indexes":             "stock market index S&P 500 Dow Nasdaq Nikkei Hang Seng MSCI news today",
    "Regional":            "global geopolitical macro economy Asia APAC Middle East news today",
    "Country Credit":      "sovereign credit rating government bonds debt Asia APAC news today",
    "Alternative Lending": "alternative lending private credit P2P non-bank financing news today",
    "Fintech":             "fintech financial technology payments digital banking startup news today",
    "Start-up":            "startup funding venture capital seed round Series A B news today",
    "Sustainable Finance": "sustainable finance ESG green bonds climate infrastructure news today global",
    "Marketing":           "marketing advertising brand campaigns media news today",
    "Entertainment":       "Singapore entertainment events concerts movies music theatre arts news today",
}

CATEGORY_DEFAULT_KEYWORDS: dict[str, list[str]] = {
    "Stocks": [
        "earnings", "profits", "stock rally", "stock drop", "guidance",
        "dividends", "buyback", "IPO", "valuation", "volatility",
    ],
    "Fiats": [
        "dollar", "euro", "DXY", "currency", "FX",
        "exchange rate", "devaluation", "central bank", "rate hike", "inflation",
    ],
    "Indexes": [
        "S&P 500", "Nasdaq", "Dow", "Nikkei", "Hang Seng",
        "MSCI", "market rally", "market selloff", "futures", "ETF",
    ],
    "Regional": [
        "ASEAN", "Southeast Asia", "APAC", "Singapore economy", "Indonesia economy",
        "China stimulus", "Asia growth", "trade", "geopolitical", "conflict",
        "Middle East", "oil prices", "sanctions", "elections", "policy",
    ],
    "Country Credit": [
        "sovereign debt", "government bonds", "credit rating", "Moody's", "S&P rating",
        "Fitch", "default risk", "debt crisis", "fiscal deficit", "bond yields",
    ],
    "Alternative Lending": [
        "private credit", "alternative lending", "SME loans", "non-bank lending", "asset-backed",
        "loan portfolio", "credit fund", "lending platform", "yield", "structured finance",
    ],
    "Fintech": [
        "fintech", "digital bank", "e-wallet", "payments", "BNPL",
        "digital lending", "open banking", "blockchain", "crypto", "financial inclusion",
    ],
    "Start-up": [
        "startup funding", "venture capital", "Series A", "Series B", "unicorn",
        "valuation", "seed round", "acquisition", "IPO", "founder",
    ],
    "Sustainable Finance": [
        "green bond", "ESG", "sustainability", "climate finance", "carbon",
        "net zero", "energy transition", "impact investing", "renewable energy", "climate policy",
        "green infrastructure", "sustainable capital", "climate bond", "transition finance",
    ],
    "Marketing": [
        "branding", "advertising", "digital marketing", "campaign", "consumer",
        "product launch", "social media", "growth", "strategy", "market share",
    ],
    "Entertainment": [
        "Singapore concert", "Singapore festival", "Singapore arts", "Singapore theatre",
        "Singapore premiere", "Singapore exhibition", "local artist", "Singapore music",
        "concert", "festival", "movie", "streaming", "art exhibition",
        "theatre", "music", "K-pop", "anime", "gaming",
        "Singapore events", "things to do", "weekend events",
    ],
}

CATEGORY_GEO_FOCUS: dict[str, str] = {
    "Stocks": (
        "Coverage should be global (US, Europe, Asia), with special attention to "
        "Asian and APAC equity markets."
    ),
    "Fiats": (
        "Coverage should be global, focusing on major currency pairs as well as "
        "Asian currencies (SGD, JPY, CNY, KRW, INR, AUD, HKD, MYR, IDR, THB)."
    ),
    "Indexes": (
        "Prioritise Asian and APAC indexes: STI (Singapore), Nikkei 225, Hang Seng, "
        "ASX 200, KOSPI, CSI 300, MSCI Asia. Include global benchmarks (S&P 500, FTSE) "
        "only for context."
    ),
    "Regional": (
        "PRIMARY focus: Asia, APAC, and Southeast Asia (SEA) — Singapore, Malaysia, "
        "Indonesia, Thailand, Vietnam, Philippines, Hong Kong, China, Japan, South Korea, "
        "Australia. Fill most slots with Asia/SEA stories. "
        "EXCEPTION: if a global event outside Asia is of exceptional magnitude — "
        "e.g. a major military conflict, a US-Iran escalation, a G7 policy shock, "
        "an oil-price spike — that is clearly moving global markets or dominating "
        "front pages worldwide, include it (max 1-2 such stories). "
        "Do NOT include routine non-Asia stories just because they are geopolitical."
    ),
    "Country Credit": (
        "Focus on sovereign and quasi-sovereign credit for Asian and APAC countries: "
        "Singapore, China, Japan, South Korea, India, Indonesia, Malaysia, Thailand, "
        "Philippines, Vietnam, Hong Kong, Australia, New Zealand."
    ),
    "Alternative Lending": (
        "Focus on alternative lending, P2P finance, and digital credit in Asia, APAC "
        "and SEA — especially Singapore, Indonesia, Malaysia, Thailand, Philippines, "
        "Vietnam and China."
    ),
    "Fintech": (
        "Focus on fintech, digital banking, payments, crypto-regulation and wealthtech "
        "in Asia, APAC and SEA — especially Singapore, Hong Kong, Indonesia, Malaysia, "
        "Thailand, the Philippines, Vietnam, China, Japan and South Korea."
    ),
    "Start-up": (
        "Focus on startup ecosystem news in Asia, APAC and SEA — especially "
        "Singapore, Indonesia, Malaysia, Thailand, Vietnam, Philippines, India, "
        "Hong Kong and China."
    ),
    "Sustainable Finance": (
        "Coverage should be global — include significant sustainable finance, ESG, "
        "green bonds, climate infrastructure, and transition finance news from anywhere "
        "in the world. Give priority to Asia, APAC and SEA stories (Singapore MAS Green "
        "Finance Action Plan, ASEAN Taxonomy, regional net-zero initiatives), but do NOT "
        "exclude major global deals, fund raises, or policy announcements from the US, "
        "Europe, or other regions."
    ),
    "Marketing": (
        "Focus on marketing, advertising, branding, digital marketing and media campaigns "
        "globally, with priority on Asia, APAC, SEA and Middle East — especially Singapore, "
        "Malaysia, Indonesia, Thailand, Philippines, Hong Kong, Japan, South Korea, China, "
        "and the Gulf/MENA region."
    ),
    "Entertainment": (
        "PRIMARY focus: Singapore entertainment — local events, concerts, festivals, "
        "theatre, arts, movies premiering or screening in Singapore, Singaporean artists "
        "and celebrities, Singapore-based productions. "
        "SECONDARY: broader Asia/SEA entertainment only when it has clear Singapore "
        "relevance (e.g. a K-pop act performing in Singapore, a regional streaming show "
        "popular here). Do NOT include generic Hollywood or global pop-culture news "
        "unless it has a direct Singapore angle."
    ),
}

SEARCH_MODEL = "claude-haiku-4-5-20251001"   # Pass 1 — web search (cheap, fast)
VERIFY_MODEL = "claude-haiku-4-5-20251001"   # Pass 2 — reasoning only (no web search)

# Verification confidence thresholds
VERIFY_HIGH   = 75   # score ≥ 75  → confirmed ✅
VERIFY_MEDIUM = 45   # score ≥ 45  → partially confirmed ⚠️
               # score  < 45  → unconfirmed ❌


# ──────────────────────────────────────────────────────────────────────────────
#  PASS 1 – Search
# ──────────────────────────────────────────────────────────────────────────────

# Categories where we want top-trending / most-important ranking
HIGH_IMPACT_CATEGORIES = {"Stocks", "Fiats", "Indexes", "Country Credit"}

# How many hours back each category searches for news.
# Fast-moving market categories stay at 24 h; niche / slow-moving ones get more runway
# so they are never empty on a quiet news day.
CATEGORY_TIME_WINDOW_HOURS: dict[str, int] = {
    "Stocks":              24,
    "Fiats":               24,
    "Indexes":             24,
    "Regional":            24,
    "Fintech":             24,
    "Country Credit":      72,
    "Alternative Lending": 72,
    "Entertainment":       72,
    "Sustainable Finance": 48,
    "Marketing":           48,
    "Start-up":            48,
}

# Results are reused for this many minutes before a fresh API call is made.
CACHE_TTL_MINUTES = 30


def fetch_news_with_search(
    category: str,
    claude_api_key: str,
    n: int,
    trusted_only: bool,
    keywords: list[str] | None = None,
    excluded_urls: set[str] | None = None,
    excluded_titles: set[str] | None = None,
    time_window_hours: int = 24,
) -> list[dict]:
    """
    Pass 1: Ask Claude to search the live web for the latest news in `category`.
    Returns a raw list of article dicts (title, source, published, url, summary, trusted).
    """
    # Use SGT (UTC+8) as the reference timezone — the app's primary audience is Singapore
    sgt_offset  = timezone(timedelta(hours=8))
    sgt_now     = datetime.now(timezone.utc).astimezone(sgt_offset)
    now_sgt_str = sgt_now.strftime("%Y-%m-%d %H:%M SGT")
    # Cutoff: articles should be published within the category's time window
    cutoff_utc  = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)
    cutoff_str  = cutoff_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    trusted_str  = ", ".join(TRUSTED_SOURCES.get(category, []))
    base_query   = CATEGORY_SEARCH_QUERIES.get(category, f"{category} news today")
    geo_focus    = CATEGORY_GEO_FOCUS.get(category, "")
    kw_list      = keywords if keywords else []

    # Build the search query: append each keyword as an OR alternative so Claude
    # searches for ANY of them rather than expecting all to appear together.
    if kw_list:
        kw_or        = " OR ".join(f'"{k}"' for k in kw_list)
        search_q     = f"{base_query} ({kw_or})"
        keyword_line = (
            "\nKeyword rule — include a story if it mentions AT LEAST ONE of these "
            f"keywords (not all of them): {', '.join(kw_list)}. "
            "Run separate searches per keyword when needed to find matching articles."
        )
    else:
        search_q     = base_query
        keyword_line = ""
    source_rule = (
        f"ONLY include articles from these trusted sources: {trusted_str}."
        if trusted_only
        else f"Preferred trusted sources (prioritise these): {trusted_str}."
    )

    # Build exclusion rule: skip articles already found in other categories
    excl_urls   = excluded_urls   or set()
    excl_titles = excluded_titles or set()
    if excl_urls or excl_titles:
        excl_parts = []
        if excl_urls:
            excl_parts.append("URLs: " + "; ".join(sorted(excl_urls)))
        if excl_titles:
            excl_parts.append("Headlines: " + "; ".join(sorted(excl_titles)))
        exclusion_rule = (
            "\nDEDUPLICATION — these articles are already assigned to other categories. "
            "Do NOT include them here, even if relevant:\n" + "\n".join(excl_parts)
        )
    else:
        exclusion_rule = ""

    # Extra ranking instruction for high-impact market categories
    if category in HIGH_IMPACT_CATEGORIES:
        ranking_rule = (
            "RANKING PRIORITY — do NOT pick random recent articles. "
            "Select only the {n} most market-moving, widely-covered or trending stories: "
            "stories with the highest reader interest, biggest price/policy impact, "
            "or most citations across multiple outlets. "
            "Prefer breaking news and stories that top financial news homepages right now."
        ).format(n=n)
    else:
        ranking_rule = (
            f"Select the {n} most significant and widely-reported stories within the scope above."
        )

    prompt = f"""Current time: {now_sgt_str}

Use the web_search tool to find the {n} most important news stories about **{category}**.

Search query to use: "{search_q}"{keyword_line}

Geographic / editorial focus:
{geo_focus}

{ranking_rule}

{source_rule}{exclusion_rule}

PUBLICATION DATE RULES — follow in order:
1. FIRST PRIORITY: articles published after {cutoff_str} (last {time_window_hours}h).
   Search for these first — they are preferred.
2. FILL RULE: if you find fewer than {n} articles within that window, extend your search
   backwards in time until you have {n} total. Never return an empty array.
   There is always relevant news — keep searching with different queries if needed.
3. Every article you return must have a real, verifiable publication date.

After searching, return ONLY a raw JSON array (no markdown, no explanation) with exactly {n} items.
Each item must have these fields:
  "title"     : exact headline from the article (string)
  "source"    : name of the news outlet (string)
  "published" : publication ISO datetime of the article, e.g. "2026-02-22T14:30:00Z" (string)
  "url"       : the real, full URL of the article — MUST be a working link you found (string)
  "summary"   : your 1-2 sentence summary of the story (string)
  "trusted"   : true if the source is in [{trusted_str}], else false (boolean)

OTHER RULES:
- Every URL must be a real link you actually retrieved via web_search — never invent URLs.
- Apply the geographic/editorial focus strictly.
- Do NOT wrap in markdown code fences — return the raw JSON array only.
"""
    return _run_claude_search(prompt, category, claude_api_key, n)


# ──────────────────────────────────────────────────────────────────────────────
#  PASS 2 – Verify
# ──────────────────────────────────────────────────────────────────────────────

def verify_articles(
    articles: list[dict],
    category: str,
    claude_api_key: str,
) -> list[dict]:
    """
    Pass 2: A lightweight reasoning-only call (no web search) that evaluates
    each article from Pass 1 on source reputation, headline plausibility,
    summary coherence, and recency.

    For each article it returns:
      "verified_score"  : int 0-100  (confidence the story is credible)
      "verified_status" : "confirmed" | "partial" | "unconfirmed"
      "verified_note"   : short explanation of the assessment
      "corrected_summary": optionally improved summary (or same as original)
    """
    if not articles:
        return articles

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build a compact list for the prompt
    articles_json = json.dumps(
        [{"idx": i, "title": a.get("title",""), "source": a.get("source",""),
          "url": a.get("url",""), "summary": a.get("summary","")}
         for i, a in enumerate(articles)],
        ensure_ascii=False, indent=2
    )

    prompt = f"""Today is {today}. You are a fact-checking editor for the **{category}** category.

Evaluate each article below using ONLY your internal knowledge and reasoning.
Do NOT hallucinate — if you are unsure about a source or claim, score conservatively.

Articles:
{articles_json}

For EACH article (by "idx"), evaluate these four signals:
1. **Source reputation**: Is the source a well-known, credible outlet for {category}?
   (Major wire services & established outlets → high; unknown or blog-like → low)
2. **Headline plausibility**: Does the title describe a realistic, specific event?
   (Concrete facts → high; vague clickbait or sensationalism → low)
3. **Summary coherence**: Are the summary details internally consistent and specific?
   (Named entities, dates, figures → high; generic filler → low)
4. **Recency**: Does the published date fall within the last 48 hours?

Scoring guide:
  75-100  Reputable source + plausible headline + coherent summary + recent
  45-74   Minor concerns on one signal (e.g. lesser-known source but plausible story)
  0-44    Unknown source, implausible claims, or inconsistent details

Return ONLY a raw JSON array (no markdown fences) with exactly {len(articles)} objects:
  "idx"              : int — same index as input
  "verified_score"   : int 0-100
  "verified_status"  : "confirmed" | "partial" | "unconfirmed"
  "verified_note"    : 1-2 sentences explaining your reasoning
  "corrected_summary": improved summary, or the original if accurate
"""

    delays = [5, 15]
    for attempt, delay in enumerate([0] + delays):
        if delay:
            time.sleep(delay)
        try:
            raw           = _run_claude_agentic_loop(
                prompt, claude_api_key,
                model=VERIFY_MODEL,
                tools=None,            # no web search — pure reasoning
            )
            verifications = _extract_json_array(raw)

            if verifications is None:
                if attempt < len(delays):
                    continue   # no JSON returned — retry
                return _mark_verify_skipped(articles, "Verifier returned no JSON")
            if not isinstance(verifications, list):
                if attempt < len(delays):
                    continue   # unexpected type — retry
                return _mark_verify_skipped(articles, "Verifier returned non-list JSON")

            # Merge verification results back into article dicts
            verify_map = {v.get("idx", i): v for i, v in enumerate(verifications)}
            enriched   = []
            for i, art in enumerate(articles):
                v     = verify_map.get(i, {})
                cor_s = v.get("corrected_summary", "")
                art   = dict(art)   # copy so we don't mutate original
                art["verified_score"]  = int(v.get("verified_score",  0))
                art["verified_status"] = v.get("verified_status", "unconfirmed")
                art["verified_note"]   = v.get("verified_note",   "No verification note returned.")
                if cor_s and cor_s != art.get("summary", ""):
                    art["summary"] = cor_s
                enriched.append(art)

            return enriched

        except anthropic.RateLimitError:
            if attempt < len(delays):
                continue
            return _mark_verify_skipped(articles, "Rate limit reached during verification")
        except Exception as e:
            return _mark_verify_skipped(articles, f"Verification error: {e}")

    return _mark_verify_skipped(articles, "Rate limit reached during verification")


def _mark_verify_skipped(articles: list[dict], reason: str) -> list[dict]:
    """Attach a 'skipped' verification marker to every article."""
    out = []
    for art in articles:
        art = dict(art)
        art["verified_score"]  = -1
        art["verified_status"] = "skipped"
        art["verified_note"]   = reason
        out.append(art)
    return out


# ──────────────────────────────────────────────────────────────────────────────
#  Shared Claude agentic-loop helpers
# ──────────────────────────────────────────────────────────────────────────────

def _run_claude_agentic_loop(
    prompt: str,
    claude_api_key: str,
    model: str = SEARCH_MODEL,
    tools: list[dict] | None = None,
) -> str:
    """
    Execute a Claude call — agentic (with tools) or single-turn (without).
    Returns the concatenated text of the final assistant message.
    Raises anthropic exceptions on API errors (callers handle them).
    """
    client   = anthropic.Anthropic(api_key=claude_api_key)
    messages = [{"role": "user", "content": prompt}]

    kwargs: dict = dict(model=model, max_tokens=1500, messages=messages)
    if tools:
        kwargs["tools"] = tools

    while True:
        response = client.messages.create(**kwargs)
        if response.stop_reason == "end_turn":
            break
        if response.stop_reason == "tool_use" and tools:
            messages.append({"role": "assistant", "content": response.content})
            tool_results = [
                {"type": "tool_result", "tool_use_id": b.id, "content": "Search completed."}
                for b in response.content if b.type == "tool_use"
            ]
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            continue
        break

    return "".join(getattr(b, "text", "") for b in response.content).strip()


def _extract_json_array(raw: str) -> list | None:
    """Strip markdown fences and extract the first JSON array from text.
    Returns the parsed list, or None if no array was found."""
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```\s*$",        "", raw, flags=re.MULTILINE).strip()
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return None
    return json.loads(match.group())


def _run_claude_search(
    prompt: str,
    category: str,
    claude_api_key: str,
    n: int,
) -> list[dict]:
    """Run a Claude web-search agentic loop and parse the JSON array response.
    Retries once on transient errors (bad JSON, rate limit). Empty results are
    handled upstream by the auto-fallback — no point retrying the same prompt."""
    delays = [8]   # one retry, 8 s gap, for transient API/JSON errors only

    for attempt, delay in enumerate([0] + delays):
        if delay:
            time.sleep(delay)
        try:
            raw      = _run_claude_agentic_loop(
                prompt, claude_api_key,
                model=SEARCH_MODEL,
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
            )
            articles = _extract_json_array(raw)

            if articles is None:
                # Claude returned text without a JSON array — retry once
                if attempt < len(delays):
                    continue
                return []
            if not isinstance(articles, list):
                raise ValueError("Expected JSON array")
            # Empty list is returned immediately; fallback is handled by the caller
            return articles[:n]

        except anthropic.AuthenticationError:
            st.error("❌ **Invalid Claude API key.** It should start with `sk-ant-`.")
            return []
        except anthropic.RateLimitError:
            if attempt < len(delays):
                continue   # wait and retry
            return []      # all retries exhausted
        except anthropic.APIError as e:
            err = str(e)
            if "web_search" in err.lower() or "tool" in err.lower():
                st.error(f"❌ Web search unavailable for **{category}**: {e}")
            else:
                st.error(f"❌ Claude API error for **{category}**: {e}")
            return []
        except json.JSONDecodeError:
            return []
        except Exception as e:
            st.error(f"❌ Unexpected error for **{category}**: {e}")
            return []

    return []


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def verify_css_class(score: int, status: str, trusted_only: bool = False) -> tuple[str, str, str]:
    """
    Returns (card_extra_class, badge_class, badge_label) based on
    the verification score / status.

    When trusted_only=True the 'skipped / not-verified' state is shown as
    'Trusted Source' (navy) rather than a confusing grey badge, because
    the article is already guaranteed to come from a curated outlet.
    """
    if status == "skipped" or score < 0:
        if trusted_only:
            # Already filtered to trusted outlets — no need to show 'Not verified'
            return "verified-high", "badge-verify-high", "✅ Trusted Source"
        return "", "badge-verify-skip", "🔘 Pending verification"
    if score >= VERIFY_HIGH:
        return "verified-high",   "badge-verify-high",   f"✅ Verified ({score}%)"
    if score >= VERIFY_MEDIUM:
        return "verified-medium", "badge-verify-medium", f"⚠️ Partially verified ({score}%)"
    return "verified-low", "badge-verify-low", f"❌ Could not verify ({score}%)"


def articles_to_df(articles: list[dict], category: str) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Category":      category,
            "Title":         a.get("title",           "N/A"),
            "Source":        a.get("source",          "Unknown"),
            "Published":     a.get("published",       ""),
            "Summary":       a.get("summary",         ""),
            "URL":           a.get("url",             ""),
            "Trusted":       "YES" if a.get("trusted", False) else "NO",
            "Verify Score":  a.get("verified_score",  ""),
            "Verify Status": a.get("verified_status", ""),
            "Verify Note":   a.get("verified_note",   ""),
        }
        for a in articles
    ])


def df_to_excel(dfs: dict[str, pd.DataFrame]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        all_df = pd.concat(dfs.values(), ignore_index=True) if dfs else pd.DataFrame()
        if not all_df.empty:
            all_df.to_excel(writer, sheet_name="All Articles", index=False)
        for cat, df in dfs.items():
            if not df.empty:
                df.to_excel(writer, sheet_name=cat[:31], index=False)
        for sheet in writer.sheets.values():
            for col in sheet.columns:
                w = max((len(str(c.value)) for c in col if c.value), default=10)
                sheet.column_dimensions[col[0].column_letter].width = min(w + 4, 80)
    return output.getvalue()


def strip_html_tags(text: str) -> str:
    """Remove any HTML tags from a string (e.g. tags Claude accidentally returns)."""
    return re.sub(r"<[^>]+>", "", text).strip()


def format_age(pub: str) -> str:
    """Return a human-readable age string, always in SGT context."""
    try:
        # Handle both 'Z' suffix and naive strings
        clean = pub[:19].replace("Z", "")
        dt = datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - dt
        total_secs = age.total_seconds()
        if total_secs < 0:
            # Future-dated — show the date
            return pub[:10]
        h = int(total_secs // 3600)
        m = int((total_secs % 3600) // 60)
        if h > 48:
            return pub[:10]
        return f"{h}h {m}m ago" if h else f"{m}m ago"
    except Exception:
        return pub[:10] if pub else "recent"


def is_within_24h(pub: str) -> bool:
    """Return True if the article's published timestamp is within the last 24 hours."""
    try:
        clean = pub[:19].replace("Z", "")
        dt  = datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - dt
        return 0 <= age.total_seconds() <= 86400   # 24 h = 86 400 s
    except Exception:
        return True   # if we can't parse, keep the article (don't silently drop)


# ──────────────────────────────────────────────────────────────────────────────
#  Sidebar
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.markdown('<span class="pill-claude">✦ Powered by Claude + Web Search</span>', unsafe_allow_html=True)
    st.markdown("")

    claude_api_key = st.text_input(
        "Anthropic (Claude) API Key",
        type="password",
        placeholder="sk-ant-…",
        help="Get yours at https://console.anthropic.com — this is the only key needed.",
    )

    st.markdown("---")
    st.markdown("### 📂 Categories")
    all_cats = list(CATEGORY_ICONS.keys())
    selected_cats = st.multiselect(
        "Select categories",
        options=all_cats,
        default=["Stocks", "Fiats", "Fintech"],
        format_func=lambda c: f"{CATEGORY_ICONS.get(c, '')} {c}",
        key="category_multiselect",
    )

    # ── Per-category keyword inputs ───────────────────────────────────────────
    if selected_cats:
        st.markdown("---")
        st.markdown("### 🏷️ Keywords")
        st.caption("Pre-filled per category — edit or clear as needed.")
        category_keywords: dict[str, list[str]] = {}
        for cat in selected_cats:
            defaults = CATEGORY_DEFAULT_KEYWORDS.get(cat, [])
            raw = st.text_input(
                f"{CATEGORY_ICONS.get(cat, '')} {cat}",
                value=", ".join(defaults),
                key=f"kw_{cat}",
                placeholder="keyword1, keyword2, …",
            )
            category_keywords[cat] = [k.strip() for k in raw.split(",") if k.strip()]
    else:
        category_keywords = {}

    st.markdown("---")
    st.markdown("### 🔍 Options")
    max_per_cat   = st.slider("Articles per category", 1, 10, 5)
    trusted_only  = st.checkbox("Trusted sources only", value=True)
    run_verify    = st.checkbox("Run Pass 2 verification", value=False,
                                help="Adds a second Claude call per category to cross-check credibility. Doubles API usage.")
    force_refresh = st.checkbox(
        f"Force refresh (ignore {CACHE_TTL_MINUTES}-min cache)", value=False,
        help=f"By default, results are reused for {CACHE_TTL_MINUTES} minutes to save API credits. "
             "Tick this to always fetch fresh results.",
    )

    st.markdown("---")
    st.markdown("### 🔬 How verification works")
    st.markdown("""
**Two-pass pipeline:**

**Pass 1 · Search** — Claude searches the live web and finds the latest news for each category.

**Pass 2 · Verify** — A second independent Claude call re-searches the web to cross-check every article:
- Confirms the story is real and recent
- Checks headline & key facts
- Scores confidence **0 – 100**:
  - 🟢 **≥ 75** Confirmed
  - 🟡 **45–74** Partially confirmed
  - 🔴 **< 45** Unconfirmed

*Most categories focus on **Asia · APAC · SEA**. Regional includes global geopolitical events. Sustainable Finance and Marketing have global coverage.*
    """)

# ──────────────────────────────────────────────────────────────────────────────
#  Header
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>📰 24h News Explorer</h1>
    <p>
        <span style="opacity:.8">Pass 1: Claude searches the web</span>
        &nbsp;·&nbsp;
        <span style="opacity:.8">Pass 2: Independent verification</span>
        &nbsp;·&nbsp;
        Asia · APAC · SEA focus
        &nbsp;·&nbsp;
        Export to Excel
    </p>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
#  Gate checks
# ──────────────────────────────────────────────────────────────────────────────
if not claude_api_key:
    st.info(
        "👈 Paste your **Anthropic API key** (`sk-ant-…`) in the sidebar.\n\n"
        "Get one at https://console.anthropic.com — it's the **only key you need**."
    )
    st.stop()

if not selected_cats:
    st.warning("⚠️ Please select at least one category from the sidebar.")
    st.stop()

# ──────────────────────────────────────────────────────────────────────────────
#  Search button
# ──────────────────────────────────────────────────────────────────────────────
search_btn = st.button(
    "🔍  Search Latest News via Claude",
    use_container_width=True,
    type="primary",
)

if search_btn or st.session_state.get("last_results"):

    if search_btn:
        # ── Cache check ───────────────────────────────────────────────────────
        last_fetch = st.session_state.get("fetched_at")
        use_cache  = (
            last_fetch
            and not force_refresh
            and (datetime.now() - last_fetch).total_seconds() < CACHE_TTL_MINUTES * 60
        )

        if use_cache:
            age_s   = (datetime.now() - last_fetch).total_seconds()
            age_min = int(age_s // 60)
            age_sec = int(age_s % 60)
            st.info(
                f"⚡ Showing cached results from **{age_min}m {age_sec}s ago** "
                f"(cache valid for {CACHE_TTL_MINUTES} min). "
                f"Tick **'Force refresh'** in the sidebar to fetch fresh data."
            )

        else:
            # ── Fresh fetch ───────────────────────────────────────────────────
            all_data:     dict[str, pd.DataFrame] = {}
            raw_articles: dict[str, list[dict]]   = {}

            total_cats = len(selected_cats)

            progress = st.progress(0, text="Starting…")
            status   = st.empty()

            INTER_CAT_PAUSE  = 6   # seconds between categories
            INTER_PASS_PAUSE = 3   # seconds between Pass 1 → Pass 2

            seen_urls:   set[str] = set()
            seen_titles: set[str] = set()

            for i, cat in enumerate(selected_cats):
                icon     = CATEGORY_ICONS.get(cat, "📌")
                base_pct = i / total_cats
                win_h    = CATEGORY_TIME_WINDOW_HOURS.get(cat, 24)

                if i > 0:
                    status.markdown(
                        f"⏱️ Pausing {INTER_CAT_PAUSE}s before next category…",
                        unsafe_allow_html=True,
                    )
                    time.sleep(INTER_CAT_PAUSE)

                # ── PASS 1: Search ────────────────────────────────────────────
                status.markdown(
                    f'<span class="pass-label pass-1">PASS 1 · SEARCH</span>'
                    f'🌐 Claude is searching for <b>{icon} {cat}</b> news '
                    f'(last {win_h}h)…',
                    unsafe_allow_html=True,
                )
                progress.progress(
                    base_pct,
                    text=f"Pass 1 – Searching: {cat}…",
                )

                articles = fetch_news_with_search(
                    category          = cat,
                    claude_api_key    = claude_api_key,
                    n                 = max_per_cat,
                    trusted_only      = trusted_only,
                    keywords          = category_keywords.get(cat, []),
                    excluded_urls     = seen_urls,
                    excluded_titles   = seen_titles,
                    time_window_hours = win_h,
                )

                # ── Auto-fallback if still empty ──────────────────────────────
                if not articles:
                    status.markdown(
                        f'<span class="pass-label pass-1">PASS 1 · RETRY</span>'
                        f'🔄 No results — retrying <b>{icon} {cat}</b> with relaxed filters…',
                        unsafe_allow_html=True,
                    )
                    articles = fetch_news_with_search(
                        category          = cat,
                        claude_api_key    = claude_api_key,
                        n                 = max_per_cat,
                        trusted_only      = False,          # open up source filter
                        keywords          = [],             # drop keyword restriction
                        excluded_urls     = seen_urls,
                        excluded_titles   = seen_titles,
                        time_window_hours = win_h * 2,      # double the time window
                    )
                    for a in articles:
                        a["fallback"] = True   # flag so card can show a note

                # Post-fetch dedup filter
                articles = [
                    a for a in articles
                    if a.get("url",   "").strip() not in seen_urls
                    and a.get("title", "").strip() not in seen_titles
                ]

                for a in articles:
                    if a.get("url"):
                        seen_urls.add(a["url"].strip())
                    if a.get("title"):
                        seen_titles.add(a["title"].strip())

                # ── PASS 2: Verify (optional) ─────────────────────────────────
                if articles and run_verify:
                    time.sleep(INTER_PASS_PAUSE)
                    status.markdown(
                        f'<span class="pass-label pass-2">PASS 2 · VERIFY</span>'
                        f'🔬 Cross-checking <b>{len(articles)}</b> articles in '
                        f'<b>{icon} {cat}</b>…',
                        unsafe_allow_html=True,
                    )
                    progress.progress(
                        base_pct + 0.5 / total_cats,
                        text=f"Pass 2 – Verifying: {cat}…",
                    )
                    articles = verify_articles(articles, cat, claude_api_key)

                progress.progress(
                    (i + 1) / total_cats,
                    text=f"Done: {cat}",
                )

                raw_articles[cat] = articles
                df = articles_to_df(articles, cat)
                if not df.empty:
                    all_data[cat] = df

            progress.empty()
            status.empty()

            st.session_state["last_results"] = all_data
            st.session_state["last_raw"]     = raw_articles
            st.session_state["fetched_at"]   = datetime.now()

    # ── Restore from session ──────────────────────────────────────────────────
    all_data     = st.session_state.get("last_results", {})
    raw_articles = st.session_state.get("last_raw",     {})

    # ── Metrics ───────────────────────────────────────────────────────────────
    total      = sum(len(df) for df in all_data.values())
    trusted_n  = sum((df["Trusted"] == "YES").sum() for df in all_data.values()) if all_data else 0
    cats_found = len(all_data)

    # Count confirmed articles (score >= VERIFY_HIGH)
    confirmed_n = 0
    for arts in raw_articles.values():
        for a in arts:
            if a.get("verified_score", -1) >= VERIFY_HIGH:
                confirmed_n += 1

    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-card">
            <div class="value">{total}</div>
            <div class="label">Total Articles</div>
        </div>
        <div class="metric-card">
            <div class="value">{trusted_n}</div>
            <div class="label">Trusted Sources</div>
        </div>
        <div class="metric-card">
            <div class="value" style="color:#16a34a">{confirmed_n}</div>
            <div class="label">✅ Verified (Pass 2)</div>
        </div>
        <div class="metric-card">
            <div class="value">{cats_found}</div>
            <div class="label">Categories</div>
        </div>
        <div class="metric-card">
            <div class="value">24h</div>
            <div class="label">Time Window</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Excel export ──────────────────────────────────────────────────────────
    if all_data:
        excel_bytes = df_to_excel(all_data)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        st.download_button(
            label="📥  Export All Results to Excel",
            data=excel_bytes,
            file_name=f"news_24h_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.markdown("---")

    # ── Article cards ─────────────────────────────────────────────────────────
    if not all_data:
        st.warning("No articles found. Check your API key or try different categories.")
    else:
        for cat in selected_cats:
            icon = CATEGORY_ICONS.get(cat, "📌")
            if cat not in all_data or all_data[cat].empty:
                st.markdown(
                    f'<div class="section-title">{icon} {cat}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    "<div style='background:#fef3c7;border:1px solid #fde68a;"
                    "border-left:4px solid #d97706;border-radius:8px;"
                    "padding:.8rem 1.1rem;margin-bottom:1rem;color:#78350f;'>"
                    "⏳ <b>No articles retrieved for this category.</b> "
                    "This is usually caused by a temporary API rate limit. "
                    "Wait a moment and search again — or reduce the number of "
                    "categories selected at once."
                    "</div>",
                    unsafe_allow_html=True,
                )
                continue

            icon     = CATEGORY_ICONS.get(cat, "📌")
            articles = raw_articles.get(cat, [])

            st.markdown(f'<div class="section-title">{icon} {cat}</div>', unsafe_allow_html=True)

            for art in articles:
                title   = art.get("title",          "No title")
                source  = art.get("source",         "Unknown")
                url     = art.get("url",            "#")
                pub     = art.get("published",      "")
                summary = art.get("summary",        "")
                trusted = art.get("trusted",        False)
                v_score  = art.get("verified_score",  -1)
                v_status  = art.get("verified_status", "skipped")
                v_note    = art.get("verified_note",   "")
                is_fallback = art.get("fallback", False)

                age_str    = format_age(pub)
                trust_cls  = "badge-trust-yes" if trusted else "badge-trust-no"
                trust_lbl  = "✅ Trusted"       if trusted else "⚠️ Unverified"

                card_cls, v_badge_cls, v_badge_lbl = verify_css_class(v_score, v_status, trusted_only)

                # ── staleness warning (outside 24 h window) ───────────────────
                stale_html = ""
                if pub and not is_within_24h(pub):
                    stale_html = (
                        "<div style='font-size:.75rem;color:#b45309;background:#fef3c7;"
                        "border:1px solid #fde68a;border-radius:5px;padding:.3rem .6rem;"
                        "margin:.4rem 0;'>⚠️ <b>Outside 24h window</b> — "
                        f"published {pub[:10]}</div>"
                    )

                clean_summary = strip_html_tags(summary)
                summary_html = (
                    f"<p class='summary-text'>{clean_summary}</p>"
                ) if clean_summary else ""

                # Sanitise URL: strip quotes and whitespace that break inline HTML
                safe_url = url.strip().replace('"', '%22').replace("'", '%27')

                # Source badge — clickable link
                source_badge = (
                    f"<a href='{safe_url}' target='_blank' style='text-decoration:none;'>"
                    f"<span class='badge badge-source'>🗞️ {source} ↗</span></a>"
                )

                # Read-more link — clean button style, no raw URL exposed
                read_link = (
                    f"<a href='{safe_url}' target='_blank' "
                    f"style='display:inline-block;margin-top:.5rem;font-size:.8rem;"
                    f"color:#1a3a6e;font-weight:600;text-decoration:none;"
                    f"border:1px solid #1a3a6e;border-radius:6px;"
                    f"padding:.25rem .75rem;'>"
                    f"🔗 Read full article →</a>"
                )

                st.markdown(f"""
                <div class="news-card {card_cls}">
                    <p class="headline">{title}</p>
                    <div class="meta">
                        {source_badge}
                        <span class="badge badge-cat">{icon} {cat}</span>
                        <span class="badge badge-time">🕐 {age_str}</span>
                        <span class="badge {trust_cls}">{trust_lbl}</span>
                        <span class="badge {v_badge_cls}">{v_badge_lbl}</span>
                        {"<span class='badge badge-verify-skip'>🔄 Extended search</span>" if is_fallback else ""}
                    </div>
                    {stale_html}
                    {summary_html}
                    {read_link}
                </div>
                """, unsafe_allow_html=True)
