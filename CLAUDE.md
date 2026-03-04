# News Automation — Project Context

## Purpose
This tool exists to help the user **stay informed about current events and developments
around the world**, organised by the categories they care about (Stocks, Fiats, Indexes,
Regional, Country Credit, Alternative Lending, Fintech, Start-up, Sustainable Finance,
Marketing, Entertainment).

## Core design philosophy

### The 24h window (hard cap: 36h) is intentional
The primary search window is the **last 24 hours**. The 36-hour cap exists only as a
safety buffer — not as a target. The goal is the **most recent and relevant** updates,
not the widest coverage possible. Older articles dilute the value of the digest.

Do NOT relax the time window to fill slots. An empty category is better than a
category padded with stale content.

### Relevance > Volume
For high-impact market categories (Stocks, Fiats, Indexes, Country Credit), what is
happening RIGHT NOW in markets matters more than finding exactly N articles.
A single breaking geopolitical story that is moving markets is worth more than five
routine earnings updates.

### No fabrication, no padding
If no real articles exist within the window, return empty. The auto-fallback retries
with relaxed source filters (but never a wider time window).

## Design decisions to preserve

| Decision | Rationale |
|----------|-----------|
| 36h hard cap enforced in Python (`_within_max_age`) | Prevent stale content even if Claude ignores the prompt rule |
| 3-step search for HIGH_IMPACT_CATEGORIES | Detect breaking news before selecting, rank by market importance tier |
| String concatenation (not f-string) for card HTML | Prevents blank lines that break Streamlit's CommonMark HTML block parser |
| Empty array allowed from Claude | Triggers Python auto-fallback; better than fabricating articles |
| `verified_score` coerced with `try/int()` | Claude sometimes returns scores as strings |
| `&` in URLs escaped via `html_mod.escape()` | Required for valid HTML attributes (query strings with `&`) |

## Categories and their scope
See `CATEGORY_GEO_FOCUS` in `app.py` for the detailed editorial scope of each category.
Key rules:
- **Fiats**: always include USD/SGD and USD/IDR spot context; cover CBDC developments
- **Stocks**: global scope, but no FX/macro/index-level articles (those belong elsewhere)
- **Indexes**: MSCI actions, ASEAN economic data, and gold records are in scope
- **Marketing**: explicitly excludes financial market and economic data articles
- **Entertainment**: Singapore-angle required; no generic global entertainment
