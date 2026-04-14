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
