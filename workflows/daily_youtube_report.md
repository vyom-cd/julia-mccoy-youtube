# Daily YouTube Comment Report

## Objective
Scrape comments from Julia McCoy's recent YouTube videos, classify them by category, and email an HTML report.

## Pipeline Sequence
1. Run `tools/scrape_comments.py` — fetches videos from last 7 days, scrapes all comments
2. Run `tools/classify_comments.py` — classifies unclassified comments (keywords first, Claude AI second)
3. Run `tools/send_report.py` — builds HTML report and emails it

## Required Environment
- `.env` must contain: YOUTUBE_API_KEY, ANTHROPIC_API_KEY, GMAIL_ADDRESS, GMAIL_APP_PASSWORD, REPORT_RECIPIENTS
- Python dependencies installed from `requirements.txt`

## Running Manually
```bash
python tools/run_pipeline.py
```

## Scheduled Execution
Configured via Claude Code `/schedule` to run daily.

## Troubleshooting
- **YouTube API quota exceeded**: Free tier allows 10,000 units/day. Each search costs 100 units, each commentThreads.list costs 1 unit. Reduce `days_back` if hitting limits.
- **Comments disabled on video**: Handled gracefully — returns empty list, logs a message.
- **Gmail auth fails**: Ensure App Password is used (not regular password). Enable 2FA on the Gmail account first.
- **Claude API error**: Check ANTHROPIC_API_KEY is valid. Haiku is used for cost efficiency.
