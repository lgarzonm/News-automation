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

    /* ── Summary / verify text ── */
    .summary-text { color: #4a5568; font-size: .85rem; margin: .6rem 0 .4rem 0; }

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
        "Business Times Singapore", "Seeking Alpha",
    ],
    "Fiats": [
        "Bloomberg", "Reuters", "Financial Times", "Wall Street Journal",
        "CNBC", "FX Street", "Investopedia", "Nikkei Asia",
        "South China Morning Post", "MAS (Monetary Authority of Singapore)",
    ],
    "Indexes": [
        "Bloomberg", "Reuters", "Financial Times", "CNBC",
        "Nikkei Asia", "South China Morning Post", "Business Times Singapore",
        "The Straits Times", "Morningstar", "S&P Global",
    ],
    "Regional": [
        "Nikkei Asia", "South China Morning Post", "The Straits Times",
        "Bangkok Post", "The Jakarta Post", "Philippine Daily Inquirer",
        "Vietnam News", "Reuters", "Bloomberg", "Channel NewsAsia (CNA)",
    ],
    "Country Credit": [
        "Bloomberg", "Reuters", "Financial Times", "Moody's",
        "S&P Global", "Fitch Ratings", "The Straits Times",
        "Nikkei Asia", "South China Morning Post", "Asian Development Bank",
    ],
    "Alternative Lending": [
        "Bloomberg", "Reuters", "Fintech News Singapore", "e27",
        "Deal Street Asia", "Tech in Asia", "The Business Times",
        "Crowdfund Insider", "Lending Times", "AltFi",
    ],
    "Fintech": [
        "Fintech News Singapore", "e27", "Deal Street Asia", "Tech in Asia",
        "TechCrunch", "Bloomberg", "Reuters", "The Business Times",
        "Channel NewsAsia (CNA)", "Fintechnews.sg",
    ],
    "Start-up": [
        "e27", "Tech in Asia", "Deal Street Asia", "TechCrunch",
        "Bloomberg", "Reuters", "Channel NewsAsia (CNA)",
        "The Straits Times", "KrASIA", "Vulcan Post",
    ],
    "Sustainable Finance": [
        "Bloomberg Green", "Reuters", "Financial Times", "The Straits Times",
        "Channel NewsAsia (CNA)", "Eco-Business", "MAS (Monetary Authority of Singapore)",
        "Asian Development Bank", "Carbon Brief", "GreenBiz",
    ],
    "Marketing": [
        "Campaign Asia", "Marketing Interactive", "Mumbrella Asia",
        "The Drum", "Adweek", "South China Morning Post",
        "The Straits Times", "Channel NewsAsia (CNA)",
        "Marketing Week", "Ad Age",
    ],
    "Entertainment": [
        "Variety Asia", "Hollywood Reporter", "Deadline",
        "South China Morning Post", "The Straits Times",
        "Channel NewsAsia (CNA)", "Billboard", "Tatler Asia",
        "Nikkei Asia", "Vulcan Post",
    ],
}

CATEGORY_SEARCH_QUERIES: dict[str, str] = {
    "Stocks":              "global stock market equities news today Asia APAC",
    "Fiats":               "forex currency exchange rates USD EUR JPY SGD AUD news today",
    "Indexes":             "stock market index STI Nikkei Hang Seng ASX S&P 500 MSCI Asia news today",
    "Regional":            "Asia APAC Southeast Asia SEA Singapore economy finance news today",
    "Country Credit":      "sovereign credit rating Asia APAC Singapore bonds debt news today",
    "Alternative Lending": "alternative lending P2P crowdfunding credit Asia Singapore fintech news today",
    "Fintech":             "fintech financial technology Singapore Asia APAC payments digital banking news today",
    "Start-up":            "startup funding venture capital Asia Singapore APAC SEA news today",
    "Sustainable Finance": "sustainable finance ESG green bonds Singapore Asia APAC news today",
    "Marketing":           "marketing advertising brand campaigns Asia Singapore APAC SEA news today",
    "Entertainment":       "entertainment movies music streaming celebrities Asia Singapore APAC SEA news today",
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
        "Focus EXCLUSIVELY on Asia, APAC, and Southeast Asia (SEA) — especially "
        "Singapore, Malaysia, Indonesia, Thailand, Vietnam, Philippines, Hong Kong, "
        "China, Japan, South Korea, Australia. No stories from outside these regions."
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
        "Focus on sustainable finance, ESG, green and transition bonds in Asia, APAC "
        "and SEA — especially Singapore (MAS Green Finance Action Plan), ASEAN "
        "Taxonomy, and regional net-zero initiatives."
    ),
    "Marketing": (
        "Focus on marketing, advertising, branding, digital marketing and media campaigns "
        "in Asia, APAC and SEA — especially Singapore, Malaysia, Indonesia, Thailand, "
        "Philippines, Hong Kong, Japan, South Korea and China."
    ),
    "Entertainment": (
        "Focus on entertainment news — movies, TV, music, streaming, gaming and celebrity "
        "culture — in Asia, APAC and SEA. Prioritise content relevant to or produced in "
        "Singapore, South Korea (K-pop/K-drama), Japan (anime/manga), China, Hong Kong, "
        "India (Bollywood), Thailand, Malaysia, Indonesia and the Philippines."
    ),
}

CLAUDE_MODEL = "claude-opus-4-5"

# Verification confidence thresholds
VERIFY_HIGH   = 75   # score ≥ 75  → confirmed ✅
VERIFY_MEDIUM = 45   # score ≥ 45  → partially confirmed ⚠️
               # score  < 45  → unconfirmed ❌


# ──────────────────────────────────────────────────────────────────────────────
#  PASS 1 – Search
# ──────────────────────────────────────────────────────────────────────────────

# Categories where we want top-trending / most-important ranking
HIGH_IMPACT_CATEGORIES = {"Stocks", "Fiats", "Indexes", "Country Credit"}


def fetch_news_with_search(
    category: str,
    claude_api_key: str,
    n: int,
    trusted_only: bool,
) -> list[dict]:
    """
    Pass 1: Ask Claude to search the live web for the latest news in `category`.
    Returns a raw list of article dicts (title, source, published, url, summary, trusted).
    """
    # Use SGT (UTC+8) as the reference timezone — the app's primary audience is Singapore
    sgt_offset  = timezone(timedelta(hours=8))
    sgt_now     = datetime.now(timezone.utc).astimezone(sgt_offset)
    now_sgt_str = sgt_now.strftime("%Y-%m-%d %H:%M SGT")
    # Strict cutoff: articles must be published AFTER this ISO timestamp
    cutoff_utc  = datetime.now(timezone.utc) - timedelta(hours=24)
    cutoff_str  = cutoff_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    trusted_str = ", ".join(TRUSTED_SOURCES.get(category, []))
    search_q    = CATEGORY_SEARCH_QUERIES.get(category, f"{category} news today")
    geo_focus   = CATEGORY_GEO_FOCUS.get(category, "")
    source_rule = (
        f"ONLY include articles from these trusted sources: {trusted_str}."
        if trusted_only
        else f"Preferred trusted sources (prioritise these): {trusted_str}."
    )

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

    prompt = f"""Current time: {now_sgt_str}  (UTC cutoff: {cutoff_str})

Use the web_search tool to find the {n} most important news stories about **{category}**
that were published STRICTLY AFTER {cutoff_str} (i.e. within the last 24 hours only).

Search query to use: "{search_q}"

Geographic / editorial focus:
{geo_focus}

{ranking_rule}

{source_rule}

After searching, return ONLY a raw JSON array (no markdown, no explanation) with exactly {n} items.
Each item must have these fields:
  "title"     : exact headline from the article (string)
  "source"    : name of the news outlet (string)
  "published" : publication ISO datetime of the article, e.g. "2026-02-22T14:30:00Z" (string)
  "url"       : the real, full URL of the article — MUST be a working link you found (string)
  "summary"   : your 1-2 sentence summary of the story (string)
  "trusted"   : true if the source is in [{trusted_str}], else false (boolean)

STRICT RULES:
- REJECT any article published before {cutoff_str} — do not include it regardless of relevance.
- Every URL must be a real link you actually retrieved via web_search — never invent URLs.
- Apply the geographic/editorial focus strictly.
- If you find fewer than {n} qualifying articles, return however many you found.
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
    Pass 2: A second independent Claude call re-searches the web to cross-check
    every article from Pass 1.

    For each article it returns:
      "verified_score"  : int 0-100  (confidence the story is real & accurate)
      "verified_status" : "confirmed" | "partial" | "unconfirmed"
      "verified_note"   : short explanation of what the verification found
      "corrected_summary": optionally improved summary (or same as original)

    Articles that cannot be confirmed at all are flagged but still returned
    so the user can decide whether to trust them.
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

    prompt = f"""Today is {today}. You are an independent fact-checking editor for the **{category}** category.

You have been given a list of news articles found by a colleague. Your job is to verify each one
independently using your web_search tool — do NOT simply trust the data you were given.

Articles to verify:
{articles_json}

For EACH article (identified by its "idx"):
1. Search the web to confirm the story is real and was published in the last 48 hours.
2. Check whether the title, source and key facts in the summary are accurate.
3. Assign a confidence score (0–100):
   - 75-100 : Story confirmed by independent search — facts check out
   - 45-74  : Story partially confirmed — found related coverage but details differ slightly
   - 0-44   : Story NOT confirmed — could not find independent evidence, or facts appear wrong

Return ONLY a raw JSON array (no markdown) with exactly {len(articles)} objects, one per article,
in the same order, with these fields:
  "idx"              : same integer index as input (int)
  "verified_score"   : confidence score 0-100 (int)
  "verified_status"  : "confirmed" | "partial" | "unconfirmed" (string)
  "verified_note"    : 1-2 sentences explaining what your independent search found (string)
  "corrected_summary": improved or confirmed summary — keep original if accurate (string)

Rules:
- Use web_search for EVERY article — do not guess.
- Be strict: a score ≥ 75 means you found independent corroboration.
- Do NOT wrap in markdown code fences — return the raw JSON array only.
"""

    try:
        client = anthropic.Anthropic(api_key=claude_api_key)
        tools  = [{"type": "web_search_20250305", "name": "web_search"}]
        messages = [{"role": "user", "content": prompt}]

        while True:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                tools=tools,
                messages=messages,
            )
            if response.stop_reason == "end_turn":
                break
            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = [
                    {"type": "tool_result", "tool_use_id": b.id, "content": "Search completed."}
                    for b in response.content if b.type == "tool_use"
                ]
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
                continue
            break

        raw = "".join(getattr(b, "text", "") for b in response.content).strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$",        "", raw, flags=re.MULTILINE)
        raw = raw.strip()

        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            # Verification failed — return articles with a "skip" flag
            return _mark_verify_skipped(articles, "Verifier returned no JSON")

        verifications = json.loads(match.group())
        if not isinstance(verifications, list):
            return _mark_verify_skipped(articles, "Verifier returned non-list JSON")

        # Merge verification results back into article dicts
        verify_map = {v.get("idx", i): v for i, v in enumerate(verifications)}
        enriched = []
        for i, art in enumerate(articles):
            v = verify_map.get(i, {})
            score  = int(v.get("verified_score",  0))
            status = v.get("verified_status", "unconfirmed")
            note   = v.get("verified_note",   "No verification note returned.")
            cor_s  = v.get("corrected_summary", art.get("summary", ""))

            art = dict(art)   # copy so we don't mutate original
            art["verified_score"]   = score
            art["verified_status"]  = status
            art["verified_note"]    = note
            # Use corrected summary if verifier improved it
            if cor_s and cor_s != art.get("summary", ""):
                art["summary"] = cor_s
            enriched.append(art)

        return enriched

    except anthropic.RateLimitError:
        st.warning("⏳ Rate limit hit during verification — articles shown without Pass 2 check.")
        return _mark_verify_skipped(articles, "Rate limit reached during verification")
    except Exception as e:
        st.warning(f"⚠️ Verification pass failed ({e}) — showing unverified articles.")
        return _mark_verify_skipped(articles, f"Verification error: {e}")


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
#  Shared Claude agentic-loop helper
# ──────────────────────────────────────────────────────────────────────────────

def _run_claude_search(
    prompt: str,
    category: str,
    claude_api_key: str,
    n: int,
) -> list[dict]:
    """Run a Claude web-search agentic loop and parse the JSON array response."""
    try:
        client   = anthropic.Anthropic(api_key=claude_api_key)
        tools    = [{"type": "web_search_20250305", "name": "web_search"}]
        messages = [{"role": "user", "content": prompt}]

        while True:
            response = client.messages.create(
                model=CLAUDE_MODEL, max_tokens=4096,
                tools=tools, messages=messages,
            )
            if response.stop_reason == "end_turn":
                break
            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = [
                    {"type": "tool_result", "tool_use_id": b.id, "content": "Search completed."}
                    for b in response.content if b.type == "tool_use"
                ]
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
                continue
            break

        raw = "".join(getattr(b, "text", "") for b in response.content).strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$",        "", raw, flags=re.MULTILINE)
        raw = raw.strip()

        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            st.warning(f"⚠️ Claude returned no JSON array for **{category}**.")
            return []

        articles = json.loads(match.group())
        if not isinstance(articles, list):
            raise ValueError("Expected JSON array")
        return articles[:n]

    except anthropic.AuthenticationError:
        st.error("❌ **Invalid Claude API key.** It should start with `sk-ant-`.")
        return []
    except anthropic.RateLimitError:
        st.error("⏳ **Claude rate limit reached.** Wait a moment and try again.")
        return []
    except anthropic.APIError as e:
        err = str(e)
        if "web_search" in err.lower() or "tool" in err.lower():
            st.error(f"❌ Web search unavailable for **{category}**: {e}")
        else:
            st.error(f"❌ Claude API error for **{category}**: {e}")
        return []
    except json.JSONDecodeError as e:
        st.warning(f"⚠️ Could not parse response for **{category}**: {e}")
        return []
    except Exception as e:
        st.error(f"❌ Unexpected error for **{category}**: {e}")
        return []


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def verify_css_class(score: int, status: str) -> tuple[str, str, str]:
    """
    Returns (card_extra_class, badge_class, badge_label) based on
    the verification score / status.
    """
    if status == "skipped" or score < 0:
        return "", "badge-verify-skip", "🔘 Not verified"
    if score >= VERIFY_HIGH:
        return "verified-high",   "badge-verify-high",   f"✅ Confirmed ({score}%)"
    if score >= VERIFY_MEDIUM:
        return "verified-medium", "badge-verify-medium", f"⚠️ Partial ({score}%)"
    return "verified-low", "badge-verify-low", f"❌ Unconfirmed ({score}%)"


def articles_to_df(articles: list[dict], category: str) -> pd.DataFrame:
    rows = []
    for a in articles:
        rows.append({
            "Category":          category,
            "Title":             a.get("title",          "N/A"),
            "Source":            a.get("source",         "Unknown"),
            "Published":         a.get("published",      ""),
            "Summary":           a.get("summary",        ""),
            "URL":               a.get("url",            ""),
            "Trusted":           "YES" if a.get("trusted", False) else "NO",
            "Verify Score":      a.get("verified_score",  ""),
            "Verify Status":     a.get("verified_status", ""),
            "Verify Note":       a.get("verified_note",   ""),
        })
    return pd.DataFrame(rows)


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

    st.markdown("---")
    st.markdown("### 🔍 Options")
    max_per_cat  = st.slider("Articles per category", 1, 10, 5)
    trusted_only = st.checkbox("Trusted sources only", value=True)

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

*Non-Stocks/Fiats categories focus on **Asia · APAC · SEA**.*
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
    "🔍  Search & Verify Latest News via Claude  (last 24 h)",
    use_container_width=True,
    type="primary",
)

if search_btn or st.session_state.get("last_results"):

    if search_btn:
        all_data:     dict[str, pd.DataFrame] = {}
        raw_articles: dict[str, list[dict]]   = {}

        total_cats = len(selected_cats)

        # ── progress UI ───────────────────────────────────────────────────────
        # Each category has 2 sub-steps (search + verify) → total steps = cats × 2
        progress = st.progress(0, text="Starting…")
        status   = st.empty()

        for i, cat in enumerate(selected_cats):
            icon = CATEGORY_ICONS.get(cat, "📌")
            base_pct = i / total_cats   # fraction at start of this category

            # ── PASS 1: Search ────────────────────────────────────────────────
            status.markdown(
                f'<span class="pass-label pass-1">PASS 1 · SEARCH</span>'
                f'🌐 Claude is searching for <b>{icon} {cat}</b> news…',
                unsafe_allow_html=True,
            )
            progress.progress(
                base_pct + 0.0 / total_cats,
                text=f"Pass 1 – Searching: {cat}…",
            )

            articles = fetch_news_with_search(
                category       = cat,
                claude_api_key = claude_api_key,
                n              = max_per_cat,
                trusted_only   = trusted_only,
            )

            # ── PASS 2: Verify ────────────────────────────────────────────────
            if articles:
                status.markdown(
                    f'<span class="pass-label pass-2">PASS 2 · VERIFY</span>'
                    f'🔬 Cross-checking <b>{len(articles)}</b> articles in <b>{icon} {cat}</b>…',
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
            if cat not in all_data or all_data[cat].empty:
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
                v_status = art.get("verified_status", "skipped")
                v_note   = art.get("verified_note",   "")

                age_str    = format_age(pub)
                trust_cls  = "badge-trust-yes" if trusted else "badge-trust-no"
                trust_lbl  = "✅ Trusted"       if trusted else "⚠️ Unverified"

                card_cls, v_badge_cls, v_badge_lbl = verify_css_class(v_score, v_status)

                # ── staleness warning (outside 24 h window) ───────────────────
                stale_html = ""
                if pub and not is_within_24h(pub):
                    stale_html = (
                        "<div style='font-size:.75rem;color:#b45309;background:#fef3c7;"
                        "border:1px solid #fde68a;border-radius:5px;padding:.3rem .6rem;"
                        "margin:.4rem 0;'>⚠️ <b>Outside 24h window</b> — "
                        f"published {pub[:10]}</div>"
                    )

                summary_html = (
                    f"<p class='summary-text'>"
                    f"{summary[:280]}{'…' if len(summary) > 280 else ''}</p>"
                ) if summary else ""

                verify_note_html = (
                    f"<div class='verify-note'>"
                    f"<span class='pass-label pass-2'>PASS 2 · VERIFY</span> {v_note}"
                    f"</div>"
                ) if v_note and v_status != "skipped" else ""

                # Source badge is now a clickable link to the article
                source_badge = (
                    f"<a href='{url}' target='_blank' style='text-decoration:none;'>"
                    f"<span class='badge badge-source'>🗞️ {source} ↗</span></a>"
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
                    </div>
                    {stale_html}
                    {summary_html}
                    {verify_note_html}
                    <a href="{url}" target="_blank">🔗 Read full article →</a>
                </div>
                """, unsafe_allow_html=True)
