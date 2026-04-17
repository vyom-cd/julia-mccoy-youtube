# Daily YouTube Comment Report — SOP

## Objective

Scrape comments from Julia McCoy's YouTube channel daily, classify them into 8 categories, and email an HTML summary report.

## Pipeline Sequence

```
1. Scrape → Apify API fetches comments from @JuliaMcCoy's recent videos (last 7 days)
2. Classify → Pattern-based classifier assigns each comment a category
3. Report → HTML email sent via N8N webhook + full interactive report on GitHub Pages
```

## How to Run

### Automatic (daily)
GitHub Actions runs at 9:00 AM IST (3:30 AM UTC) via `.github/workflows/daily_report.yml`.

### Manual
```bash
python tools/run_pipeline.py
```

### Individual steps
```bash
python -c "from tools.scrape_comments import run; run()"
python -c "from tools.classify_comments import run; run()"
python -c "from tools.send_report import run; run()"
```

### Re-classify everything
```bash
python tools/classify_comments.py --reset
```

## Required Environment Variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `APIFY_API_TOKEN` | `.env` + GitHub Secrets | Apify API for YouTube scraping |
| `N8N_WEBHOOK_URL` | `.env` + GitHub Secrets | N8N webhook for email delivery |
| `REPORT_RECIPIENTS` | `.env` + GitHub Secrets | Comma-separated email addresses |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Apify quota exceeded | Check usage at console.apify.com |
| Comments not appearing | Video may have comments disabled |
| Webhook fails | Check N8N workflow is active at n8n.callreceptionist.com |
| Classification wrong | Edit patterns in `tools/classify_comments.py`, run with `--reset` |
| Tests failing | `pytest tests/ -v` to see which test fails |
