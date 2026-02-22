"""
24h News Explorer
─────────────────
Uses Claude with the built-in `web_search` tool (Anthropic API).
Claude searches the live web for real news published in the last 24 hours,
returns verified headlines, real URLs, real sources and editorial summaries.
Only ONE API key needed: your Anthropic (Claude) key.
"""

import json
import re
from datetime import datetime, timezone
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
#  CSS
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container{padding-top:2rem;padding-bottom:2rem}

    .app-header{
        background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);
        border-radius:16px;padding:2rem 2.5rem;margin-bottom:2rem;text-align:center
    }
    .app-header h1{color:#e94560;font-size:2.6rem;margin:0}
    .app-header p{color:#a8b2d8;font-size:1.05rem;margin-top:.5rem}

    .metric-row{display:flex;gap:1rem;margin-bottom:1.5rem}
    .metric-card{
        flex:1;background:#16213e;border:1px solid #0f3460;border-radius:12px;
        padding:1rem 1.4rem;text-align:center
    }
    .metric-card .value{font-size:2rem;font-weight:700;color:#e94560}
    .metric-card .label{font-size:.85rem;color:#a8b2d8;margin-top:.2rem}

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

    .section-title{
        color:#e94560;font-size:1.3rem;font-weight:700;
        border-bottom:2px solid #e94560;padding-bottom:.4rem;margin-bottom:1.2rem
    }

    [data-testid="stSidebar"]{background:#0d1117}
    [data-testid="stSidebar"] .stMarkdown h3{color:#e94560!important}

    .stDownloadButton>button{
        background:linear-gradient(135deg,#e94560,#f5a623)!important;
        color:white!important;border:none!important;border-radius:8px!important;
        font-weight:600!important;padding:.55rem 1.2rem!important
    }
    .stDownloadButton>button:hover{opacity:.85!important}

    .pill-claude{
        display:inline-block;
        background:linear-gradient(135deg,#6B46C1,#9F7AEA);
        color:white;font-size:.7rem;font-weight:700;
        padding:.2rem .8rem;border-radius:20px;letter-spacing:.05em
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

# Trusted source names per category (used in prompt + trust badge)
TRUSTED_SOURCES: dict[str, list[str]] = {
    "Technology":            ["TechCrunch", "Wired", "The Verge", "Ars Technica", "Engadget", "MIT Technology Review"],
    "Finance & Markets":     ["Bloomberg", "Reuters", "Financial Times", "Wall Street Journal", "CNBC", "The Economist"],
    "Politics":              ["Reuters", "BBC", "AP News", "Politico", "The Guardian", "NPR"],
    "Science":               ["Scientific American", "Nature", "New Scientist", "Science Daily", "Live Science", "National Geographic"],
    "Health & Medicine":     ["WHO", "WebMD", "Healthline", "STAT News", "MedPage Today", "The Lancet"],
    "Business":              ["Bloomberg", "Forbes", "Business Insider", "Reuters", "Fortune", "Harvard Business Review"],
    "AI & Machine Learning": ["VentureBeat", "TechCrunch", "Wired", "MIT Technology Review", "The Next Web", "IEEE Spectrum"],
    "Environment":           ["The Guardian", "BBC", "National Geographic", "Carbon Brief", "Climate Central", "Inside Climate News"],
    "Sports":                ["ESPN", "BBC Sport", "Sky Sports", "The Athletic", "Sports Illustrated", "Reuters"],
    "Entertainment":         ["Variety", "Hollywood Reporter", "Deadline", "Entertainment Weekly", "Rolling Stone", "Pitchfork"],
}

# Search queries Claude uses when web-searching per category
CATEGORY_SEARCH_QUERIES: dict[str, str] = {
    "Technology":            "latest technology news today",
    "Finance & Markets":     "financial markets economy news today",
    "Politics":              "politics government news today",
    "Science":               "science research discovery news today",
    "Health & Medicine":     "health medicine medical news today",
    "Business":              "business corporate news today",
    "AI & Machine Learning": "artificial intelligence AI news today",
    "Environment":           "environment climate news today",
    "Sports":                "sports news today",
    "Entertainment":         "entertainment movies music news today",
}

CLAUDE_MODEL = "claude-opus-4-5"

# ──────────────────────────────────────────────────────────────────────────────
#  Core: ask Claude to web-search and return structured news
# ──────────────────────────────────────────────────────────────────────────────

def fetch_news_with_search(
    category: str,
    claude_api_key: str,
    n: int,
    trusted_only: bool,
) -> list[dict]:
    """
    Ask Claude to search the live web for the latest news in `category`.
    Claude uses the built-in web_search tool, then returns a JSON array
    of real articles with verified URLs.
    """
    today        = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    trusted_str  = ", ".join(TRUSTED_SOURCES.get(category, []))
    search_query = CATEGORY_SEARCH_QUERIES.get(category, f"{category} news today")
    source_rule  = (
        f"ONLY include articles from these trusted sources: {trusted_str}."
        if trusted_only
        else f"Preferred trusted sources (prioritise these): {trusted_str}."
    )

    prompt = f"""Today is {today}.

Use the web_search tool to find the {n} most important news stories about **{category}** published in the last 24 hours.

Search query to use: "{search_query}"

{source_rule}

After searching, return ONLY a raw JSON array (no markdown, no explanation) with exactly {n} items.
Each item must have these fields:
  "title"     : exact headline from the article (string)
  "source"    : name of the news outlet (string)
  "published" : publication date/time if available, else "{today}" (string)
  "url"       : the real, full URL of the article — MUST be a working link you found (string)
  "summary"   : your 1-2 sentence summary of the story (string)
  "trusted"   : true if the source is in [{trusted_str}], else false (boolean)

Rules:
- Every URL must be a real link you actually retrieved via web_search — never invent URLs.
- If you find fewer than {n} articles, return however many you found.
- Do NOT wrap in markdown code fences — return the raw JSON array only.
"""

    try:
        client = anthropic.Anthropic(api_key=claude_api_key)

        # Define the web_search tool for Claude
        tools = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
            }
        ]

        messages = [{"role": "user", "content": prompt}]

        # Agentic loop: keep going until Claude stops using tools
        while True:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                tools=tools,
                messages=messages,
            )

            # If Claude is done (no more tool calls), extract the JSON
            if response.stop_reason == "end_turn":
                break

            # If Claude wants to use a tool, add its response to messages
            # and continue the loop (Anthropic handles tool execution server-side)
            if response.stop_reason == "tool_use":
                # Add assistant's response to message history
                messages.append({"role": "assistant", "content": response.content})

                # Build tool_result blocks for each tool_use block
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        # With server-side tools, the result comes back automatically
                        # We just need to acknowledge and let the loop continue
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "Search completed.",
                        })

                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
                continue

            # Any other stop reason — break out
            break

        # Extract text from the final response
        raw = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw += block.text

        raw = raw.strip()

        # Strip accidental markdown fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$",        "", raw, flags=re.MULTILINE)
        raw = raw.strip()

        # Extract JSON array (handle cases where Claude adds preamble text)
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            st.warning(f"⚠️ Claude did not return a JSON array for **{category}**.")
            return []

        articles = json.loads(match.group())
        if not isinstance(articles, list):
            raise ValueError("Expected JSON array")

        return articles[:n]

    except anthropic.AuthenticationError:
        st.error("❌ **Invalid Claude API key.** Please check your key — it should start with `sk-ant-`.")
        return []
    except anthropic.RateLimitError:
        st.error("⏳ **Claude rate limit reached.** Wait a moment and try again.")
        return []
    except anthropic.APIError as e:
        # Check if web_search tool is not available on this tier
        err_str = str(e)
        if "web_search" in err_str.lower() or "tool" in err_str.lower():
            st.error(
                f"❌ **Web search not available** on your Claude plan for **{category}**. "
                "The `web_search` tool requires an Anthropic API account with tool access enabled. "
                f"Details: {e}"
            )
        else:
            st.error(f"❌ Claude API error for **{category}**: {e}")
        return []
    except json.JSONDecodeError as e:
        st.warning(f"⚠️ Could not parse Claude's response for **{category}**: {e}")
        return []
    except Exception as e:
        st.error(f"❌ Unexpected error for **{category}**: {e}")
        return []


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def articles_to_df(articles: list[dict], category: str) -> pd.DataFrame:
    rows = []
    for a in articles:
        rows.append({
            "Category":  category,
            "Title":     a.get("title",     "N/A"),
            "Source":    a.get("source",    "Unknown"),
            "Published": a.get("published", ""),
            "Summary":   a.get("summary",   ""),
            "URL":       a.get("url",       ""),
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


def format_age(pub: str) -> str:
    """Convert ISO timestamp to '2h 15m ago' style string."""
    try:
        dt  = datetime.strptime(pub[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - dt
        h   = int(age.total_seconds() // 3600)
        m   = int((age.total_seconds() % 3600) // 60)
        if h > 48:
            return pub[:10]
        return f"{h}h {m}m ago" if h else f"{m}m ago"
    except Exception:
        return pub[:10] if pub else "recent"


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
        default=["Technology", "Finance & Markets", "AI & Machine Learning"],
        format_func=lambda c: f"{CATEGORY_ICONS.get(c, '')} {c}",
    )

    st.markdown("---")
    st.markdown("### 🔍 Options")
    max_per_cat  = st.slider("Articles per category", 3, 10, 5)
    trusted_only = st.checkbox("Trusted sources only", value=False)

    st.markdown("---")
    st.markdown("### ℹ️ How it works")
    st.markdown("""
**One key. Real news.**

Claude uses its built-in **web search** tool to find articles published in the last **24 hours**, returning real headlines, working URLs, real sources and editorial summaries — all via your single Claude API key.
    """)

# ──────────────────────────────────────────────────────────────────────────────
#  Header
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>📰 24h News Explorer</h1>
    <p>Claude searches the live web &nbsp;·&nbsp; Real articles &nbsp;·&nbsp; Working links &nbsp;·&nbsp; Export to Excel</p>
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
    "🔍  Search Latest News via Claude  (last 24 h)",
    use_container_width=True,
    type="primary",
)

if search_btn or st.session_state.get("last_results"):

    if search_btn:
        all_data:    dict[str, pd.DataFrame] = {}
        raw_articles: dict[str, list[dict]]  = {}

        progress = st.progress(0, text="Starting web search…")
        status   = st.empty()

        for i, cat in enumerate(selected_cats):
            pct = (i + 1) / len(selected_cats)
            icon = CATEGORY_ICONS.get(cat, "📌")

            status.markdown(f"🌐 **Claude is searching the web** for *{icon} {cat}* news…")
            progress.progress(pct, text=f"Searching: {cat}…")

            articles = fetch_news_with_search(
                category       = cat,
                claude_api_key = claude_api_key,
                n              = max_per_cat,
                trusted_only   = trusted_only,
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
        st.warning("No articles found. Check your API key or try different categories.")
    else:
        for cat in selected_cats:
            if cat not in all_data or all_data[cat].empty:
                continue

            icon     = CATEGORY_ICONS.get(cat, "📌")
            articles = raw_articles.get(cat, [])

            st.markdown(f'<div class="section-title">{icon} {cat}</div>', unsafe_allow_html=True)

            for art in articles:
                title   = art.get("title",   "No title")
                source  = art.get("source",  "Unknown")
                url     = art.get("url",     "#")
                pub     = art.get("published", "")
                summary = art.get("summary", "")
                trusted = art.get("trusted", False)

                age_str     = format_age(pub)
                trust_cls   = "badge-trust-yes" if trusted else "badge-trust-no"
                trust_label = "✅ Trusted"       if trusted else "⚠️ Unverified"

                summary_html = (
                    f"<p style='color:#94a3b8;font-size:.85rem;margin:.6rem 0 .4rem 0'>"
                    f"{summary[:240]}{'…' if len(summary) > 240 else ''}</p>"
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
