import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from io import BytesIO

# ─────────────────────────────────────────────
#  Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="📰 24h News Explorer",
    page_icon="📰",
    layout="wide",
)

# ─────────────────────────────────────────────
#  Custom CSS
# ─────────────────────────────────────────────
st.markdown(
    """
    <style>
        /* ---------- global ---------- */
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }

        /* ---------- header banner ---------- */
        .app-header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            border-radius: 16px;
            padding: 2rem 2.5rem;
            margin-bottom: 2rem;
            text-align: center;
        }
        .app-header h1 { color: #e94560; font-size: 2.6rem; margin: 0; }
        .app-header p  { color: #a8b2d8; font-size: 1.05rem; margin-top: .5rem; }

        /* ---------- metric cards ---------- */
        .metric-row { display: flex; gap: 1rem; margin-bottom: 1.5rem; }
        .metric-card {
            flex: 1;
            background: #16213e;
            border: 1px solid #0f3460;
            border-radius: 12px;
            padding: 1rem 1.4rem;
            text-align: center;
        }
        .metric-card .value { font-size: 2rem; font-weight: 700; color: #e94560; }
        .metric-card .label { font-size: .85rem; color: #a8b2d8; margin-top: .2rem; }

        /* ---------- news cards ---------- */
        .news-card {
            background: #16213e;
            border: 1px solid #0f3460;
            border-left: 4px solid #e94560;
            border-radius: 10px;
            padding: 1rem 1.3rem;
            margin-bottom: .9rem;
            transition: border-color .2s;
        }
        .news-card:hover { border-left-color: #f5a623; }
        .news-card .headline {
            color: #e2e8f0;
            font-size: 1rem;
            font-weight: 600;
            line-height: 1.45;
            margin: 0 0 .55rem 0;
        }
        .news-card .meta {
            display: flex;
            flex-wrap: wrap;
            gap: .6rem;
            align-items: center;
        }
        .badge {
            font-size: .72rem;
            padding: .2rem .6rem;
            border-radius: 20px;
            font-weight: 600;
        }
        .badge-source { background: #0f3460; color: #63b3ed; }
        .badge-cat    { background: #2d3748; color: #f6ad55; }
        .badge-time   { background: #1a202c; color: #68d391; }
        .news-card a {
            font-size: .8rem;
            color: #667eea;
            text-decoration: none;
        }
        .news-card a:hover { text-decoration: underline; }

        /* ---------- section title ---------- */
        .section-title {
            color: #e94560;
            font-size: 1.3rem;
            font-weight: 700;
            border-bottom: 2px solid #e94560;
            padding-bottom: .4rem;
            margin-bottom: 1.2rem;
        }

        /* ---------- sidebar ---------- */
        [data-testid="stSidebar"] {
            background: #0d1117;
        }
        [data-testid="stSidebar"] .stMarkdown h3 {
            color: #e94560 !important;
        }

        /* ---------- export button ---------- */
        .stDownloadButton > button {
            background: linear-gradient(135deg, #e94560, #f5a623) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            padding: .55rem 1.2rem !important;
        }
        .stDownloadButton > button:hover { opacity: .85 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────

# Trusted / well-known sources mapped per category
TRUSTED_SOURCES: dict[str, list[str]] = {
    "Technology":         ["techcrunch.com", "wired.com", "theverge.com", "arstechnica.com", "engadget.com"],
    "Finance & Markets":  ["bloomberg.com", "reuters.com", "ft.com", "wsj.com", "cnbc.com"],
    "Politics":           ["reuters.com", "bbc.co.uk", "apnews.com", "politico.com", "theguardian.com"],
    "Science":            ["scientificamerican.com", "nature.com", "newscientist.com", "sciencedaily.com", "livescience.com"],
    "Health & Medicine":  ["who.int", "webmd.com", "healthline.com", "medscape.com", "statnews.com"],
    "Business":           ["bloomberg.com", "forbes.com", "businessinsider.com", "reuters.com", "fortune.com"],
    "AI & Machine Learning": ["venturebeat.com", "techcrunch.com", "wired.com", "thenextweb.com", "deepmind.com"],
    "Environment":        ["theguardian.com", "bbc.co.uk", "nationalgeographic.com", "climatecentral.org", "carbonbrief.org"],
    "Sports":             ["espn.com", "bbc.co.uk", "skysports.com", "theathletic.com", "sportskeeda.com"],
    "Entertainment":      ["variety.com", "hollywoodreporter.com", "deadline.com", "ew.com", "rollingstone.com"],
}

CATEGORY_ICONS: dict[str, str] = {
    "Technology": "💻",
    "Finance & Markets": "📈",
    "Politics": "🏛️",
    "Science": "🔬",
    "Health & Medicine": "🏥",
    "Business": "💼",
    "AI & Machine Learning": "🤖",
    "Environment": "🌿",
    "Sports": "⚽",
    "Entertainment": "🎬",
}

# ─────────────────────────────────────────────
#  GNews API helper
# ─────────────────────────────────────────────

GNEWS_BASE = "https://gnews.io/api/v4/search"

def fetch_news(query: str, api_key: str, max_results: int = 10) -> list[dict]:
    """Call GNews API and return list of article dicts."""
    from_dt = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "q": query,
        "lang": "en",
        "from": from_dt,
        "max": min(max_results, 10),
        "token": api_key,
        "sortby": "publishedAt",
    }
    try:
        resp = requests.get(GNEWS_BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("articles", [])
    except requests.exceptions.HTTPError as e:
        st.error(f"API Error ({resp.status_code}): {e}")
    except requests.exceptions.ConnectionError:
        st.error("Connection error – check your internet connection.")
    except requests.exceptions.Timeout:
        st.error("Request timed out. Please try again.")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
    return []


def source_is_trusted(article: dict, category: str) -> bool:
    """Return True when article source domain matches a trusted source for the category."""
    url = article.get("url", "").lower()
    trusted = TRUSTED_SOURCES.get(category, [])
    return any(src in url for src in trusted)


def articles_to_df(articles: list[dict], category: str) -> pd.DataFrame:
    rows = []
    for art in articles:
        pub = art.get("publishedAt", "")
        try:
            dt = datetime.strptime(pub, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            pub_fmt = dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            pub_fmt = pub
        rows.append(
            {
                "Category":    category,
                "Title":       art.get("title", "N/A"),
                "Source":      art.get("source", {}).get("name", "Unknown"),
                "Published":   pub_fmt,
                "Description": art.get("description", ""),
                "URL":         art.get("url", ""),
                "Trusted":     "YES" if source_is_trusted(art, category) else "NO",
            }
        )
    return pd.DataFrame(rows)


def df_to_excel(dfs: dict[str, pd.DataFrame]) -> bytes:
    """Write one sheet per category and return bytes."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Summary sheet
        all_df = pd.concat(dfs.values(), ignore_index=True) if dfs else pd.DataFrame()
        if not all_df.empty:
            all_df.to_excel(writer, sheet_name="All Articles", index=False)
        # Per-category sheets
        for cat, df in dfs.items():
            if not df.empty:
                safe_name = cat[:31]  # Excel sheet name max 31 chars
                df.to_excel(writer, sheet_name=safe_name, index=False)
        # Auto-fit columns
        for sheet in writer.sheets.values():
            for col in sheet.columns:
                max_len = max((len(str(c.value)) for c in col if c.value), default=10)
                sheet.column_dimensions[col[0].column_letter].width = min(max_len + 4, 80)
    return output.getvalue()


# ─────────────────────────────────────────────
#  Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    api_key = st.text_input(
        "GNews API Key",
        type="password",
        help="Free key at https://gnews.io  –  100 requests/day on the free tier.",
        placeholder="Paste your API key here…",
    )
    st.markdown("---")
    st.markdown("### 📂 Categories")
    all_cats = list(TRUSTED_SOURCES.keys())
    selected_cats = st.multiselect(
        "Select categories to search",
        options=all_cats,
        default=["Technology", "Finance & Markets", "AI & Machine Learning"],
        format_func=lambda c: f"{CATEGORY_ICONS.get(c, '')} {c}",
    )
    st.markdown("---")
    st.markdown("### 🔍 Search Options")
    max_per_cat = st.slider("Articles per category", min_value=3, max_value=10, value=5)
    trusted_only = st.checkbox("Show trusted sources only", value=False)
    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.markdown(
        """
        Fetches news published in the **last 24 hours** via the
        [GNews API](https://gnews.io).

        Trusted sources are pre-vetted, well-known publishers per category.

        Export all results to a multi-sheet **Excel file** with one click.
        """
    )

# ─────────────────────────────────────────────
#  Header
# ─────────────────────────────────────────────
st.markdown(
    """
    <div class="app-header">
        <h1>📰 24h News Explorer</h1>
        <p>Search breaking news across categories · Verified sources · Export to Excel</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
#  Run Search
# ─────────────────────────────────────────────
if not api_key:
    st.info("👈  Enter your **GNews API key** in the sidebar to get started. You can get a free key at https://gnews.io")
    st.stop()

if not selected_cats:
    st.warning("⚠️ Please select at least one category from the sidebar.")
    st.stop()

search_btn = st.button("🔍 Search Latest News (last 24 h)", use_container_width=True, type="primary")

if search_btn or st.session_state.get("last_results"):

    if search_btn:
        all_data: dict[str, pd.DataFrame] = {}
        raw_articles: dict[str, list[dict]] = {}

        progress = st.progress(0, text="Fetching articles…")
        for i, cat in enumerate(selected_cats):
            progress.progress((i + 1) / len(selected_cats), text=f"Searching: {cat}…")
            articles = fetch_news(cat, api_key, max_results=max_per_cat)
            if trusted_only:
                articles = [a for a in articles if source_is_trusted(a, cat)]
            raw_articles[cat] = articles
            df = articles_to_df(articles, cat)
            if not df.empty:
                all_data[cat] = df
        progress.empty()

        st.session_state["last_results"] = all_data
        st.session_state["last_raw"]     = raw_articles

    # ── Restore from session ──────────────────
    all_data     = st.session_state.get("last_results", {})
    raw_articles = st.session_state.get("last_raw", {})

    # ── Summary metrics ───────────────────────
    total_articles = sum(len(df) for df in all_data.values())
    trusted_count  = sum(
        (df["Trusted"] == "YES").sum() for df in all_data.values()
    ) if all_data else 0
    categories_found = len(all_data)

    st.markdown(
        f"""
        <div class="metric-row">
            <div class="metric-card">
                <div class="value">{total_articles}</div>
                <div class="label">Total Articles</div>
            </div>
            <div class="metric-card">
                <div class="value">{trusted_count}</div>
                <div class="label">Trusted Sources</div>
            </div>
            <div class="metric-card">
                <div class="value">{categories_found}</div>
                <div class="label">Categories Found</div>
            </div>
            <div class="metric-card">
                <div class="value">24h</div>
                <div class="label">Time Window</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Export button ─────────────────────────
    if all_data:
        excel_bytes = df_to_excel(all_data)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        st.download_button(
            label="📥 Export All Results to Excel",
            data=excel_bytes,
            file_name=f"news_24h_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.markdown("---")

    # ── Article cards per category ────────────
    if not all_data:
        st.warning("No articles found. Try different categories or check your API key.")
    else:
        for cat in selected_cats:
            if cat not in all_data or all_data[cat].empty:
                continue

            icon = CATEGORY_ICONS.get(cat, "📌")
            articles = raw_articles.get(cat, [])
            if trusted_only:
                articles = [a for a in articles if source_is_trusted(a, cat)]

            st.markdown(f'<div class="section-title">{icon} {cat}</div>', unsafe_allow_html=True)

            for art in articles:
                title  = art.get("title", "No title")
                source = art.get("source", {}).get("name", "Unknown")
                url    = art.get("url", "#")
                pub    = art.get("publishedAt", "")
                desc   = art.get("description", "")
                trust  = "✅ Trusted" if source_is_trusted(art, cat) else "⚠️ Unverified"

                try:
                    dt     = datetime.strptime(pub, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    age    = datetime.now(timezone.utc) - dt
                    hours  = int(age.total_seconds() // 3600)
                    mins   = int((age.total_seconds() % 3600) // 60)
                    age_str = f"{hours}h {mins}m ago" if hours else f"{mins}m ago"
                except Exception:
                    age_str = pub

                st.markdown(
                    f"""
                    <div class="news-card">
                        <p class="headline">{title}</p>
                        <div class="meta">
                            <span class="badge badge-source">🗞️ {source}</span>
                            <span class="badge badge-cat">{icon} {cat}</span>
                            <span class="badge badge-time">🕐 {age_str}</span>
                            <span class="badge" style="background:#1c3a2b;color:#68d391">{trust}</span>
                        </div>
                        {"<p style='color:#94a3b8;font-size:.85rem;margin:.6rem 0 .4rem 0'>" + desc[:200] + ("…" if len(desc)>200 else "") + "</p>" if desc else ""}
                        <a href="{url}" target="_blank">🔗 Read full article →</a>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
