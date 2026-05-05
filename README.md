# Julia McCoy YouTube Comment Monitor

Daily pipeline that scrapes comments from Julia McCoy's YouTube channel, classifies them into 8 categories, and delivers an email digest with a link to a full interactive report.

## What it does

1. **Scrape** — Apify pulls comments from `@JuliaMcCoy`'s videos published in the last 7 days.
2. **Classify** — Each comment is tagged with one of 8 categories: `mistake`, `good_point`, `idea`, `question`, `testimonial`, `complaint`, `spam`, `other`. Claude Haiku handles primary classification; a pattern-matching fallback covers anything the model misses.
3. **Report** — An HTML email digest is sent via an N8N webhook, with a CTA linking to the full interactive report hosted on GitHub Pages.

The full pipeline runs daily at 9:00 AM IST via GitHub Actions and can be triggered manually from the Actions tab or locally.

## Quick start

### Prerequisites
- Python 3.12
- Apify account with API token
- Anthropic API key (optional — pipeline falls back to pattern matching)
- N8N webhook configured for email delivery

### Install
```bash
pip install -r requirements.txt
```

### Configure
Create `.env` in the project root:
```
APIFY_API_TOKEN=apify_api_...
ANTHROPIC_API_KEY=sk-ant-...           # optional
N8N_WEBHOOK_URL=https://n8n.../webhook/...
REPORT_RECIPIENTS=user@example.com,other@example.com
```

### Run
```bash
python tools/run_pipeline.py
```

Each step can also be run independently — see [`workflows/daily_youtube_report.md`](workflows/daily_youtube_report.md).

## Project layout

```
.
├── tools/                      # Deterministic Python scripts (execution layer)
│   ├── run_pipeline.py         # Orchestrator — runs scrape → classify → report
│   ├── scrape_comments.py      # Apify YouTube scraper
│   ├── classify_comments.py    # Claude + pattern classifier
│   ├── send_report.py          # HTML email + webhook delivery
│   └── db.py                   # SQLite helpers and schema
├── workflows/                  # Markdown SOPs (instruction layer)
│   └── daily_youtube_report.md
├── config/
│   ├── channels.json           # Channels to monitor
│   └── categories.json         # Classification categories + keywords
├── templates/
│   ├── report.html             # Compact email template
│   └── report_web.html         # Full interactive report (GitHub Pages)
├── docs/
│   └── report/index.html       # Published GitHub Pages report
├── data/
│   └── comments.db             # SQLite database (channels, videos, comments)
├── tests/                      # pytest suite
├── .github/workflows/          # GitHub Actions CI
└── requirements.txt
```

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — WAT framework, pipeline diagram, database schema, design decisions.
- **[docs/TOOLS.md](docs/TOOLS.md)** — Per-script reference: inputs, outputs, CLI flags.
- **[workflows/daily_youtube_report.md](workflows/daily_youtube_report.md)** — Runbook for the daily pipeline.
- **[CHANGELOG.md](CHANGELOG.md)** — Notable changes.

## Tests

```bash
pytest tests/ -v
```

## License

Private project. All rights reserved.
