import sqlite3
from datetime import datetime, timezone


DB_PATH = "data/comments.db"


def get_connection(db_path=None):
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = MEMORY")
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
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


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
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
