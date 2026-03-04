"""
36h News Explorer
─────────────────
Uses Claude with the built-in `web_search` tool (Anthropic API).

Single-pass pipeline:
  Claude searches the live web for real news (last 36 h) and simultaneously
  self-assesses each article's credibility — source reputation, headline
  plausibility, and recency — returning a verified_score (0-100) inline.

Only ONE API key needed: your Anthropic (Claude) key.
"""

import html as html_mod
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
    page_title="📰 36h News Explorer",
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
        display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
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
        "The Business Times", "Business Times", "Channel NewsAsia", "CNA",
        "The Edge Singapore", "Asia Financial", "Seeking Alpha",
        "Barron's", "Barrons", "MarketWatch", "Yahoo Finance", "AP News",
        "Investor's Business Daily", "Japan Wire by Kyodo News",
    ],
    "Fiats": [
        "Bloomberg", "Reuters", "Financial Times", "Wall Street Journal",
        "CNBC", "FX Street", "Investing.com", "Nikkei Asia",
        "South China Morning Post", "MAS", "Bank Indonesia",
        "Barron's", "MarketWatch", "FX Empire", "Convera",
        "The Edge Singapore", "Business Times", "CNA",
    ],
    "Indexes": [
        "Bloomberg", "Reuters", "Financial Times", "CNBC", "AP News",
        "Nikkei Asia", "South China Morning Post", "Business Times",
        "The Straits Times", "Morningstar", "S&P Global",
        "MarketWatch", "Barron's", "Yahoo Finance", "Xinhua",
        "Japan Wire by Kyodo News", "AMRO",
    ],
    "Regional": [
        "Nikkei Asia", "South China Morning Post", "The Straits Times",
        "Bangkok Post", "The Jakarta Post", "Philippine Daily Inquirer",
        "Manila Times", "Vietnam News", "Reuters", "Bloomberg",
        "Channel NewsAsia", "CNA", "Financial Times", "Wall Street Journal",
        "The Guardian", "BBC", "Associated Press", "Al Jazeera",
        "The Malay Mail", "YICAI Global", "Asian News Network",
        "Japan Wire by Kyodo News", "Korea JoongAng Daily",
        "Times of India", "Business Times",
    ],
    "Country Credit": [
        "Bloomberg", "Reuters", "Financial Times", "Moody's",
        "S&P Global", "Fitch Ratings", "The Straits Times",
        "Nikkei Asia", "South China Morning Post", "Asian Development Bank",
        "Asian Banking & Finance", "Asia Times", "Barron's",
        "Vietnam News", "Bangkok Post", "The Jakarta Post",
    ],
    "Alternative Lending": [
        "Bloomberg", "Reuters", "Financial Times", "Asian Banking & Finance",
        "The Business Times", "Business Times", "Caproasia",
        "Private Debt Investor", "Institutional Investor",
        "CNBC", "Yahoo Finance", "Global Trade Review",
        "Crowdfund Insider", "AltFi", "Asset Report",
        "The Intermediary", "Alternative Credit Investor",
    ],
    "Fintech": [
        "Fintech News Singapore", "Fintech Magazine", "e27", "Deal Street Asia", "Tech in Asia",
        "TechCrunch", "Bloomberg", "Reuters", "The Business Times", "Business Times",
        "Channel NewsAsia", "CNA", "Finextra", "Payments Dive",
        "Asian Banking & Finance", "The Fintech Times", "Digital Banker",
        "Singapore Business Review", "Data Economy", "Meyka",
        "Fintech Futures", "Fintech Global",
        "Nikkei Asia", "South China Morning Post", "Manila Bulletin",
    ],
    "Start-up": [
        "e27", "Tech in Asia", "Deal Street Asia", "TechCrunch",
        "Bloomberg", "Reuters", "Channel NewsAsia", "CNA",
        "The Straits Times", "KrASIA", "Vulcan Post",
        "Yahoo Finance", "Forbes", "Business Insider",
        "Caproasia", "BlockHead", "PE Insights", "YICAI Global",
        "Korea Tech Desk",
    ],
    "Sustainable Finance": [
        "Bloomberg", "Reuters", "Financial Times", "The Straits Times",
        "Channel NewsAsia", "CNA", "Eco-Business", "ESG News",
        "Asian Development Bank", "Carbon Brief", "GreenBiz",
        "CNBC", "Wall Street Journal", "S&P Global",
        "Singapore Business Review", "EU Reporter", "Business Line",
        "Mena FN", "Sustainability Magazine",
    ],
    "Marketing": [
        "Campaign Asia", "Marketing Interactive", "Mumbrella Asia",
        "The Drum", "Adweek", "Marketing Week", "Ad Age",
        "South China Morning Post", "The Straits Times",
        "Sports Business Journal", "Media Newsroom", "AI News",
        "USA Today", "Singapore Business Review",
    ],
    "Entertainment": [
        "The Straits Times", "CNA", "TODAY", "8Days", "Mothership",
        "Time Out Singapore", "Time Out", "Visit Singapore", "The Smart Local",
        "Variety Asia", "South China Morning Post",
        "Billboard", "Tatler Asia", "Vulcan Post",
        "Bandwagon", "HungryGoWhere", "Sethlui.com", "Gardens by the Bay",
    ],
}

CATEGORY_SEARCH_QUERIES: dict[str, str] = {
    "Stocks":              "stock market equities IPO earnings corporate Asia APAC Singapore STI Wall Street CEO leadership news today",
    "Fiats":               "forex currency USD SGD IDR CNY JPY spot rate CBDC digital currency central bank rate decision exchange rate news today",
    "Indexes":             "stock index S&P 500 Dow Nasdaq Nikkei STI Kospi Hang Seng MSCI ASEAN economic outlook inflation gold news today",
    "Regional":            "Asia APAC Southeast Asia geopolitical economy trade deal Singapore Indonesia Malaysia Philippines India Japan news today",
    "Country Credit":      "sovereign credit rating Moody's S&P Fitch upgrade downgrade outlook government bonds fiscal banking credit news today",
    "Alternative Lending": "private credit alternative lending securitization real estate credit APAC Asia direct lending fund global news today",
    "Fintech":             "fintech digital banking payments neobank embedded finance AI agent payment crypto BNPL digital payment growth Singapore APAC Asia global news today",
    "Start-up":            "startup funding venture capital VC PE AI unicorn valuation round APAC Asia global deep tech news today",
    "Sustainable Finance": "sustainable finance ESG green bond carbon net zero climate transition Asia global corporate news today",
    "Marketing":           "marketing advertising brand campaign sports partnership AI agency digital transformation news today",
    "Entertainment":       "Singapore restaurant opening food dining events concerts arts lifestyle things to do weekend news today",
}

CATEGORY_DEFAULT_KEYWORDS: dict[str, list[str]] = {
    "Stocks": [
        "earnings", "profits", "stock rally", "stock drop", "IPO",
        "dividends", "buyback", "valuation", "volatility", "leadership change", "CEO",
        "STI", "Kospi", "Nifty", "Sensex", "Asian markets", "market cap",
        "geopolitical", "tariffs", "fully subscribed", "capex",
    ],
    "Fiats": [
        "USD/SGD", "USD/IDR", "dollar", "euro", "DXY", "currency", "FX",
        "exchange rate", "devaluation", "central bank", "rate decision", "rate hold",
        "SGD", "IDR", "rupee", "yuan", "ringgit", "baht", "yen", "PBOC", "MAS",
        "CBDC", "digital euro", "digital yuan", "de-dollarization", "gold cap",
    ],
    "Indexes": [
        "S&P 500", "Nasdaq", "Dow", "Nikkei", "Hang Seng",
        "MSCI", "MSCI addition", "market rally", "market selloff", "futures",
        "STI", "Kospi", "AMRO", "ASEAN growth", "inflation data",
        "gold record", "index record high", "market recap",
    ],
    "Regional": [
        "ASEAN", "Southeast Asia", "APAC", "Singapore economy", "Indonesia economy",
        "Malaysia economy", "Philippines economy", "China stimulus", "Asia growth",
        "trade deal", "tariffs", "geopolitical", "Middle East", "conflict",
        "sanctions", "elections", "data centre", "AI investment", "5G",
        "India bank", "ICT market",
    ],
    "Country Credit": [
        "sovereign debt", "government bonds", "credit rating", "Moody's", "S&P",
        "Fitch", "default risk", "fiscal deficit", "bond yields",
        "upgrade", "downgrade", "outlook change", "rating action", "public debt",
        "banking credit", "loan outlook", "sovereign rating", "liquidity",
        "emerging market debt", "treasury",
    ],
    "Alternative Lending": [
        "private credit", "alternative lending", "non-bank lending", "asset-backed",
        "loan portfolio", "credit fund", "structured finance", "securitization",
        "Blackstone", "Blue Owl", "Ares", "KKR credit", "Apollo", "direct lending",
        "AIIB", "loan growth", "real estate credit", "private markets",
        "credit infrastructure", "BDC", "trade finance",
    ],
    "Fintech": [
        "fintech", "digital bank", "neobank", "e-wallet", "payments", "BNPL",
        "digital lending", "open banking", "blockchain", "crypto", "financial inclusion",
        "AI fintech", "fintech funding", "fintech IPO", "fintech investment",
        "APAC fintech", "digital payment", "credit invisible", "wealthtech",
    ],
    "Start-up": [
        "startup funding", "venture capital", "VC fund", "PE fund", "Series A", "Series B",
        "unicorn", "valuation", "seed round", "acquisition", "IPO",
        "robotics", "biotech", "deep tech", "AI startup",
        "crypto VC", "fund close", "hospitality strategy",
        "digital economy", "startup ecosystem",
    ],
    "Sustainable Finance": [
        "green bond", "ESG", "ESG-linked", "sustainability", "climate finance", "carbon",
        "net zero", "energy transition", "impact investing", "renewable energy", "climate policy",
        "carbon fund", "transition finance", "social bond", "low carbon",
        "sustainable finance platform", "climate grant", "EPA",
        "corporate ESG", "mobilising capital", "sustainable target",
    ],
    "Marketing": [
        "marketing campaign", "brand partnership", "advertising", "digital marketing",
        "sports marketing", "sponsorship", "product launch", "AI in marketing",
        "marketing agency", "agency outsourcing", "marketing summit",
        "tourism spend", "mega-event", "marketing initiative", "official partner",
    ],
    "Entertainment": [
        "Singapore concert", "Singapore festival", "Singapore arts", "Singapore theatre",
        "Singapore premiere", "Singapore exhibition", "local artist", "Singapore music",
        "restaurant opening", "brunch", "food festival", "dining Singapore",
        "things to do", "weekend events", "Time Out Singapore",
        "Singapore food", "Singapore lifestyle", "new restaurant", "Singapore Airshow",
    ],
}

CATEGORY_GEO_FOCUS: dict[str, str] = {
    "Stocks": (
        "Coverage is global (US, Europe, Asia). Include: APAC and Singapore equity market moves, "
        "major Asian IPOs, corporate earnings, CEO/leadership changes at significant companies, "
        "and global market-moving events (tariffs, geopolitical shocks, capex announcements). "
        "Do NOT include currency, index-level, or macroeconomic data stories — those belong in Fiats/Indexes."
    ),
    "Fiats": (
        "Coverage is global, with strong focus on currencies relevant to Singapore readers: "
        "USD/SGD and USD/IDR spot rates, CNY, JPY, KRW, INR, AUD, MYR, THB, EUR. "
        "Include: central bank rate decisions, CBDC developments (digital euro, digital yuan, "
        "MAS), currency outlook and analyst calls, FX market moves driven by policy or data. "
        "Do NOT include stock market or equity articles."
    ),
    "Indexes": (
        "Cover major index moves globally: S&P 500, Dow, Nasdaq, Nikkei 225, Hang Seng, "
        "STI, KOSPI, ASX 200, CSI 300, MSCI (additions, rebalancing). "
        "Also include: ASEAN/APAC economic forecasts (AMRO, ADB), inflation data releases "
        "that move markets, gold price records, and broad market recap articles. "
        "Do NOT include individual stock stories — those belong in Stocks."
    ),
    "Regional": (
        "PRIMARY focus: Asia, APAC, and Southeast Asia (SEA) — Singapore, Malaysia, "
        "Indonesia, Thailand, Vietnam, Philippines, Hong Kong, China, Japan, South Korea, "
        "India, Australia. Cover trade deals, foreign investment, government policy, "
        "infrastructure, tech investment, and business expansions in the region. "
        "EXCEPTION: if a global event outside Asia is of exceptional magnitude — "
        "e.g. a major military conflict, a US-Iran escalation, a G7 policy shock — "
        "that dominates front pages worldwide, include it (max 1-2 such stories). "
        "Do NOT include routine non-Asia stories just because they are geopolitical."
    ),
    "Country Credit": (
        "Cover sovereign and banking credit: rating actions (upgrades/downgrades/outlook changes) "
        "by Moody's, S&P, or Fitch on any country — global in scope. "
        "Also include: banking sector credit quality (loan growth, credit squeeze, NPLs), "
        "government fiscal outlook, sovereign bond yields, and treasury market stories "
        "when they relate to creditworthiness. "
        "Primary focus: APAC (Indonesia, Philippines, Japan, China, India, South Korea, "
        "Malaysia, Vietnam), but major actions elsewhere (Kenya, Denmark, Latin America) "
        "are in scope when published by a rating agency."
    ),
    "Alternative Lending": (
        "Coverage is global — do NOT restrict to Asia. "
        "Private credit and alternative lending are dominated by US and European fund managers "
        "(Blackstone, Blue Owl, Ares, Apollo, KKR, Caproasia deals). "
        "Cover: private credit fundraising and deals, securitization trends, AI in credit, "
        "direct lending performance and risk, real estate credit (APAC and global), "
        "AIIB/multilateral private credit partnerships, and APAC loan growth data. "
        "Do NOT include fintech payments or digital banking stories — those belong in Fintech."
    ),
    "Fintech": (
        "Coverage is global — fintech is a worldwide sector and major stories come from "
        "Latin America (Brazil), Europe, Africa, and the US as well as APAC. "
        "Cover: fintech funding and IPOs, digital payments growth, neobanks (Revolut, Agibank), "
        "BNPL, crypto innovation, AI in financial services, APAC fintech market data "
        "(investment trends, market size forecasts), and financial inclusion stories. "
        "Prioritise APAC (Singapore, Hong Kong, Indonesia, Malaysia, Philippines, Vietnam, "
        "Australia, India), but include global fintech news of significance."
    ),
    "Start-up": (
        "Coverage is global — major AI startup funding rounds (Anthropic, Runway) are as "
        "relevant as APAC deals. "
        "Cover: VC/PE fund closes, startup funding rounds (Seed to Series D+), unicorn "
        "valuations, crypto VC, AI and deep-tech investments, APAC hospitality/real estate PE, "
        "notable acquisitions. "
        "Primary focus: Asia, APAC and SEA ecosystems. "
        "Include global AI and deep-tech startups unconditionally when deal size or "
        "innovation significance is high."
    ),
    "Sustainable Finance": (
        "Coverage is global. Include: green bonds, ESG-linked products, carbon funds, "
        "sustainable finance targets (bank commitments like StanChart $300B), "
        "climate policy (EPA, EU Taxonomy, Singapore MAS Green Finance), "
        "low-carbon logistics and supply chain, transition finance, and net-zero commitments. "
        "Give priority to APAC and SEA stories, but do NOT exclude major global deals, "
        "regulatory actions, or policy rollbacks regardless of geography."
    ),
    "Marketing": (
        "Cover: marketing campaigns, brand partnerships, sports sponsorships (Olympics, "
        "Grand Prix, tours), AI applications in marketing, marketing agency trends and "
        "transformations, marketing summits and industry events, and mega-event tourism. "
        "Prioritise Asia and APAC but include global trends that affect the industry. "
        "Do NOT include stock market, financial markets, economic data, or investment "
        "articles — those belong in Stocks, Indexes, or Fiats."
    ),
    "Entertainment": (
        "PRIMARY focus: Singapore lifestyle — restaurant and food venue openings, "
        "food festivals, weekend guides (things to do in Singapore), concerts, exhibitions, "
        "theatre, arts, movies premiering in Singapore, and Singapore-hosted events "
        "(Singapore Airshow, F1, food fairs, Gardens by the Bay shows). "
        "SECONDARY: international chains opening specifically in Singapore, "
        "K-pop or Asian acts performing in Singapore. "
        "Do NOT include generic global entertainment news without a Singapore angle."
    ),
}

MODEL = "claude-haiku-4-5-20251001"

# Verification confidence thresholds
VERIFY_HIGH   = 75   # score ≥ 75  → confirmed ✅
VERIFY_MEDIUM = 45   # score ≥ 45  → partially confirmed ⚠️
               # score  < 45  → unconfirmed ❌


# ──────────────────────────────────────────────────────────────────────────────
#  PASS 1 – Search
# ──────────────────────────────────────────────────────────────────────────────

# Categories where we want top-trending / most-important ranking
HIGH_IMPACT_CATEGORIES = {"Stocks", "Fiats", "Indexes", "Country Credit"}

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
    fill_hours: int = 36,
) -> list[dict]:
    """
    Ask Claude to search the live web for the latest news in `category`.
    The hard time window is always the last 36 h — no extension beyond that.
    Returns a raw list of article dicts (title, source, published, url, summary, trusted).
    """
    # Use SGT (UTC+8) as the reference timezone — the app's primary audience is Singapore
    sgt_offset     = timezone(timedelta(hours=8))
    sgt_now        = datetime.now(timezone.utc).astimezone(sgt_offset)
    now_sgt_str    = sgt_now.strftime("%Y-%m-%d %H:%M SGT")
    cutoff_36h     = datetime.now(timezone.utc) - timedelta(hours=36)
    cutoff_36h_str = cutoff_36h.strftime("%Y-%m-%dT%H:%M:%SZ")

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
            "SEARCH STRATEGY — follow these three steps in order:\n\n"
            "STEP 1 — SCAN BREAKING NEWS FIRST.\n"
            "Before anything else, run a broad search:\n"
            '  "financial markets breaking news today {now_sgt_str}"\n'
            "This tells you what major events (wars, sanctions, trade shocks, "
            "central bank surprises, currency crises, market crashes) are "
            "actively dominating headlines RIGHT NOW. Note what you find.\n\n"
            "STEP 2 — RUN YOUR CATEGORY SEARCH.\n"
            'Use the query: "{search_q}"\n\n'
            "STEP 3 — RANK AND SELECT by this strict priority tier system:\n"
            "  TIER 1 — Market-wide shocks (MUST appear if happening):\n"
            "    Wars, military escalations, sanctions, emergency central bank actions,\n"
            "    currency crises, major sovereign defaults, Strait-of-Hormuz/supply-chain\n"
            "    disruptions, major tariff announcements. If a Tier-1 event is happening\n"
            "    today, it MUST be in your results — it outranks everything else.\n"
            "  TIER 2 — Macro market moves covered by 5+ major outlets:\n"
            "    Index-level crashes or rallies, oil price spikes, mass risk-off/risk-on,\n"
            "    Fed/ECB/major-CB decisions, MSCI rebalancing, major ETF flows.\n"
            "  TIER 3 — Significant corporate or sovereign news:\n"
            "    Major earnings beats/misses, large IPOs, CEO changes at blue-chip firms,\n"
            "    sovereign rating actions, large M&A.\n"
            "  TIER 4 — Routine news: smaller company updates, analyst calls, previews.\n\n"
            "WITHIN EACH TIER — prefer the most recently published article.\n"
            "A Tier-1 article from 1 hour ago ALWAYS beats a Tier-3 article from 35 hours ago.\n"
            "Select only the {n} most important stories by this ranking."
        ).format(n=n, now_sgt_str=now_sgt_str, search_q=search_q)
    else:
        ranking_rule = (
            f"Select the {n} most significant and widely-reported stories within the scope above. "
            f"Prefer the most recently published articles within the 36-hour window."
        )

    # For non-high-impact categories the search query lives here;
    # for HIGH_IMPACT it is embedded inside ranking_rule (Step 2).
    query_line = (
        ""
        if category in HIGH_IMPACT_CATEGORIES
        else f'\nSearch query to use: "{search_q}"{keyword_line}\n'
    )

    prompt = f"""Current time: {now_sgt_str}

You are a financial news editor. Find the {n} most important and currently relevant news stories about **{category}**.

Geographic / editorial focus:
{geo_focus}
{query_line}
{ranking_rule}

{source_rule}{exclusion_rule}

PUBLICATION DATE RULES — non-negotiable:
1. HARD WINDOW: only include articles published after {cutoff_36h_str} (last 36 h).
   Do NOT include anything older — no exceptions, even if fewer than {n} articles are found.
2. If you genuinely cannot find {n} real articles within the last 36 h, return however many
   you did find (even if fewer than {n}). Return an empty array [] if none at all.
   Do NOT fabricate articles. Do NOT stretch the date window.
3. Every article must have a real, verifiable publication date.

After searching, return ONLY a raw JSON array (no markdown, no explanation) with exactly {n} items.
Each item must have these fields:
  "title"           : exact headline from the article (string)
  "source"          : name of the news outlet (string)
  "published"       : publication ISO datetime, e.g. "2026-02-22T14:30:00Z" (string)
  "url"             : the real, full URL — MUST be a working link you found (string)
  "summary"         : factual 1-2 sentence summary of the article content ONLY — no disclaimers, no caveats, no verification notes (string)
  "trusted"         : true if the source is in [{trusted_str}], else false (boolean)
  "verified_score"  : int 0-100 — your confidence this article is credible and real
  "verified_status" : "confirmed" | "partial" | "unconfirmed"
  "verified_note"   : 1 sentence explaining your confidence rating (string)

Confidence scoring guide for verified_score:
  75-100 : reputable outlet + specific factual headline + concrete details + within 36h
  45-74  : minor concern — lesser-known source OR headline is vague
  0-44   : unknown/unreliable source, vague or clickbait headline, inconsistent details

OTHER RULES:
- Every URL must be a real link you actually retrieved via web_search — never invent URLs.
- Apply the geographic/editorial focus strictly.
- Do NOT wrap in markdown code fences — return the raw JSON array only.
"""
    return _run_claude_search(prompt, category, claude_api_key, n)


# ──────────────────────────────────────────────────────────────────────────────
#  Shared Claude agentic-loop helpers
# ──────────────────────────────────────────────────────────────────────────────

def _run_claude_agentic_loop(
    prompt: str,
    claude_api_key: str,
    model: str = MODEL,
    tools: list[dict] | None = None,
) -> str:
    """
    Execute a Claude call — agentic (with tools) or single-turn (without).
    Returns the concatenated text of the final assistant message.
    Raises anthropic exceptions on API errors (callers handle them).
    """
    client   = anthropic.Anthropic(api_key=claude_api_key)
    messages = [{"role": "user", "content": prompt}]

    kwargs: dict = dict(model=model, max_tokens=4000, messages=messages)
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
    # Find the first '[' and the matching closing ']' by counting brackets,
    # rather than using a greedy/non-greedy regex that can over- or under-match.
    start = raw.find("[")
    if start == -1:
        return None
    depth, end = 0, -1
    for i, ch in enumerate(raw[start:], start):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None


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
                model=MODEL,
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
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


def is_within_36h(pub: str) -> bool:
    """Return True if the article's published timestamp is within the last 36 hours."""
    try:
        clean = pub[:19].replace("Z", "")
        dt  = datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - dt
        return 0 <= age.total_seconds() <= 129600   # 36 h = 129 600 s
    except Exception:
        return True   # if we can't parse, keep the article (don't silently drop)


# Hard ceiling: regardless of what Claude returns, never show articles older than this.
# Hard cap: any article older than 36 h is dropped, regardless of what Claude returned.
MAX_ARTICLE_AGE_HOURS = 36


def _within_max_age(pub: str) -> bool:
    """Return True if the article is within the 36-hour hard cap."""
    try:
        clean = pub[:19].replace("Z", "")
        dt  = datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - dt
        return 0 <= age.total_seconds() <= MAX_ARTICLE_AGE_HOURS * 3600
    except Exception:
        return True   # unparseable date — keep the article, don't silently drop


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
    force_refresh = st.checkbox(
        f"Force refresh (ignore {CACHE_TTL_MINUTES}-min cache)", value=False,
        help=f"By default, results are reused for {CACHE_TTL_MINUTES} minutes to save API credits. "
             "Tick this to always fetch fresh results.",
    )

    st.markdown("---")
    st.markdown("### 🔬 How it works")
    st.markdown("""
**Single-pass pipeline:**

Claude searches the live web for each category and simultaneously self-assesses every article it finds:
- Source reputation (major outlet vs unknown)
- Headline plausibility (specific facts vs clickbait)
- Recency (published within the 36h window)

**Confidence score 0 – 100:**
  - 🟢 **≥ 75** Confirmed
  - 🟡 **45–74** Partially confirmed
  - 🔴 **< 45** Unconfirmed

*Most categories: **Asia · APAC · SEA** focus. Sustainable Finance and Marketing are global.*
    """)

# ──────────────────────────────────────────────────────────────────────────────
#  Header
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>📰 36h News Explorer</h1>
    <p>
        <span style="opacity:.8">Claude searches the web &amp; self-verifies each article</span>
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

            seen_urls:   set[str] = set()
            seen_titles: set[str] = set()

            for i, cat in enumerate(selected_cats):
                icon     = CATEGORY_ICONS.get(cat, "📌")
                base_pct = i / total_cats

                # ── Search ────────────────────────────────────────────────────
                status.markdown(
                    f'🌐 Searching <b>{icon} {cat}</b>…',
                    unsafe_allow_html=True,
                )
                progress.progress(
                    base_pct,
                    text=f"Searching: {cat}…",
                )

                articles = fetch_news_with_search(
                    category       = cat,
                    claude_api_key = claude_api_key,
                    n              = max_per_cat,
                    trusted_only   = trusted_only,
                    keywords       = category_keywords.get(cat, []),
                    excluded_urls  = seen_urls,
                    excluded_titles= seen_titles,
                    fill_hours     = 36,   # hard 36-hour window
                )

                # ── Auto-fallback if still empty ──────────────────────────────
                # Retries within the SAME 36-hour window, but with source filter
                # and keyword restriction relaxed — no date extension.
                if not articles:
                    status.markdown(
                        f'<span class="pass-label pass-1">PASS 1 · RETRY</span>'
                        f'🔄 No results — retrying <b>{icon} {cat}</b> with relaxed filters…',
                        unsafe_allow_html=True,
                    )
                    articles = fetch_news_with_search(
                        category       = cat,
                        claude_api_key = claude_api_key,
                        n              = max_per_cat,
                        trusted_only   = False,   # open up source filter
                        keywords       = [],      # drop keyword restriction
                        excluded_urls  = seen_urls,
                        excluded_titles= seen_titles,
                        fill_hours     = 36,      # still hard 36-hour cap — no extension
                    )
                    for a in articles:
                        a["fallback"] = True   # flag so card can show a note

                # Hard date cap — drop anything older than 36 h
                # regardless of what Claude returned (prevents stale content slipping through)
                articles = [a for a in articles if _within_max_age(a.get("published", ""))]

                # Post-fetch dedup filter
                articles = [
                    a for a in articles
                    if a.get("url",   "").strip() not in seen_urls
                    and a.get("title", "").strip() not in seen_titles
                ]

                for a in articles:
                    u = str(a.get("url") or "").strip()
                    if u and u != "#":          # don't treat missing-URL placeholder as a real URL
                        seen_urls.add(u)
                    if a.get("title"):
                        seen_titles.add(a["title"].strip())

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
            <div class="label">✅ Verified</div>
        </div>
        <div class="metric-card">
            <div class="value">{cats_found}</div>
            <div class="label">Categories</div>
        </div>
        <div class="metric-card">
            <div class="value">36h</div>
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
            file_name=f"news_36h_{ts}.xlsx",
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
                    "📭 <b>No articles found in the last 36 hours for this category.</b> "
                    "Try searching again later, or adjust the categories selected."
                    "</div>",
                    unsafe_allow_html=True,
                )
                continue

            icon     = CATEGORY_ICONS.get(cat, "📌")
            articles = raw_articles.get(cat, [])

            st.markdown(f'<div class="section-title">{icon} {cat}</div>', unsafe_allow_html=True)

            for art in articles:
                title   = html_mod.escape(str(art.get("title")   or "No title"))
                source  = html_mod.escape(str(art.get("source")  or "Unknown"))
                url     = str(art.get("url") or "#").strip()
                pub     = str(art.get("published") or "")
                summary = str(art.get("summary")   or "")
                trusted = bool(art.get("trusted",  False))
                # verified_score: Claude may return a string — coerce safely
                try:
                    v_score = int(art.get("verified_score", -1))
                except (TypeError, ValueError):
                    v_score = -1
                v_status    = str(art.get("verified_status") or "skipped")
                v_note      = str(art.get("verified_note")   or "")
                is_fallback = bool(art.get("fallback", False))

                age_str    = format_age(pub)
                trust_cls  = "badge-trust-yes" if trusted else "badge-trust-no"
                trust_lbl  = "✅ Listed source" if trusted else "📰 Unlisted source"

                card_cls, v_badge_cls, v_badge_lbl = verify_css_class(v_score, v_status, trusted_only)

                clean_summary = html_mod.escape(strip_html_tags(summary))
                summary_html = (
                    f"<p class='summary-text'>{clean_summary}</p>"
                ) if clean_summary else ""

                clean_note = html_mod.escape(strip_html_tags(v_note))
                note_html  = (
                    f"<div class='verify-note'>🔍 {clean_note}</div>"
                ) if clean_note else ""

                # Sanitise URL for use inside a single-quoted HTML attribute:
                # html.escape handles & → &amp; (required in HTML attrs),
                # then we URL-encode ' so it can't break the attribute boundary.
                safe_url = html_mod.escape(url, quote=False).replace("'", "%27")

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

                # Build card as a single concatenated string — NO blank lines.
                # Streamlit's CommonMark parser ends an HTML block the moment it
                # sees a blank line, so any empty interpolated variable (e.g. note_html="")
                # in a multi-line f-string would split the block and show raw HTML.
                card_html = (
                    f'<div class="news-card {card_cls}">'
                    + f'<p class="headline">{title}</p>'
                    + f'<div class="meta">'
                    + source_badge
                    + f'<span class="badge badge-cat">{icon} {cat}</span>'
                    + f'<span class="badge badge-time">🕐 {age_str}</span>'
                    + f'<span class="badge {trust_cls}">{trust_lbl}</span>'
                    + f'<span class="badge {v_badge_cls}">{v_badge_lbl}</span>'
                    + '</div>'
                    + summary_html
                    + note_html
                    + read_link
                    + '</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)
