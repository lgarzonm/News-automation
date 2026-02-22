"""
24h News Explorer
─────────────────
Architecture:
  1. NewsAPI.org  → fetches REAL articles published in the last 24 h (live URLs, real dates)
  2. Claude API   → acts as an intelligent curator: filters noise, ranks relevance,
                    adds a short editorial summary, and flags trusted sources.

Both API keys are entered by the user in the sidebar.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO

import anthropic
import pandas as pd
import requests
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
#  CSS
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container{padding-top:2rem;padding-bottom:2rem}

    /* header */
    .app-header{
        background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);
        border-radius:16px;padding:2rem 2.5rem;margin-bottom:2rem;text-align:center
    }
    .app-header h1{color:#e94560;font-size:2.6rem;margin:0}
    .app-header p{color:#a8b2d8;font-size:1.05rem;margin-top:.5rem}

    /* metric row */
    .metric-row{display:flex;gap:1rem;margin-bottom:1.5rem}
    .metric-card{
        flex:1;background:#16213e;border:1px solid #0f3460;border-radius:12px;
        padding:1rem 1.4rem;text-align:center
    }
    .metric-card .value{font-size:2rem;font-weight:700;color:#e94560}
    .metric-card .label{font-size:.85rem;color:#a8b2d8;margin-top:.2rem}

    /* news cards */
    .news-card{
        background:#16213e;border:1px solid #0f3460;
        border-left:4px solid #e94560;border-radius:10px;
        padding:1rem 1.3rem;margin-bottom:.9rem
    }
    .news-card:hover{border-left-color:#f5a623}
    .news-card .headline{
        color:#e2e8f0;font-size:1rem;font-weight:600;
        line-height:1.45;margin:0 0 .55rem 0
    }
    .news-card .meta{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center}
    .badge{font-size:.72rem;padding:.2rem .6rem;border-radius:20px;font-weight:600}
    .badge-source{background:#0f3460;color:#63b3ed}
    .badge-cat{background:#2d3748;color:#f6ad55}
    .badge-time{background:#1a202c;color:#68d391}
    .badge-trust-yes{background:#1c3a2b;color:#68d391}
    .badge-trust-no{background:#3a2a1c;color:#f6ad55}
    .news-card a{font-size:.8rem;color:#667eea;text-decoration:none}
    .news-card a:hover{text-decoration:underline}

    /* section title */
    .section-title{
        color:#e94560;font-size:1.3rem;font-weight:700;
        border-bottom:2px solid #e94560;padding-bottom:.4rem;margin-bottom:1.2rem
    }

    /* sidebar */
    [data-testid="stSidebar"]{background:#0d1117}
    [data-testid="stSidebar"] .stMarkdown h3{color:#e94560!important}

    /* download button */
    .stDownloadButton>button{
        background:linear-gradient(135deg,#e94560,#f5a623)!important;
        color:white!important;border:none!important;border-radius:8px!important;
        font-weight:600!important;padding:.55rem 1.2rem!important
    }
    .stDownloadButton>button:hover{opacity:.85!important}

    /* pill badges */
    .pill-claude{
        display:inline-block;background:linear-gradient(135deg,#6B46C1,#9F7AEA);
        color:white;font-size:.7rem;font-weight:700;padding:.2rem .7rem;
        border-radius:20px;letter-spacing:.05em
    }
    .pill-news{
        display:inline-block;background:linear-gradient(135deg,#1a56db,#3b82f6);
        color:white;font-size:.7rem;font-weight:700;padding:.2rem .7rem;
        border-radius:20px;letter-spacing:.05em;margin-left:.3rem
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────────────────────

CATEGORY_ICONS: dict[str, str] = {
    "Technology":            "💻",
    "Finance & Markets":     "📈",
    "Politics":              "🏛️",
    "Science":               "🔬",
    "Health & Medicine":     "🏥",
    "Business":              "💼",
    "AI & Machine Learning": "🤖",
    "Environment":           "🌿",
    "Sports":                "⚽",
    "Entertainment":         "🎬",
}

# Clean keyword queries for NewsAPI (no special chars)
CATEGORY_QUERIES: dict[str, str] = {
    "Technology":            "technology",
    "Finance & Markets":     "finance OR markets OR economy OR stocks",
    "Politics":              "politics OR government OR election OR policy",
    "Science":               "science OR research OR discovery OR study",
    "Health & Medicine":     "health OR medicine OR medical OR disease OR drug",
    "Business":              "business OR corporate OR startup OR earnings",
    "AI & Machine Learning": "artificial intelligence OR machine learning OR AI OR LLM",
    "Environment":           "environment OR climate OR nature OR emissions OR energy",
    "Sports":                "sports OR football OR basketball OR tennis OR soccer",
    "Entertainment":         "entertainment OR movies OR music OR celebrity OR film",
}

# Trusted source domains for NewsAPI `domains` filter + trust badge logic
TRUSTED_DOMAINS: dict[str, list[str]] = {
    "Technology":            ["techcrunch.com", "wired.com", "theverge.com", "arstechnica.com", "engadget.com", "technologyreview.com"],
    "Finance & Markets":     ["bloomberg.com", "reuters.com", "ft.com", "wsj.com", "cnbc.com", "economist.com"],
    "Politics":              ["reuters.com", "bbc.co.uk", "apnews.com", "politico.com", "theguardian.com", "npr.org"],
    "Science":               ["scientificamerican.com", "nature.com", "newscientist.com", "sciencedaily.com", "livescience.com", "nationalgeographic.com"],
    "Health & Medicine":     ["who.int", "webmd.com", "healthline.com", "statnews.com", "medpagetoday.com", "thelancet.com"],
    "Business":              ["bloomberg.com", "forbes.com", "businessinsider.com", "reuters.com", "fortune.com", "hbr.org"],
    "AI & Machine Learning": ["venturebeat.com", "techcrunch.com", "wired.com", "technologyreview.com", "thenextweb.com"],
    "Environment":           ["theguardian.com", "bbc.co.uk", "nationalgeographic.com", "carbonbrief.org", "climatecentral.org"],
    "Sports":                ["espn.com", "bbc.co.uk", "skysports.com", "theathletic.com", "si.com"],
    "Entertainment":         ["variety.com", "hollywoodreporter.com", "deadline.com", "ew.com", "rollingstone.com"],
}

NEWSAPI_BASE  = "https://newsapi.org/v2/everything"
CLAUDE_MODEL  = "claude-opus-4-5"
MAX_FETCH     = 20   # articles pulled from NewsAPI before Claude trims to user's N

# ──────────────────────────────────────────────────────────────────────────────
#  Step 1 — NewsAPI: fetch real, live articles
# ──────────────────────────────────────────────────────────────────────────────

def fetch_real_articles(category: str, news_api_key: str, trusted_only: bool) -> list[dict]:
    """
    Pull up to MAX_FETCH real articles from NewsAPI published in the last 24 h.
    If trusted_only is True, restrict to the pre-vetted domain list.
    """
    from_dt = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    query   = CATEGORY_QUERIES[category]
    domains = ",".join(TRUSTED_DOMAINS[category]) if trusted_only else None

    params: dict = {
        "q":        query,
        "from":     from_dt,
        "sortBy":   "publishedAt",
        "language": "en",
        "pageSize": MAX_FETCH,
        "apiKey":   news_api_key,
    }
    if domains:
        params["domains"] = domains

    try:
        resp = requests.get(NEWSAPI_BASE, params=params, timeout=15)
        data = resp.json()

        if data.get("status") != "ok":
            code = data.get("code", "")
            msg  = data.get("message", resp.text)
            if code == "apiKeyInvalid":
                st.error("❌ **Invalid NewsAPI key.** Get a free one at https://newsapi.org/register")
            elif code == "rateLimited":
                st.error("⏳ **NewsAPI rate limit hit.** Wait a moment and retry.")
            else:
                st.error(f"NewsAPI error for **{category}**: {msg}")
            return []

        articles = data.get("articles", [])
        # Strip "[Removed]" placeholders NewsAPI sometimes returns
        articles = [
            a for a in articles
            if a.get("title") and a["title"] != "[Removed]"
            and a.get("url")  and a["url"]   != "https://removed.com"
        ]
        return articles

    except requests.exceptions.ConnectionError:
        st.error("🔌 Connection error — check your internet connection.")
        return []
    except requests.exceptions.Timeout:
        st.error("⏱ NewsAPI request timed out. Please try again.")
        return []
    except Exception as e:
        st.error(f"Unexpected error fetching news for **{category}**: {e}")
        return []


# ──────────────────────────────────────────────────────────────────────────────
#  Step 2 — Claude: curate, rank, and summarise the real articles
# ──────────────────────────────────────────────────────────────────────────────

def _articles_to_text(articles: list[dict]) -> str:
    """Serialise NewsAPI articles into a compact text block for Claude."""
    lines = []
    for i, a in enumerate(articles, 1):
        pub    = a.get("publishedAt", "")[:16].replace("T", " ")
        source = (a.get("source") or {}).get("name", "Unknown")
        title  = a.get("title",       "").replace("\n", " ")
        desc   = (a.get("description") or "").replace("\n", " ")[:200]
        url    = a.get("url", "")
        lines.append(
            f"{i}. [{source}] {title}\n"
            f"   Published: {pub} UTC | URL: {url}\n"
            f"   Description: {desc}"
        )
    return "\n\n".join(lines)


def curate_with_claude(
    category: str,
    articles: list[dict],
    claude_api_key: str,
    n: int,
    trusted_domains: list[str],
) -> list[dict]:
    """
    Send the real articles to Claude.
    Claude returns a ranked, deduplicated JSON list of the top-N stories.
    """
    if not articles:
        return []

    articles_text = _articles_to_text(articles)
    trusted_str   = ", ".join(trusted_domains)
    today         = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    prompt = f"""You are an expert news editor. Current time: {today}.

Below are {len(articles)} REAL news articles fetched from NewsAPI for the category "{category}".
Your job is to select and return the TOP {n} most important, relevant, and recent stories.

Trusted sources for this category: {trusted_str}

Rules:
- You MUST use ONLY the articles provided below — do NOT invent any new stories.
- Preserve the EXACT original URL from each article — never modify or guess URLs.
- Preserve the EXACT publishedAt timestamp.
- Preserve the EXACT source name.
- Write a concise 1–2 sentence editorial summary (field "summary") based on the title+description.
- Set "trusted": true only if the source domain matches one of the trusted sources above.
- Pick the most newsworthy and diverse set of stories — avoid near-duplicates.
- Return EXACTLY {n} items (or fewer if fewer articles were provided).

Return ONLY a raw JSON array (no markdown, no explanation) with these fields per item:
  "title"      : original headline (string)
  "source"     : source name (string)
  "published"  : publishedAt value (string, e.g. "2026-02-22T14:30:00Z")
  "url"        : original article URL (string) — MUST be copied exactly
  "summary"    : your 1-2 sentence editorial summary (string)
  "trusted"    : true or false (boolean)

Articles to choose from:
{articles_text}

JSON array:"""

    try:
        client  = anthropic.Anthropic(api_key=claude_api_key)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip accidental markdown fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$",        "", raw, flags=re.MULTILINE)
        raw = raw.strip()

        curated = json.loads(raw)
        if not isinstance(curated, list):
            raise ValueError("Expected JSON array")

        # Safety: make sure URLs were not hallucinated (must appear in original set)
        original_urls = {a.get("url", "") for a in articles}
        safe = []
        for item in curated:
            url = item.get("url", "")
            if url not in original_urls:
                # Fall back to finding the article by matching title
                match = next(
                    (a for a in articles if a.get("title", "") == item.get("title", "")),
                    None,
                )
                item["url"] = match["url"] if match else url
            safe.append(item)

        return safe[:n]

    except anthropic.AuthenticationError:
        st.error("❌ **Invalid Claude API key.** Check your key at https://console.anthropic.com")
        return []
    except anthropic.RateLimitError:
        st.error("⏳ **Claude rate limit reached.** Wait a moment and retry.")
        return []
    except anthropic.APIError as e:
        st.error(f"❌ Claude API error for **{category}**: {e}")
        return []
    except json.JSONDecodeError:
        # If Claude still adds prose, try to extract the JSON array
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())[:n]
            except Exception:
                pass
        st.warning(f"⚠️ Could not parse Claude's curation for **{category}** — showing raw NewsAPI results.")
        return []
    except Exception as e:
        st.error(f"Unexpected Claude error for **{category}**: {e}")
        return []


# ──────────────────────────────────────────────────────────────────────────────
#  Fallback — build curated list directly from raw NewsAPI when Claude fails
# ──────────────────────────────────────────────────────────────────────────────

def _build_fallback(articles: list[dict], category: str, n: int) -> list[dict]:
    """Convert raw NewsAPI articles into the same shape as Claude's output."""
    trusted_doms = TRUSTED_DOMAINS.get(category, [])
    result = []
    for a in articles[:n]:
        source_name = (a.get("source") or {}).get("name", "Unknown")
        url         = a.get("url", "")
        is_trusted  = any(d in url.lower() for d in trusted_doms)
        result.append({
            "title":     a.get("title", ""),
            "source":    source_name,
            "published": a.get("publishedAt", ""),
            "url":       url,
            "summary":   (a.get("description") or "")[:240],
            "trusted":   is_trusted,
        })
    return result


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers — DataFrame & Excel
# ──────────────────────────────────────────────────────────────────────────────

def articles_to_df(articles: list[dict], category: str) -> pd.DataFrame:
    rows = []
    for a in articles:
        pub = a.get("published", "")
        try:
            dt      = datetime.strptime(pub[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            pub_fmt = dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            pub_fmt = pub
        rows.append({
            "Category":  category,
            "Title":     a.get("title",   "N/A"),
            "Source":    a.get("source",  "Unknown"),
            "Published": pub_fmt,
            "Summary":   a.get("summary", ""),
            "URL":       a.get("url",     ""),
            "Trusted":   "YES" if a.get("trusted", False) else "NO",
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


# ──────────────────────────────────────────────────────────────────────────────
#  Sidebar
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ API Keys")
    st.markdown(
        '<span class="pill-news">NewsAPI</span>'
        '<span class="pill-claude">✦ Claude</span>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    news_api_key = st.text_input(
        "NewsAPI Key",
        type="password",
        placeholder="Paste your NewsAPI key…",
        help="Free at https://newsapi.org/register — 100 req/day",
    )
    claude_api_key = st.text_input(
        "Claude (Anthropic) API Key",
        type="password",
        placeholder="sk-ant-…",
        help="Get yours at https://console.anthropic.com",
    )

    st.markdown("---")
    st.markdown("### 📂 Categories")
    all_cats = list(CATEGORY_ICONS.keys())
    selected_cats = st.multiselect(
        "Select categories",
        options=all_cats,
        default=["Technology", "Finance & Markets", "AI & Machine Learning"],
        format_func=lambda c: f"{CATEGORY_ICONS.get(c,'')} {c}",
    )

    st.markdown("---")
    st.markdown("### 🔍 Options")
    max_per_cat  = st.slider("Articles per category", 3, 10, 5)
    trusted_only = st.checkbox("Trusted sources only", value=False)

    st.markdown("---")
    st.markdown("### ℹ️ How it works")
    st.markdown("""
1. **NewsAPI** fetches real articles published in the last **24 hours** with live URLs  
2. **Claude** reads those real articles and selects the most important ones, adds summaries, and flags trusted sources  
3. Results are displayed with **working links** and can be exported to **Excel**
    """)

# ──────────────────────────────────────────────────────────────────────────────
#  Header
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>📰 24h News Explorer</h1>
    <p>Real articles via NewsAPI &nbsp;·&nbsp; Curated by Claude &nbsp;·&nbsp; Working links &nbsp;·&nbsp; Export to Excel</p>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
#  Gate checks
# ──────────────────────────────────────────────────────────────────────────────
if not news_api_key or not claude_api_key:
    missing = []
    if not news_api_key:
        missing.append("**NewsAPI key** — free at https://newsapi.org/register")
    if not claude_api_key:
        missing.append("**Claude API key** — free at https://console.anthropic.com")
    st.info("👈 Please enter the following in the sidebar:\n\n" + "\n\n".join(f"• {m}" for m in missing))
    st.stop()

if not selected_cats:
    st.warning("⚠️ Select at least one category in the sidebar.")
    st.stop()

# ──────────────────────────────────────────────────────────────────────────────
#  Search
# ──────────────────────────────────────────────────────────────────────────────
search_btn = st.button(
    "🔍  Fetch & Curate Latest News  (last 24 h)",
    use_container_width=True,
    type="primary",
)

if search_btn or st.session_state.get("last_results"):

    if search_btn:
        all_data:     dict[str, pd.DataFrame] = {}
        raw_curated:  dict[str, list[dict]]   = {}

        progress = st.progress(0, text="Starting…")
        status   = st.empty()

        for i, cat in enumerate(selected_cats):
            pct = (i + 1) / len(selected_cats)

            # ── Step 1: fetch real articles ───────────────
            status.markdown(f"📡 **Fetching real articles** for *{cat}*…")
            progress.progress(pct * 0.5, text=f"NewsAPI → {cat}")
            raw = fetch_real_articles(cat, news_api_key, trusted_only)

            if not raw:
                status.markdown(f"⚠️ No articles found for *{cat}* — skipping.")
                continue

            # ── Step 2: Claude curation ───────────────────
            status.markdown(f"🤖 **Claude is curating** *{cat}* ({len(raw)} articles → top {max_per_cat})…")
            progress.progress(pct * 0.5 + 0.5 * (1 / len(selected_cats)), text=f"Claude → {cat}")

            curated = curate_with_claude(
                cat, raw, claude_api_key, max_per_cat, TRUSTED_DOMAINS[cat]
            )

            # If Claude curation failed, fall back to raw NewsAPI results
            if not curated:
                status.markdown(f"⚠️ Claude curation failed for *{cat}* — using raw NewsAPI results.")
                curated = _build_fallback(raw, cat, max_per_cat)

            raw_curated[cat] = curated
            df = articles_to_df(curated, cat)
            if not df.empty:
                all_data[cat] = df

        progress.empty()
        status.empty()

        st.session_state["last_results"] = all_data
        st.session_state["last_raw"]     = raw_curated

    # ── Restore session ───────────────────────────────────────────────────────
    all_data    = st.session_state.get("last_results", {})
    raw_curated = st.session_state.get("last_raw",     {})

    # ── Metrics ───────────────────────────────────────────────────────────────
    total      = sum(len(df) for df in all_data.values())
    trusted_n  = sum((df["Trusted"] == "YES").sum() for df in all_data.values()) if all_data else 0
    cats_found = len(all_data)

    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-card"><div class="value">{total}</div><div class="label">Total Articles</div></div>
        <div class="metric-card"><div class="value">{trusted_n}</div><div class="label">Trusted Sources</div></div>
        <div class="metric-card"><div class="value">{cats_found}</div><div class="label">Categories</div></div>
        <div class="metric-card"><div class="value">24h</div><div class="label">Time Window</div></div>
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
        st.warning("No articles found. Check your API keys or try different categories.")
    else:
        for cat in selected_cats:
            if cat not in all_data or all_data[cat].empty:
                continue

            icon     = CATEGORY_ICONS.get(cat, "📌")
            articles = raw_curated.get(cat, [])

            st.markdown(f'<div class="section-title">{icon} {cat}</div>', unsafe_allow_html=True)

            for art in articles:
                title   = art.get("title",   "No title")
                source  = art.get("source",  "Unknown")
                url     = art.get("url",     "#")
                pub     = art.get("published", "")
                summary = art.get("summary", "")
                trusted = art.get("trusted", False)

                # Format time-ago
                try:
                    dt      = datetime.strptime(pub[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                    age     = datetime.now(timezone.utc) - dt
                    h, m    = int(age.total_seconds()//3600), int((age.total_seconds()%3600)//60)
                    age_str = f"{h}h {m}m ago" if h else f"{m}m ago"
                except Exception:
                    age_str = pub[:16].replace("T", " ") + " UTC" if pub else "recent"

                trust_cls   = "badge-trust-yes" if trusted else "badge-trust-no"
                trust_label = "✅ Trusted"       if trusted else "⚠️ Unverified"

                summary_html = (
                    f"<p style='color:#94a3b8;font-size:.85rem;margin:.6rem 0 .4rem 0'>"
                    f"{summary[:240]}{'…' if len(summary)>240 else ''}</p>"
                ) if summary else ""

                st.markdown(f"""
                <div class="news-card">
                    <p class="headline">{title}</p>
                    <div class="meta">
                        <span class="badge badge-source">🗞️ {source}</span>
                        <span class="badge badge-cat">{icon} {cat}</span>
                        <span class="badge badge-time">🕐 {age_str}</span>
                        <span class="badge {trust_cls}">{trust_label}</span>
                    </div>
                    {summary_html}
                    <a href="{url}" target="_blank">🔗 Read full article →</a>
                </div>
                """, unsafe_allow_html=True)
