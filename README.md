# 📰 24h News Explorer — Streamlit App

A Streamlit demo app that searches for breaking news published in the **last 24 hours** across multiple categories, filters by trusted/well-known sources, and exports results to a multi-sheet **Excel file**.

---

## Features

| Feature | Details |
|---|---|
| 🔍 Multi-category search | Technology, Finance, Politics, Science, Health, AI/ML, Environment, Sports, Entertainment, Business |
| 🗞️ Trusted sources | Pre-vetted, well-known publishers per category (Reuters, Bloomberg, TechCrunch, BBC, …) |
| 🕐 24 h window | Only articles published in the last 24 hours via GNews API |
| 📥 Excel export | One sheet per category + summary sheet, auto-formatted |
| 🎨 Dark UI | Styled cards showing title, source badge, time ago, trust indicator |

---

## Setup

### 1. Clone / enter the project

```bash
cd /home/user/webapp
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Get a free GNews API key

Sign up at **https://gnews.io** → copy your API token.  
The free tier allows **100 requests/day**.

### 4. Run the app

```bash
streamlit run app.py --server.port 8501
```

Then open the public URL shown in the terminal.

---

## Usage

1. Paste your **GNews API key** in the left sidebar.
2. Choose **categories** to search.
3. Adjust the number of articles per category (3–10).
4. Optionally toggle **"Trusted sources only"**.
5. Click **🔍 Search Latest News (last 24 h)**.
6. Browse the cards — each shows title, source, time ago, and trust badge.
7. Click **📥 Export All Results to Excel** to download a `.xlsx` file.

---

## Excel Export Structure

| Sheet | Content |
|---|---|
| `All Articles` | Combined results from all categories |
| `Technology` | Articles for Technology only |
| `Finance & Markets` | Articles for Finance & Markets only |
| *(one per selected category)* | … |

Columns: **Category · Title · Source · Published · Description · URL · Trusted**

---

## Trusted Sources by Category

| Category | Sources |
|---|---|
| Technology | TechCrunch, Wired, The Verge, Ars Technica, Engadget |
| Finance & Markets | Bloomberg, Reuters, FT, WSJ, CNBC |
| Politics | Reuters, BBC, AP News, Politico, The Guardian |
| Science | Scientific American, Nature, New Scientist, ScienceDaily |
| Health & Medicine | WHO, WebMD, Healthline, MedScape, STAT News |
| Business | Bloomberg, Forbes, Business Insider, Reuters, Fortune |
| AI & Machine Learning | VentureBeat, TechCrunch, Wired, TNW, DeepMind |
| Environment | The Guardian, BBC, National Geographic, Carbon Brief |
| Sports | ESPN, BBC, Sky Sports, The Athletic |
| Entertainment | Variety, Hollywood Reporter, Deadline, Rolling Stone |
