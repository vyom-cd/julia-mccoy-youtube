# Tools reference

Per-script documentation for everything under `tools/`. Each tool has a `run()` function used by the orchestrator and is also directly invokable.

---

## `run_pipeline.py`

Orchestrator. Chains scrape → classify → report with per-step logging.

**Run:**
```bash
python tools/run_pipeline.py
```

**Behavior:**
- Logs each step with `[INFO] STEP: <name>` headers.
- On exception: logs the error, prints the traceback, exits with status 1.
- No CLI flags; configuration is entirely via `.env` and `config/`.

---

## `scrape_comments.py`

Fetches recent videos and their comments via Apify.

**Run:**
```bash
python -c "from tools.scrape_comments import run; run()"
```

**Public API:**
```python
run(db_path: str | None = None, days_back: int = 7) -> None
```

**Required env:**
- `APIFY_API_TOKEN`

**Config inputs:**
- `config/channels.json` — list of `{id, name, handle}` entries.

**Apify actors used:**
| Actor | Purpose |
|-------|---------|
| `streamers/youtube-scraper` | Lists recent videos for a channel handle. |
| `streamers/youtube-comments-scraper` | Pulls up to 500 comments per video. |

**Writes:** `channels`, `videos`, `comments` tables (`INSERT OR IGNORE`).

**Notes:**
- Videos older than `days_back` are skipped.
- Empty `video_id` comments are dropped.
- Batched `commit()` — one per video collection, one per comments collection.

---

## `classify_comments.py`

Assigns a category to every comment that lacks one.

**Run:**
```bash
# Default — Claude Haiku with pattern fallback
python -c "from tools.classify_comments import run; run()"

# Pattern-only (no API call)
python -c "from tools.classify_comments import run; run(use_ai=False)"

# Re-classify everything
python tools/classify_comments.py --reset
```

**Public API:**
```python
run(db_path: str | None = None, reset: bool = False, use_ai: bool = True) -> None

# Helpers exposed for scripts / notebooks:
classify_comment(text: str, categories: list | None = None) -> tuple[str, str]
classify_by_keywords(text: str, categories: list) -> str | None
ai_classify_batch(comments_batch: list, api_key: str) -> dict[int, str] | None
get_unclassified_for_review(db_path=None) -> list[dict]
apply_classifications(classifications: dict[str, str], db_path=None) -> None
```

**Required env:**
- `ANTHROPIC_API_KEY` — optional; falls back to pattern matching if absent.

**Config inputs:**
- `config/categories.json` — additional keyword hints per category.

**Classification flow:**
1. Load unclassified comments.
2. If `use_ai` and API key present — batches of 20 sent to Claude Haiku 4.5; response parsed as JSON.
3. Any comment not returned by the model falls through to pattern matching (`classify_comment`).
4. Writes `category`, `classification_method`, `classified_at`.

**`classification_method` values:**
| Method | Meaning |
|--------|---------|
| `ai` | Claude returned a category. |
| `pattern` | Matched a hardcoded phrase/regex list. |
| `keyword` | Matched a `config/categories.json` keyword. |
| `manual` | Set via `apply_classifications()`. |

---

## `send_report.py`

Builds the HTML digest and dispatches it through the N8N webhook.

**Run:**
```bash
python -c "from tools.send_report import run; run()"
```

**Public API:**
```python
run(db_path: str | None = None) -> None
build_report_data(conn, since_date: str | None = None) -> dict
render_report(data: dict, template_dir: str = "templates") -> str
send_email(html_content: str, subject: str | None = None) -> None
```

**Required env:**
- `N8N_WEBHOOK_URL`
- `REPORT_RECIPIENTS`

**Template:**
- `templates/report.html` — compact email; top 3 comments per category per video, plus CTA to the interactive report.

**Data shape passed to the template:**
```python
{
  "report_date":     "April 23, 2026",
  "generated_at":    "2026-04-23 12:01 UTC",
  "total_comments":  1234,
  "video_count":     12,
  "category_count":  8,
  "category_totals": OrderedDict(cat -> {"icon": "…", "count": N}),
  "videos":          OrderedDict(video_id -> {title, url, total_comments, categories}),
  "all_categories":  [list of 8 category names],
  "category_icons":  {cat: icon},
  "full_report_url": "https://vyom-cd.github.io/julia-mccoy-youtube/report/?v=…",
}
```

**Security:** all user-supplied text (`text`, `author`, `video_title`) is passed through `html.escape()` before templating, and Jinja autoescape is on.

**Delivery:** one JSON POST to `N8N_WEBHOOK_URL` containing `{to, subject, html}`. The N8N scenario handles the actual SMTP send.

---

## `db.py`

SQLite layer. Every other tool imports from here.

**Public API:**
```python
get_connection(db_path: str | None = None) -> sqlite3.Connection
init_db(conn) -> None
insert_channel(conn, id, name, handle) -> None
insert_video(conn, id, channel_id, title, published_at, url) -> None
insert_comment(conn, id, video_id, author, text, likes, published_at, is_reply, parent_id) -> None
commit(conn) -> None
get_unclassified_comments(conn) -> list[dict]
update_comment_category(conn, comment_id, category, method) -> None
get_classified_comments_for_report(conn, since_date: str | None = None) -> list[dict]
```

**Defaults:**
- `DB_PATH = "data/comments.db"`
- `PRAGMA foreign_keys = ON`
- `PRAGMA journal_mode = WAL`

**Schema:** see [ARCHITECTURE.md#database-schema](../ARCHITECTURE.md#database-schema).

**Write semantics:**
- All inserts use `INSERT OR IGNORE` — idempotent on re-run.
- `insert_*` helpers do **not** commit. Call `commit(conn)` explicitly after a batch.
- `update_comment_category` commits immediately (per-row update).

---

## Testing

```bash
pytest tests/ -v
```

Test modules: `test_scrape.py`, `test_classify.py`, `test_report.py`, `test_db.py`, `test_pipeline.py`.
