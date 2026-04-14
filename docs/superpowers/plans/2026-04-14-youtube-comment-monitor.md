# YouTube Comment Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily pipeline that scrapes YouTube comments, classifies them, and emails an HTML report.

**Architecture:** Three sequential Python tools (scrape, classify, report) connected by a shared SQLite database. Keyword rules handle obvious classifications, Claude API handles ambiguous ones. Gmail SMTP delivers the report.

**Tech Stack:** Python 3, google-api-python-client, anthropic, jinja2, python-dotenv, SQLite, smtplib

---

## File Structure

```
julia mccoy youtube/
  tools/
    db.py                     # DB connection, schema creation, helper queries
    scrape_comments.py        # YouTube API: fetch videos + comments
    classify_comments.py      # Keyword rules + Claude API classification
    send_report.py            # Query DB, render HTML, send email
  config/
    categories.json           # Category definitions + keyword rules
    channels.json             # YouTube channels to monitor
  templates/
    report.html               # Jinja2 HTML email template
  workflows/
    daily_youtube_report.md   # SOP for the pipeline
  data/                       # SQLite DB lives here (gitignored)
  tests/
    test_db.py
    test_scrape.py
    test_classify.py
    test_report.py
  .env                        # API keys (gitignored)
  .gitignore
  requirements.txt
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env`
- Create: `config/channels.json`
- Create: `config/categories.json`

- [ ] **Step 1: Initialize git repo**

Run: `cd "/c/Users/VJ/Desktop/Office/julia mccoy youtube" && git init`
Expected: Initialized empty Git repository

- [ ] **Step 2: Create requirements.txt**

```
google-api-python-client==2.169.0
anthropic==0.52.0
jinja2==3.1.6
python-dotenv==1.1.0
```

- [ ] **Step 3: Create .gitignore**

```
.env
data/
__pycache__/
*.pyc
.tmp/
token.json
credentials.json
```

- [ ] **Step 4: Create .env template**

```
YOUTUBE_API_KEY=
ANTHROPIC_API_KEY=
GMAIL_ADDRESS=
GMAIL_APP_PASSWORD=
REPORT_RECIPIENTS=
```

User must fill in actual values.

- [ ] **Step 5: Create config/channels.json**

```json
[
  {
    "id": "UCkTR0JsnRkSJR5dYSjCmMcA",
    "name": "Julia McCoy",
    "handle": "@JuliaMcCoy"
  }
]
```

Note: Channel ID to be confirmed from YouTube. This is a placeholder structure — the actual ID will be resolved during implementation.

- [ ] **Step 6: Create config/categories.json**

```json
{
  "categories": [
    {
      "name": "mistake",
      "description": "Points out an error in the video",
      "keywords": ["wrong", "incorrect", "error", "actually it's", "you said", "correction", "not true", "mistake"]
    },
    {
      "name": "good_point",
      "description": "Highlights something valuable in the video",
      "keywords": ["great point", "well said", "exactly", "so true", "nailed it", "brilliant", "insightful"]
    },
    {
      "name": "idea",
      "description": "Suggests something new or a topic to cover",
      "keywords": ["you should", "would be cool", "idea:", "suggestion", "how about", "could you cover", "please make a video"]
    },
    {
      "name": "question",
      "description": "Asks for clarification or help",
      "keywords": ["how do", "what is", "can you explain", "where do", "why does", "is there"],
      "patterns": ["\\?\\s*$"]
    },
    {
      "name": "testimonial",
      "description": "Shares a success story or praises the content",
      "keywords": ["worked for me", "tried this", "thanks to you", "changed my", "helped me", "life changing", "game changer"]
    },
    {
      "name": "complaint",
      "description": "Negative feedback or frustration",
      "keywords": ["didn't work", "waste of time", "disappointed", "misleading", "clickbait", "not helpful", "terrible"]
    },
    {
      "name": "spam",
      "description": "Irrelevant, promotional, or bot content",
      "keywords": ["check out my", "subscribe to", "free money", "click here", "giveaway", "dm me", "whatsapp"],
      "patterns": ["https?://(?!youtube\\.com|youtu\\.be)\\S+"]
    },
    {
      "name": "other",
      "description": "Does not fit any category above"
    }
  ]
}
```

- [ ] **Step 7: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: Successfully installed all packages

- [ ] **Step 8: Commit**

```bash
git add requirements.txt .gitignore config/
git commit -m "chore: project scaffolding with config files"
```

---

### Task 2: Database Layer (db.py)

**Files:**
- Create: `tools/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db.py
import os
import sqlite3
import pytest
from tools.db import get_connection, init_db, insert_channel, insert_video, insert_comment, get_unclassified_comments, update_comment_category

TEST_DB = "data/test_comments.db"


@pytest.fixture(autouse=True)
def clean_db():
    os.makedirs("data", exist_ok=True)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_init_db_creates_tables():
    conn = get_connection(TEST_DB)
    init_db(conn)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "channels" in tables
    assert "videos" in tables
    assert "comments" in tables
    conn.close()


def test_insert_channel():
    conn = get_connection(TEST_DB)
    init_db(conn)
    insert_channel(conn, id="UC123", name="Test Channel", handle="@test")
    cursor = conn.execute("SELECT id, name, handle FROM channels WHERE id='UC123'")
    row = cursor.fetchone()
    assert row == ("UC123", "Test Channel", "@test")
    conn.close()


def test_insert_channel_duplicate_skips():
    conn = get_connection(TEST_DB)
    init_db(conn)
    insert_channel(conn, id="UC123", name="Test Channel", handle="@test")
    insert_channel(conn, id="UC123", name="Test Channel", handle="@test")
    cursor = conn.execute("SELECT COUNT(*) FROM channels WHERE id='UC123'")
    assert cursor.fetchone()[0] == 1
    conn.close()


def test_insert_video():
    conn = get_connection(TEST_DB)
    init_db(conn)
    insert_channel(conn, id="UC123", name="Test", handle="@test")
    insert_video(
        conn,
        id="vid1",
        channel_id="UC123",
        title="Test Video",
        published_at="2026-04-10T00:00:00Z",
        url="https://youtube.com/watch?v=vid1",
    )
    cursor = conn.execute("SELECT id, title FROM videos WHERE id='vid1'")
    row = cursor.fetchone()
    assert row == ("vid1", "Test Video")
    conn.close()


def test_insert_comment():
    conn = get_connection(TEST_DB)
    init_db(conn)
    insert_channel(conn, id="UC123", name="Test", handle="@test")
    insert_video(conn, id="vid1", channel_id="UC123", title="Test", published_at="2026-04-10T00:00:00Z", url="https://youtube.com/watch?v=vid1")
    insert_comment(
        conn,
        id="comment1",
        video_id="vid1",
        author="User1",
        text="Great video!",
        likes=5,
        published_at="2026-04-10T01:00:00Z",
        is_reply=False,
        parent_id=None,
    )
    cursor = conn.execute("SELECT id, author, text, likes FROM comments WHERE id='comment1'")
    row = cursor.fetchone()
    assert row == ("comment1", "User1", "Great video!", 5)
    conn.close()


def test_get_unclassified_comments():
    conn = get_connection(TEST_DB)
    init_db(conn)
    insert_channel(conn, id="UC123", name="Test", handle="@test")
    insert_video(conn, id="vid1", channel_id="UC123", title="Test", published_at="2026-04-10T00:00:00Z", url="https://youtube.com/watch?v=vid1")
    insert_comment(conn, id="c1", video_id="vid1", author="A", text="Hello", likes=0, published_at="2026-04-10T01:00:00Z", is_reply=False, parent_id=None)
    insert_comment(conn, id="c2", video_id="vid1", author="B", text="World", likes=0, published_at="2026-04-10T02:00:00Z", is_reply=False, parent_id=None)
    comments = get_unclassified_comments(conn)
    assert len(comments) == 2
    assert comments[0]["id"] == "c1"
    conn.close()


def test_update_comment_category():
    conn = get_connection(TEST_DB)
    init_db(conn)
    insert_channel(conn, id="UC123", name="Test", handle="@test")
    insert_video(conn, id="vid1", channel_id="UC123", title="Test", published_at="2026-04-10T00:00:00Z", url="https://youtube.com/watch?v=vid1")
    insert_comment(conn, id="c1", video_id="vid1", author="A", text="Hello", likes=0, published_at="2026-04-10T01:00:00Z", is_reply=False, parent_id=None)
    update_comment_category(conn, comment_id="c1", category="question", method="keyword")
    cursor = conn.execute("SELECT category, classification_method FROM comments WHERE id='c1'")
    row = cursor.fetchone()
    assert row == ("question", "keyword")
    comments = get_unclassified_comments(conn)
    assert len(comments) == 0
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.db'`

- [ ] **Step 3: Write db.py implementation**

```python
# tools/db.py
import sqlite3
from datetime import datetime, timezone


DB_PATH = "data/comments.db"


def get_connection(db_path=None):
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS channels (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            handle TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            channel_id TEXT NOT NULL,
            title TEXT NOT NULL,
            published_at TIMESTAMP NOT NULL,
            url TEXT NOT NULL,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (channel_id) REFERENCES channels(id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL,
            author TEXT NOT NULL,
            text TEXT NOT NULL,
            likes INTEGER DEFAULT 0,
            published_at TIMESTAMP NOT NULL,
            is_reply BOOLEAN DEFAULT 0,
            parent_id TEXT,
            category TEXT,
            classification_method TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            classified_at TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos(id)
        );
    """)
    conn.commit()


def insert_channel(conn, id, name, handle):
    conn.execute(
        "INSERT OR IGNORE INTO channels (id, name, handle) VALUES (?, ?, ?)",
        (id, name, handle),
    )
    conn.commit()


def insert_video(conn, id, channel_id, title, published_at, url):
    conn.execute(
        "INSERT OR IGNORE INTO videos (id, channel_id, title, published_at, url) VALUES (?, ?, ?, ?, ?)",
        (id, channel_id, title, published_at, url),
    )
    conn.commit()


def insert_comment(conn, id, video_id, author, text, likes, published_at, is_reply, parent_id):
    conn.execute(
        """INSERT OR IGNORE INTO comments
        (id, video_id, author, text, likes, published_at, is_reply, parent_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (id, video_id, author, text, likes, published_at, is_reply, parent_id),
    )
    conn.commit()


def get_unclassified_comments(conn):
    cursor = conn.execute(
        "SELECT id, video_id, author, text, likes, published_at FROM comments WHERE category IS NULL ORDER BY published_at"
    )
    return [dict(row) for row in cursor.fetchall()]


def update_comment_category(conn, comment_id, category, method):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE comments SET category = ?, classification_method = ?, classified_at = ? WHERE id = ?",
        (category, method, now, comment_id),
    )
    conn.commit()


def get_classified_comments_for_report(conn, since_date=None):
    query = """
        SELECT c.id, c.video_id, c.author, c.text, c.likes, c.category,
               c.classification_method, c.published_at, c.classified_at,
               v.title as video_title, v.url as video_url
        FROM comments c
        JOIN videos v ON c.video_id = v.id
        WHERE c.category IS NOT NULL
    """
    params = []
    if since_date:
        query += " AND c.classified_at >= ?"
        params.append(since_date)
    query += " ORDER BY c.category, v.title, c.likes DESC"
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_db.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tools/db.py tests/test_db.py
git commit -m "feat: database layer with schema and helper functions"
```

---

### Task 3: YouTube Comment Scraper (scrape_comments.py)

**Files:**
- Create: `tools/scrape_comments.py`
- Create: `tests/test_scrape.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scrape.py
import os
import json
import pytest
from unittest.mock import MagicMock, patch
from tools.scrape_comments import load_channels, fetch_recent_videos, fetch_comments_for_video

TEST_DB = "data/test_comments.db"


@pytest.fixture(autouse=True)
def clean_db():
    os.makedirs("data", exist_ok=True)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_load_channels():
    channels = load_channels("config/channels.json")
    assert isinstance(channels, list)
    assert len(channels) >= 1
    assert "id" in channels[0]
    assert "name" in channels[0]


def test_fetch_recent_videos():
    mock_youtube = MagicMock()
    mock_youtube.search().list().execute.return_value = {
        "items": [
            {
                "id": {"videoId": "vid1"},
                "snippet": {
                    "title": "Test Video",
                    "publishedAt": "2026-04-10T00:00:00Z",
                },
            }
        ]
    }
    videos = fetch_recent_videos(mock_youtube, channel_id="UC123", days_back=7)
    assert len(videos) == 1
    assert videos[0]["id"] == "vid1"
    assert videos[0]["title"] == "Test Video"


def test_fetch_comments_for_video():
    mock_youtube = MagicMock()
    mock_youtube.commentThreads().list().execute.return_value = {
        "items": [
            {
                "id": "thread1",
                "snippet": {
                    "topLevelComment": {
                        "id": "comment1",
                        "snippet": {
                            "authorDisplayName": "User1",
                            "textDisplay": "Great video!",
                            "likeCount": 5,
                            "publishedAt": "2026-04-10T01:00:00Z",
                        },
                    },
                    "totalReplyCount": 1,
                },
                "replies": {
                    "comments": [
                        {
                            "id": "reply1",
                            "snippet": {
                                "authorDisplayName": "User2",
                                "textDisplay": "I agree!",
                                "likeCount": 1,
                                "publishedAt": "2026-04-10T02:00:00Z",
                                "parentId": "comment1",
                            },
                        }
                    ]
                },
            }
        ],
    }
    comments = fetch_comments_for_video(mock_youtube, video_id="vid1")
    assert len(comments) == 2
    assert comments[0]["id"] == "comment1"
    assert comments[0]["is_reply"] is False
    assert comments[1]["id"] == "reply1"
    assert comments[1]["is_reply"] is True
    assert comments[1]["parent_id"] == "comment1"


def test_fetch_comments_handles_disabled_comments():
    mock_youtube = MagicMock()
    from googleapiclient.errors import HttpError
    import httplib2
    resp = httplib2.Response({"status": "403"})
    mock_youtube.commentThreads().list().execute.side_effect = HttpError(resp, b'{"error": {"errors": [{"reason": "commentsDisabled"}]}}')
    comments = fetch_comments_for_video(mock_youtube, video_id="vid1")
    assert comments == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scrape.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.scrape_comments'`

- [ ] **Step 3: Write scrape_comments.py implementation**

```python
# tools/scrape_comments.py
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from tools.db import get_connection, init_db, insert_channel, insert_video, insert_comment

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


def load_channels(config_path="config/channels.json"):
    with open(config_path, "r") as f:
        return json.load(f)


def get_youtube_client(api_key=None):
    key = api_key or YOUTUBE_API_KEY
    if not key:
        raise ValueError("YOUTUBE_API_KEY not set in .env")
    return build("youtube", "v3", developerKey=key)


def fetch_recent_videos(youtube, channel_id, days_back=7):
    since = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
    videos = []
    request = youtube.search().list(
        part="id,snippet",
        channelId=channel_id,
        publishedAfter=since,
        order="date",
        type="video",
        maxResults=50,
    )
    response = request.execute()
    for item in response.get("items", []):
        videos.append({
            "id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "published_at": item["snippet"]["publishedAt"],
            "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
        })
    return videos


def fetch_comments_for_video(youtube, video_id):
    comments = []
    try:
        next_page_token = None
        while True:
            request = youtube.commentThreads().list(
                part="snippet,replies",
                videoId=video_id,
                maxResults=100,
                pageToken=next_page_token,
            )
            response = request.execute()
            for item in response.get("items", []):
                top = item["snippet"]["topLevelComment"]
                comments.append({
                    "id": top["id"],
                    "author": top["snippet"]["authorDisplayName"],
                    "text": top["snippet"]["textDisplay"],
                    "likes": top["snippet"]["likeCount"],
                    "published_at": top["snippet"]["publishedAt"],
                    "is_reply": False,
                    "parent_id": None,
                })
                for reply in item.get("replies", {}).get("comments", []):
                    comments.append({
                        "id": reply["id"],
                        "author": reply["snippet"]["authorDisplayName"],
                        "text": reply["snippet"]["textDisplay"],
                        "likes": reply["snippet"]["likeCount"],
                        "published_at": reply["snippet"]["publishedAt"],
                        "is_reply": True,
                        "parent_id": reply["snippet"]["parentId"],
                    })
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
    except HttpError as e:
        if "commentsDisabled" in str(e):
            return []
        raise
    return comments


def run(db_path=None, days_back=7):
    conn = get_connection(db_path)
    init_db(conn)
    youtube = get_youtube_client()
    channels = load_channels()
    total_comments = 0
    for channel in channels:
        insert_channel(conn, id=channel["id"], name=channel["name"], handle=channel.get("handle", ""))
        videos = fetch_recent_videos(youtube, channel_id=channel["id"], days_back=days_back)
        print(f"Found {len(videos)} recent videos for {channel['name']}")
        for video in videos:
            insert_video(
                conn,
                id=video["id"],
                channel_id=channel["id"],
                title=video["title"],
                published_at=video["published_at"],
                url=video["url"],
            )
            comments = fetch_comments_for_video(youtube, video_id=video["id"])
            for comment in comments:
                insert_comment(
                    conn,
                    id=comment["id"],
                    video_id=video["id"],
                    author=comment["author"],
                    text=comment["text"],
                    likes=comment["likes"],
                    published_at=comment["published_at"],
                    is_reply=comment["is_reply"],
                    parent_id=comment["parent_id"],
                )
            total_comments += len(comments)
            print(f"  Scraped {len(comments)} comments from: {video['title']}")
    conn.close()
    print(f"\nTotal comments scraped: {total_comments}")


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scrape.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tools/scrape_comments.py tests/test_scrape.py
git commit -m "feat: YouTube comment scraper with pagination and reply support"
```

---

### Task 4: Comment Classifier (classify_comments.py)

**Files:**
- Create: `tools/classify_comments.py`
- Create: `tests/test_classify.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_classify.py
import os
import json
import pytest
from unittest.mock import MagicMock, patch
from tools.classify_comments import load_categories, classify_by_keywords, classify_by_ai, classify_comment
from tools.db import get_connection, init_db, insert_channel, insert_video, insert_comment, get_unclassified_comments

TEST_DB = "data/test_comments.db"


@pytest.fixture(autouse=True)
def clean_db():
    os.makedirs("data", exist_ok=True)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_load_categories():
    categories = load_categories("config/categories.json")
    assert isinstance(categories, list)
    names = [c["name"] for c in categories]
    assert "mistake" in names
    assert "spam" in names
    assert "other" in names


def test_classify_by_keywords_question_mark():
    categories = load_categories("config/categories.json")
    result = classify_by_keywords("How do I use this tool?", categories)
    assert result == "question"


def test_classify_by_keywords_spam():
    categories = load_categories("config/categories.json")
    result = classify_by_keywords("Check out my channel for free stuff http://spam.com/free", categories)
    assert result == "spam"


def test_classify_by_keywords_mistake():
    categories = load_categories("config/categories.json")
    result = classify_by_keywords("You said the wrong thing at 3:20, actually it's different", categories)
    assert result == "mistake"


def test_classify_by_keywords_no_match():
    categories = load_categories("config/categories.json")
    result = classify_by_keywords("Nice video", categories)
    assert result is None


def test_classify_by_ai():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="testimonial")]
    )
    categories = load_categories("config/categories.json")
    result = classify_by_ai(mock_client, "This changed my life, I tried it and got amazing results!", categories)
    assert result == "testimonial"


def test_classify_by_ai_falls_back_to_other():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="unknown_category")]
    )
    categories = load_categories("config/categories.json")
    result = classify_by_ai(mock_client, "Random text", categories)
    assert result == "other"


def test_classify_comment_uses_keyword_first():
    categories = load_categories("config/categories.json")
    mock_client = MagicMock()
    category, method = classify_comment("What is this?", categories, mock_client)
    assert category == "question"
    assert method == "keyword"
    mock_client.messages.create.assert_not_called()


def test_classify_comment_falls_to_ai():
    categories = load_categories("config/categories.json")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="good_point")]
    )
    category, method = classify_comment("I really appreciate the depth here", categories, mock_client)
    assert category == "good_point"
    assert method == "ai"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_classify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.classify_comments'`

- [ ] **Step 3: Write classify_comments.py implementation**

```python
# tools/classify_comments.py
import json
import os
import re

import anthropic
from dotenv import load_dotenv

from tools.db import get_connection, init_db, get_unclassified_comments, update_comment_category

load_dotenv()


def load_categories(config_path="config/categories.json"):
    with open(config_path, "r") as f:
        data = json.load(f)
    return data["categories"]


def classify_by_keywords(text, categories):
    text_lower = text.lower()
    for cat in categories:
        if cat["name"] == "other":
            continue
        for keyword in cat.get("keywords", []):
            if keyword.lower() in text_lower:
                return cat["name"]
        for pattern in cat.get("patterns", []):
            if re.search(pattern, text, re.IGNORECASE):
                return cat["name"]
    return None


def classify_by_ai(client, text, categories):
    category_descriptions = "\n".join(
        f'- "{cat["name"]}": {cat["description"]}'
        for cat in categories
    )
    prompt = f"""Classify this YouTube comment into exactly one category. Reply with ONLY the category name, nothing else.

Categories:
{category_descriptions}

Comment: "{text}"

Category:"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
        messages=[{"role": "user", "content": prompt}],
    )
    result = response.content[0].text.strip().lower().replace('"', "")
    valid_names = {cat["name"] for cat in categories}
    if result in valid_names:
        return result
    return "other"


def classify_comment(text, categories, ai_client):
    keyword_result = classify_by_keywords(text, categories)
    if keyword_result:
        return keyword_result, "keyword"
    ai_result = classify_by_ai(ai_client, text, categories)
    return ai_result, "ai"


def run(db_path=None):
    conn = get_connection(db_path)
    init_db(conn)
    categories = load_categories()
    client = anthropic.Anthropic()
    comments = get_unclassified_comments(conn)
    print(f"Found {len(comments)} unclassified comments")
    keyword_count = 0
    ai_count = 0
    for comment in comments:
        category, method = classify_comment(comment["text"], categories, client)
        update_comment_category(conn, comment_id=comment["id"], category=category, method=method)
        if method == "keyword":
            keyword_count += 1
        else:
            ai_count += 1
    conn.close()
    print(f"Classified: {keyword_count} by keywords, {ai_count} by AI")


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_classify.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tools/classify_comments.py tests/test_classify.py
git commit -m "feat: comment classifier with keyword rules and Claude AI fallback"
```

---

### Task 5: HTML Email Report (send_report.py + template)

**Files:**
- Create: `templates/report.html`
- Create: `tools/send_report.py`
- Create: `tests/test_report.py`

- [ ] **Step 1: Create the Jinja2 HTML email template**

```html
<!-- templates/report.html -->
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; color: #1a1a1a; }
  .container { max-width: 700px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
  .header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #ffffff; padding: 32px; }
  .header h1 { margin: 0 0 8px 0; font-size: 24px; font-weight: 700; }
  .header .date { opacity: 0.8; font-size: 14px; }
  .summary { display: flex; gap: 16px; padding: 20px 32px; background: #f8f9fa; border-bottom: 1px solid #e9ecef; }
  .stat { text-align: center; flex: 1; }
  .stat .number { font-size: 28px; font-weight: 700; color: #1a1a2e; }
  .stat .label { font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px; }
  .category-section { padding: 24px 32px; border-bottom: 1px solid #f0f0f0; }
  .category-header { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
  .category-icon { font-size: 20px; }
  .category-name { font-size: 18px; font-weight: 600; }
  .category-count { background: #e9ecef; color: #495057; font-size: 12px; padding: 2px 8px; border-radius: 10px; }
  .video-group { margin-bottom: 16px; }
  .video-title { font-size: 13px; color: #6c757d; margin-bottom: 8px; font-weight: 500; }
  .video-title a { color: #6c757d; text-decoration: none; }
  .video-title a:hover { color: #1a1a2e; }
  .comment { background: #f8f9fa; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px; }
  .comment-author { font-weight: 600; font-size: 13px; color: #1a1a2e; }
  .comment-text { font-size: 14px; line-height: 1.5; margin-top: 4px; color: #333; }
  .comment-meta { font-size: 11px; color: #999; margin-top: 4px; }
  .spam-section { opacity: 0.5; }
  .spam-section .category-header { cursor: pointer; }
  .footer { padding: 20px 32px; text-align: center; font-size: 12px; color: #999; background: #f8f9fa; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>YouTube Comments Report</h1>
    <div class="date">{{ report_date }}</div>
  </div>

  <div class="summary">
    <div class="stat">
      <div class="number">{{ total_comments }}</div>
      <div class="label">Total Comments</div>
    </div>
    <div class="stat">
      <div class="number">{{ video_count }}</div>
      <div class="label">Videos</div>
    </div>
    <div class="stat">
      <div class="number">{{ category_count }}</div>
      <div class="label">Categories</div>
    </div>
  </div>

  {% for cat_name, cat_data in categories.items() %}
  <div class="category-section {% if cat_name == 'spam' %}spam-section{% endif %}">
    <div class="category-header">
      <span class="category-icon">{{ cat_data.icon }}</span>
      <span class="category-name">{{ cat_name | replace('_', ' ') | title }}</span>
      <span class="category-count">{{ cat_data.count }}</span>
    </div>
    {% for video_title, video_comments in cat_data.videos.items() %}
    <div class="video-group">
      <div class="video-title"><a href="{{ video_comments[0].video_url }}">{{ video_title }}</a></div>
      {% for comment in video_comments %}
      <div class="comment">
        <div class="comment-author">{{ comment.author }}</div>
        <div class="comment-text">{{ comment.text }}</div>
        <div class="comment-meta">{{ comment.likes }} likes</div>
      </div>
      {% endfor %}
    </div>
    {% endfor %}
  </div>
  {% endfor %}

  <div class="footer">
    Generated at {{ generated_at }} | Powered by WAT Framework
  </div>
</div>
</body>
</html>
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_report.py
import os
import pytest
from unittest.mock import patch, MagicMock
from tools.send_report import build_report_data, render_report
from tools.db import get_connection, init_db, insert_channel, insert_video, insert_comment, update_comment_category

TEST_DB = "data/test_comments.db"


@pytest.fixture(autouse=True)
def clean_db():
    os.makedirs("data", exist_ok=True)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def seed_db(conn):
    insert_channel(conn, id="UC123", name="Test", handle="@test")
    insert_video(conn, id="vid1", channel_id="UC123", title="Test Video", published_at="2026-04-10T00:00:00Z", url="https://youtube.com/watch?v=vid1")
    insert_comment(conn, id="c1", video_id="vid1", author="Alice", text="You said it wrong at 2:00", likes=3, published_at="2026-04-10T01:00:00Z", is_reply=False, parent_id=None)
    insert_comment(conn, id="c2", video_id="vid1", author="Bob", text="Great insight!", likes=10, published_at="2026-04-10T02:00:00Z", is_reply=False, parent_id=None)
    insert_comment(conn, id="c3", video_id="vid1", author="Spammer", text="Check out my channel http://spam.com", likes=0, published_at="2026-04-10T03:00:00Z", is_reply=False, parent_id=None)
    update_comment_category(conn, "c1", "mistake", "keyword")
    update_comment_category(conn, "c2", "good_point", "ai")
    update_comment_category(conn, "c3", "spam", "keyword")


def test_build_report_data():
    conn = get_connection(TEST_DB)
    init_db(conn)
    seed_db(conn)
    data = build_report_data(conn)
    assert data["total_comments"] == 3
    assert data["video_count"] == 1
    assert "mistake" in data["categories"]
    assert "good_point" in data["categories"]
    assert "spam" in data["categories"]
    assert data["categories"]["mistake"]["count"] == 1
    conn.close()


def test_render_report():
    conn = get_connection(TEST_DB)
    init_db(conn)
    seed_db(conn)
    data = build_report_data(conn)
    html = render_report(data)
    assert "YouTube Comments Report" in html
    assert "Alice" in html
    assert "You said it wrong" in html
    assert "Great insight" in html
    conn.close()


def test_build_report_data_empty_db():
    conn = get_connection(TEST_DB)
    init_db(conn)
    data = build_report_data(conn)
    assert data["total_comments"] == 0
    assert data["video_count"] == 0
    conn.close()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.send_report'`

- [ ] **Step 4: Write send_report.py implementation**

```python
# tools/send_report.py
import os
import smtplib
from collections import OrderedDict
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

from tools.db import get_connection, init_db, get_classified_comments_for_report

load_dotenv()

CATEGORY_ORDER = ["mistake", "complaint", "idea", "question", "testimonial", "good_point", "other", "spam"]
CATEGORY_ICONS = {
    "mistake": "🔴",
    "complaint": "😤",
    "idea": "💡",
    "question": "❓",
    "testimonial": "⭐",
    "good_point": "👍",
    "other": "📦",
    "spam": "🚫",
}


def build_report_data(conn, since_date=None):
    comments = get_classified_comments_for_report(conn, since_date)
    categories = OrderedDict()
    video_ids = set()
    for cat_name in CATEGORY_ORDER:
        cat_comments = [c for c in comments if c["category"] == cat_name]
        if not cat_comments:
            continue
        videos = OrderedDict()
        for c in cat_comments:
            video_ids.add(c["video_id"])
            title = c["video_title"]
            if title not in videos:
                videos[title] = []
            videos[title].append(c)
        categories[cat_name] = {
            "icon": CATEGORY_ICONS.get(cat_name, "📌"),
            "count": len(cat_comments),
            "videos": videos,
        }
    return {
        "report_date": datetime.now(timezone.utc).strftime("%B %d, %Y"),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "total_comments": len(comments),
        "video_count": len(video_ids),
        "category_count": len(categories),
        "categories": categories,
    }


def render_report(data, template_dir="templates"):
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("report.html")
    return template.render(**data)


def send_email(html_content, subject=None):
    gmail_address = os.getenv("GMAIL_ADDRESS")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    recipients = os.getenv("REPORT_RECIPIENTS", "").split(",")
    if not gmail_address or not gmail_password:
        raise ValueError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set in .env")
    if not recipients or recipients == [""]:
        raise ValueError("REPORT_RECIPIENTS must be set in .env")
    if not subject:
        subject = f"YouTube Comments Report — {datetime.now(timezone.utc).strftime('%b %d, %Y')}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_content, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, recipients, msg.as_string())
    print(f"Report sent to: {', '.join(recipients)}")


def run(db_path=None):
    conn = get_connection(db_path)
    init_db(conn)
    data = build_report_data(conn)
    if data["total_comments"] == 0:
        print("No classified comments found. Skipping report.")
        conn.close()
        return
    html = render_report(data)
    send_email(html)
    conn.close()
    print(f"Report sent with {data['total_comments']} comments across {data['video_count']} videos")


if __name__ == "__main__":
    run()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_report.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add tools/send_report.py templates/report.html tests/test_report.py
git commit -m "feat: HTML email report builder with Gmail delivery"
```

---

### Task 6: Pipeline Workflow & Runner

**Files:**
- Create: `workflows/daily_youtube_report.md`
- Create: `tools/run_pipeline.py`

- [ ] **Step 1: Create the workflow SOP**

```markdown
<!-- workflows/daily_youtube_report.md -->
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
```

- [ ] **Step 2: Create the pipeline runner**

```python
# tools/run_pipeline.py
import sys
import traceback

from tools.scrape_comments import run as scrape
from tools.classify_comments import run as classify
from tools.send_report import run as report


def run_pipeline():
    steps = [
        ("Scraping comments", scrape),
        ("Classifying comments", classify),
        ("Sending report", report),
    ]
    for name, step_fn in steps:
        print(f"\n{'='*50}")
        print(f"STEP: {name}")
        print(f"{'='*50}")
        try:
            step_fn()
        except Exception as e:
            print(f"\nERROR in '{name}': {e}")
            traceback.print_exc()
            sys.exit(1)
    print(f"\n{'='*50}")
    print("Pipeline complete!")
    print(f"{'='*50}")


if __name__ == "__main__":
    run_pipeline()
```

- [ ] **Step 3: Commit**

```bash
git add workflows/daily_youtube_report.md tools/run_pipeline.py
git commit -m "feat: pipeline runner and workflow SOP"
```

---

### Task 7: Create __init__.py and Integration Test

**Files:**
- Create: `tools/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Create package init files**

```python
# tools/__init__.py
```

```python
# tests/__init__.py
```

- [ ] **Step 2: Write integration test**

```python
# tests/test_pipeline.py
import os
import pytest
from unittest.mock import patch, MagicMock
from tools.db import get_connection, init_db, insert_channel, insert_video, insert_comment, get_unclassified_comments
from tools.classify_comments import load_categories, run as classify_run
from tools.send_report import build_report_data, render_report

TEST_DB = "data/test_comments.db"


@pytest.fixture(autouse=True)
def clean_db():
    os.makedirs("data", exist_ok=True)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_full_classify_and_report_flow():
    """Integration test: seed comments -> classify -> build report"""
    conn = get_connection(TEST_DB)
    init_db(conn)

    insert_channel(conn, id="UC123", name="Julia McCoy", handle="@JuliaMcCoy")
    insert_video(conn, id="v1", channel_id="UC123", title="AI Content Strategy",
                 published_at="2026-04-10T00:00:00Z", url="https://youtube.com/watch?v=v1")

    test_comments = [
        ("c1", "What tool do you use for this?", 2),
        ("c2", "You said the wrong date at 5:00", 0),
        ("c3", "Check out my channel http://spam.example.com", 0),
        ("c4", "This helped me so much, tried it and got results!", 8),
        ("c5", "You should make a video about SEO tools", 3),
    ]
    for cid, text, likes in test_comments:
        insert_comment(conn, id=cid, video_id="v1", author=f"User_{cid}",
                       text=text, likes=likes,
                       published_at="2026-04-10T01:00:00Z",
                       is_reply=False, parent_id=None)

    unclassified = get_unclassified_comments(conn)
    assert len(unclassified) == 5

    categories = load_categories("config/categories.json")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="testimonial")]
    )

    from tools.classify_comments import classify_comment
    from tools.db import update_comment_category
    for comment in unclassified:
        category, method = classify_comment(comment["text"], categories, mock_client)
        update_comment_category(conn, comment["id"], category, method)

    unclassified_after = get_unclassified_comments(conn)
    assert len(unclassified_after) == 0

    data = build_report_data(conn)
    assert data["total_comments"] == 5
    assert data["video_count"] == 1

    html = render_report(data)
    assert "YouTube Comments Report" in html
    assert "AI Content Strategy" in html

    conn.close()
```

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (7 + 4 + 9 + 3 + 1 = 24 tests)

- [ ] **Step 4: Commit**

```bash
git add tools/__init__.py tests/__init__.py tests/test_pipeline.py
git commit -m "test: integration test for full classify-and-report flow"
```

---

### Task 8: Fill .env and End-to-End Verification

**Files:**
- Modify: `.env` (user fills in real keys)

- [ ] **Step 1: Verify .env has real values**

User must fill in:
```
YOUTUBE_API_KEY=<real key>
ANTHROPIC_API_KEY=<real key>
GMAIL_ADDRESS=<real email>
GMAIL_APP_PASSWORD=<real app password>
REPORT_RECIPIENTS=<julia's email>
```

- [ ] **Step 2: Verify channel ID in config/channels.json**

Run: `python -c "from googleapiclient.discovery import build; import os; from dotenv import load_dotenv; load_dotenv(); yt = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY')); r = yt.channels().list(part='snippet', forHandle='JuliaMcCoy').execute(); print(r['items'][0]['id'], r['items'][0]['snippet']['title'])"`

Update `config/channels.json` with the real channel ID from the output.

- [ ] **Step 3: Run the full pipeline end-to-end**

Run: `python tools/run_pipeline.py`

Expected:
```
STEP: Scraping comments
Found N recent videos for Julia McCoy
  Scraped X comments from: <video title>
...
STEP: Classifying comments
Found X unclassified comments
Classified: Y by keywords, Z by AI

STEP: Sending report
Report sent to: <email>

Pipeline complete!
```

- [ ] **Step 4: Verify email received**

Check the recipient inbox for the HTML report. Verify:
- Subject line is correct
- Categories are populated
- Comments are grouped by video
- Formatting looks clean

- [ ] **Step 5: Commit verified config**

```bash
git add config/channels.json
git commit -m "chore: verified channel ID for Julia McCoy"
```

---

### Task 9: Schedule Daily Execution

- [ ] **Step 1: Set up Claude Code schedule**

Use Claude Code `/schedule` to create a daily trigger that runs:
```
python tools/run_pipeline.py
```

Schedule for a suitable time (e.g., 8:00 AM UTC daily).

- [ ] **Step 2: Verify schedule is active**

Run: `/schedule list` to confirm the schedule exists and shows the correct cron expression.

- [ ] **Step 3: Commit workflow docs update**

Update `workflows/daily_youtube_report.md` with the actual schedule details and commit.

```bash
git add workflows/daily_youtube_report.md
git commit -m "docs: add schedule details to workflow"
```
