# Architecture

## WAT framework

The project is structured around three layers — **Workflows, Agents, Tools** — to separate probabilistic reasoning from deterministic execution.

| Layer | Location | Responsibility |
|-------|----------|----------------|
| Workflows | `workflows/*.md` | Plain-language SOPs describing objective, inputs, tool sequence, outputs, and edge cases. |
| Agents | Claude Code session | Reads the workflow, orchestrates tools in the right order, handles failures, asks clarifying questions. |
| Tools | `tools/*.py` | Deterministic Python scripts. API calls, DB writes, template rendering — fast, testable, boring. |

Keeping execution out of the model avoids cascading accuracy loss across multi-step pipelines. The model decides *what to do*; the scripts decide *how*.

## Pipeline

```
 ┌──────────────────┐     ┌─────────────────────┐     ┌────────────────────┐
 │ scrape_comments  │────▶│ classify_comments   │────▶│ send_report        │
 │ (Apify → SQLite) │     │ (Claude → SQLite)   │     │ (Jinja → N8N email)│
 └──────────────────┘     └─────────────────────┘     └────────────────────┘
         │                         │                           │
         ▼                         ▼                           ▼
    data/comments.db         data/comments.db           docs/report/index.html
                                                         (GitHub Pages)
```

`tools/run_pipeline.py` chains the three steps. Each step is also invokable standalone.

### Scrape (`scrape_comments.py`)
1. Loads monitored channels from `config/channels.json`.
2. Calls Apify actor `streamers/youtube-scraper` to list videos published within the last 7 days.
3. Calls Apify actor `streamers/youtube-comments-scraper` to fetch up to 500 comments per video.
4. Upserts channels, videos, and comments into SQLite with `INSERT OR IGNORE` — safe to re-run.

### Classify (`classify_comments.py`)
1. Selects `comments WHERE category IS NULL`.
2. **Primary** — batches of 20 sent to Claude Haiku 4.5. Returns JSON array of `{index, category}`.
3. **Fallback** — any comment the model didn't return is classified by pattern matching (spam terms, testimonial phrases, complaint terms, question patterns, etc.).
4. Writes `category`, `classification_method` (`ai` | `pattern` | `keyword` | `manual`), and `classified_at`.

Force re-classification with `run(reset=True)` or `python tools/classify_comments.py --reset`.

### Report (`send_report.py`)
1. Queries classified comments with a join to `videos`.
2. Escapes all user-generated text (XSS safeguard) and groups by video, then by category.
3. Renders `templates/report.html` into a compact email with a summary card and top 3 comments per category.
4. POSTs the HTML to the N8N webhook along with recipients and subject — N8N handles the actual email send.
5. The GitHub Actions workflow separately renders `templates/report_web.html` into `docs/report/index.html` and commits it, publishing the full interactive version to GitHub Pages.

## Database schema

SQLite at `data/comments.db`. WAL mode + foreign keys enabled.

```sql
channels (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    handle      TEXT,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

videos (
    id            TEXT PRIMARY KEY,
    channel_id    TEXT NOT NULL REFERENCES channels(id),
    title         TEXT NOT NULL,
    published_at  TIMESTAMP NOT NULL,
    url           TEXT NOT NULL,
    scraped_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

comments (
    id                     TEXT PRIMARY KEY,
    video_id               TEXT NOT NULL REFERENCES videos(id),
    author                 TEXT NOT NULL,
    text                   TEXT NOT NULL,
    likes                  INTEGER DEFAULT 0,
    published_at           TIMESTAMP NOT NULL,
    is_reply               BOOLEAN DEFAULT 0,
    parent_id              TEXT,
    category               TEXT,            -- one of 8 categories, NULL until classified
    classification_method  TEXT,            -- ai | pattern | keyword | manual
    scraped_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    classified_at          TIMESTAMP
)
```

The database is cached between GitHub Actions runs (`actions/cache@v4`) so comment history and classifications persist across daily runs.

## Categories

Eight mutually exclusive labels:

| Category | Meaning |
|----------|---------|
| `mistake` | Comment points out a factual error Julia made. |
| `good_point` | Substantive opinion or discussion about the topic. |
| `idea` | Suggestion for Julia (video topics, improvements). |
| `question` | Asks for clarification, help, or information. |
| `testimonial` | Short direct praise. |
| `complaint` | Negative feedback, hostility, or strong criticism. |
| `spam` | Promotional, bot, scam, gibberish. |
| `other` | Short/neutral, doesn't fit elsewhere. |

Definitions and keyword hints live in `config/categories.json`.

## Deployment

### Scheduling
`.github/workflows/daily_report.yml` runs at `30 3 * * *` UTC (9:00 AM IST). The job also exposes `workflow_dispatch` for manual triggers.

### Secrets (GitHub repo → Settings → Secrets)
- `APIFY_API_TOKEN`
- `ANTHROPIC_API_KEY`
- `N8N_WEBHOOK_URL`
- `REPORT_RECIPIENTS`

### GitHub Pages
Repository must be **public**. `docs/.nojekyll` prevents Jekyll processing; the published URL is `https://vyom-cd.github.io/julia-mccoy-youtube/report/`.

## Design decisions

- **SQLite over hosted DB.** Zero infrastructure; the dataset is small (~thousands of comments). Cached between CI runs.
- **Claude Haiku as primary classifier.** 20-comment batches with a JSON-only response. Pattern matching stays in the codebase as a deterministic floor when the API key is absent or the model errors.
- **N8N for email.** Keeps SMTP credentials out of the repo and lets non-code users edit the delivery template.
- **Email digest + GitHub Pages.** The email stays under 10 KB; the full interactive report lives on Pages and is linked from the digest — no bloated inline HTML.
- **Separate templates** (`report.html` for email, `report_web.html` for Pages) so the email can stay compact while the web report is fully interactive.

## Error handling

- `run_pipeline.py` wraps each step in a try/except, logs the traceback, and `sys.exit(1)` on any failure so CI flips red.
- Apify failures (quota, auth) bubble up from the client and stop the pipeline.
- N8N webhook failures (`URLError`, `HTTPError`) are logged and re-raised.
- Database operations use `INSERT OR IGNORE` + explicit `commit()` batching — safe to re-run, no partial writes on duplicates.
