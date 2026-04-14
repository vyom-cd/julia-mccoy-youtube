# YouTube Comment Monitor — Design Spec

## Overview

A daily pipeline that scrapes comments from Julia McCoy's YouTube channel, categorizes them using keyword rules and AI classification, stores them in a local SQLite database, and emails a formatted HTML report.

Built within the WAT framework (Workflows, Agents, Tools).

## Goals

- Surface actionable feedback (mistakes, complaints, ideas, questions) from YouTube comments daily
- Categorize every comment automatically with high accuracy
- Deliver a clean, scannable HTML email report grouped by category
- Support future expansion: more channels, trend tracking, new categories

## Architecture

Three Python tools run in sequence, connected by a shared SQLite database:

```
Claude Code /schedule (daily cron)
         |
[1] scrape_comments.py  ->  [2] classify_comments.py  ->  [3] send_report.py
         |                           |                           |
    YouTube Data API          Keywords + Claude API         HTML email via Gmail
         |                           |                           |
      SQLite DB <--------------- SQLite DB -----------------> SQLite DB
```

### Tool 1: scrape_comments.py

- Reads channel list from `config/channels.json`
- Fetches videos published in the last 7 days via YouTube Data API v3
- Fetches all comments (including replies) for each video
- Deduplicates by YouTube comment ID — skips already-scraped comments
- Stores videos and comments in SQLite

### Tool 2: classify_comments.py

- Reads unclassified comments from DB (where `category IS NULL`)
- Loads category definitions and keyword rules from `config/categories.json`
- Phase 1 — Keyword rules: pattern-match obvious categories (spam links, questions ending in `?`, etc.)
- Phase 2 — AI classification: sends remaining comments to Claude API with category definitions as context
- Writes `category`, `classification_method`, and `classified_at` back to DB

### Tool 3: send_report.py

- Queries comments classified today (or since last report)
- Renders HTML email using Jinja2 template from `templates/report.html`
- Sends via Gmail SMTP with App Password
- Recipients configured in `.env`

## Data Model

### SQLite Database: `data/comments.db`

**channels**

| Column   | Type      | Notes                        |
|----------|-----------|------------------------------|
| id       | TEXT PK   | YouTube channel ID           |
| name     | TEXT      | Display name                 |
| handle   | TEXT      | e.g. @JuliaMcCoy             |
| added_at | TIMESTAMP | When channel was added       |

**videos**

| Column       | Type      | Notes                        |
|--------------|-----------|------------------------------|
| id           | TEXT PK   | YouTube video ID             |
| channel_id   | TEXT FK   | References channels.id       |
| title        | TEXT      | Video title                  |
| published_at | TIMESTAMP | When video was published     |
| url          | TEXT      | Full YouTube URL             |
| scraped_at   | TIMESTAMP | When we scraped this video   |

**comments**

| Column                 | Type      | Notes                              |
|------------------------|-----------|------------------------------------|
| id                     | TEXT PK   | YouTube comment ID                 |
| video_id               | TEXT FK   | References videos.id               |
| author                 | TEXT      | Commenter display name             |
| text                   | TEXT      | Comment body                       |
| likes                  | INTEGER   | Like count                         |
| published_at           | TIMESTAMP | When comment was posted            |
| is_reply               | BOOLEAN   | True if reply to another comment   |
| parent_id              | TEXT      | Parent comment ID (nullable)       |
| category               | TEXT      | Null until classified              |
| classification_method  | TEXT      | "keyword" or "ai"                  |
| scraped_at             | TIMESTAMP | When we scraped this comment       |
| classified_at          | TIMESTAMP | When classification happened       |

## Comment Categories

| Category      | Description                              |
|---------------|------------------------------------------|
| mistake       | Points out an error in the video         |
| good_point    | Highlights something valuable            |
| idea          | Suggests something new                   |
| question      | Asks for clarification or help           |
| testimonial   | Shares a success story or praise         |
| complaint     | Negative feedback or frustration         |
| spam          | Irrelevant, promotional, or bot content  |
| other         | Doesn't fit any category above           |

Categories are configurable via `config/categories.json`. New categories can be added without code changes.

### Classification Flow

1. **Keyword rules** run first — fast, free, handles obvious cases (spam with links, questions with `?`, etc.)
2. **Claude API** handles the rest — sends unclassified comments with category definitions for accurate classification
3. `classification_method` field tracks which method was used (useful for tuning keyword rules over time)

## Email Report

**Subject:** `YouTube Comments Report -- Apr 14, 2026`

**Structure:**

```
Summary Bar
  Total comments | New today | Across N videos

Category Sections (sorted by priority: mistakes, complaints, ideas, questions first)
  Category Name (count)
    Video: "Title"
      Comment by @user -- "text" (N likes)

Footer
  Generated at [timestamp]
```

- Mistakes and complaints surface first (most actionable)
- Spam collapsed/hidden by default
- Comments grouped by video within each category
- Like count shown for prioritization
- Read-only digest, no response functionality

**Delivery:** Gmail SMTP with App Password via Python `smtplib`.

## File Structure

```
julia mccoy youtube/
  tools/
    scrape_comments.py
    classify_comments.py
    send_report.py
    db.py
  workflows/
    daily_youtube_report.md
  data/
    comments.db
  config/
    categories.json
    channels.json
  templates/
    report.html
  .env
  .gitignore
  requirements.txt
```

## Dependencies

```
google-api-python-client    # YouTube Data API v3
anthropic                   # Claude API for classification
jinja2                      # HTML email templating
python-dotenv               # Load .env variables
```

No external services beyond YouTube API, Claude API, and Gmail SMTP. SQLite and smtplib are Python stdlib.

## Environment Variables (.env)

```
YOUTUBE_API_KEY=
ANTHROPIC_API_KEY=
GMAIL_ADDRESS=
GMAIL_APP_PASSWORD=
REPORT_RECIPIENTS=
```

## Scheduling

Claude Code `/schedule` runs the full pipeline daily. The schedule triggers execution of all three tools in sequence.

## Future Expansion Points

- **More channels:** Add entries to `config/channels.json`
- **New categories:** Add to `config/categories.json` with keyword rules
- **Trend tracking:** Query historical data from SQLite for patterns over time
- **New comment detection:** `scraped_at` timestamps enable "only new since last run" filtering
- **Response suggestions:** Could add Claude-generated reply drafts per comment
- **Dashboard:** SQLite data can feed a web UI later
