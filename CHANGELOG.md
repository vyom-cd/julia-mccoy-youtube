# Changelog

Notable changes to the Julia McCoy YouTube comment monitor. Based on git history.

## [Unreleased]

### Added
- Full documentation set: `README.md`, `ARCHITECTURE.md`, `docs/TOOLS.md`, `CHANGELOG.md`.

---

## April 2026

### Infrastructure
- **feat:** persist SQLite DB between GitHub Actions runs via `actions/cache@v4`; auto-update GitHub Pages report on every run. *(f7c65d4)*
- **ci:** daily GitHub Actions workflow — cron `30 3 * * *` UTC (9:00 AM IST), manual `workflow_dispatch` trigger. *(befa81d)*
- **fix:** unpin `apify-client` version for Python 3.12 compatibility. *(6c0b087)*
- **fix:** add `.nojekyll` so GitHub Pages skips Jekyll processing. *(6d65a4f)*
- **fix:** add root `index.html` for GitHub Pages navigation. *(6616cb0)*

### Reporting
- **feat:** email template shows per-video category pills + top comments. *(f836f53)*
- **fix:** compact email template — summary card + link to full interactive report; email size reduced from 256 KB to ~10 KB. *(5b3620c, a053b63)*
- **feat:** email shows top 3 comments per category with CTA linking to interactive report. *(d11579e)*
- **feat:** HTML email report builder with Gmail delivery (later migrated to N8N webhook). *(3548e38)*

### Classification
- **refactor:** consolidate multiple classifier scripts into one `classify_comments.py`; fix DB safety issues; add error handling around AI calls. *(03504ec)*
- **feat:** comment classifier with keyword rules + Claude Haiku AI primary, pattern-matching fallback. *(64b8e2d)*

### Scraping
- **feat:** switch scraper to Apify (`streamers/youtube-comments-scraper`); add First Movers UI pieces; manual classification path. *(cbf7faa)*
- **feat:** original YouTube comment scraper with pagination and reply support. *(3ae5bed)*

### Pipeline
- **feat:** `run_pipeline.py` orchestrator + `workflows/daily_youtube_report.md` SOP. *(7a52986)*
- **test:** integration test covering full classify-and-report flow. *(203b8d2)*

### Foundation
- **feat:** database layer — schema + helper functions. *(69aafc4)*
- **chore:** project scaffolding with config files (`channels.json`, `categories.json`, `requirements.txt`). *(9dd092a)*
