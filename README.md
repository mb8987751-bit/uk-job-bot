# UK Job Auto-Apply Bot

Automated bot that searches and applies to entry-level remote UK jobs on **LinkedIn** and **Indeed**. Runs on GitHub Actions (free) 3x daily.

## Features

- Searches LinkedIn UK (Easy Apply) and Indeed UK (Quick Apply)
- Filters for entry-level, remote, UK-listed jobs
- AI-generated tailored cover letters via Google Gemini (free tier)
- SQLite deduplication (never applies twice)
- GitHub Actions scheduling (3x daily, free)
- CSV export of all applications

## Setup

1. **Fork/clone this repo**

2. **Get a Gemini API key** (free)
   - Go to https://aistudio.google.com/apikey
   - Click "Get API Key" and create one

3. **Add GitHub Secrets** (Settings → Secrets and variables → Actions)
   | Secret | Value |
   |--------|-------|
   | LINKEDIN_EMAIL | Your LinkedIn email |
   | LINKEDIN_PASSWORD | Your LinkedIn password |
   | INDEED_EMAIL | Your Indeed email |
   | INDEED_PASSWORD | Your Indeed password |
   | GEMINI_API_KEY | Your Gemini API key |
   | FULL_NAME | Your full name |
   | PHONE | Your phone number |
   | EMAIL | Your email address |
   | CITY | Your city (e.g. London, United Kingdom) |

4. **Configure** config.yaml to adjust keywords, limits, and filters

5. **Enable GitHub Actions** — the bot runs automatically at 8am, 2pm, 8pm UTC

## Local Testing

`ash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # fill in your credentials
python main.py
`

## Customization

Edit config.yaml:
- job_search.linkedin.keywords — job titles to search
- job_search.indeed.keywords — job titles to search
- ot_settings.max_daily_applications — daily cap (default: 50)
- ot_settings.headless — set alse to see the browser

## ⚠️ Disclaimer

Automated job applications may violate LinkedIn/Indeed terms of service. Use at your own risk. This tool is for educational purposes.
