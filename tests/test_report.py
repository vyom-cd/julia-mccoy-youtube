import os
import pytest
from tools.send_report import build_report_data, render_report
from tools.db import get_connection, init_db, insert_channel, insert_video, insert_comment, commit, update_comment_category

TEST_DB = "data/test_report.db"


@pytest.fixture(autouse=True)
def clean_db():
    os.makedirs("data", exist_ok=True)
    # Remove any leftover DB files (including WAL/SHM)
    for ext in ["", "-wal", "-shm"]:
        path = TEST_DB + ext
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    yield
    for ext in ["", "-wal", "-shm"]:
        path = TEST_DB + ext
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def seed_db(conn):
    insert_channel(conn, id="UC123", name="Test", handle="@test")
    insert_video(conn, id="vid1", channel_id="UC123", title="Test Video", published_at="2026-04-10T00:00:00Z", url="https://youtube.com/watch?v=vid1")
    insert_comment(conn, id="c1", video_id="vid1", author="Alice", text="You said it wrong at 2:00", likes=3, published_at="2026-04-10T01:00:00Z", is_reply=False, parent_id=None)
    insert_comment(conn, id="c2", video_id="vid1", author="Bob", text="Great insight!", likes=10, published_at="2026-04-10T02:00:00Z", is_reply=False, parent_id=None)
    insert_comment(conn, id="c3", video_id="vid1", author="Spammer", text="Check out my channel http://spam.com", likes=0, published_at="2026-04-10T03:00:00Z", is_reply=False, parent_id=None)
    commit(conn)
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
    assert "mistake" in data["category_totals"]
    assert "good_point" in data["category_totals"]
    assert "spam" in data["category_totals"]
    assert data["category_totals"]["mistake"]["count"] == 1
    assert "vid1" in data["videos"]
    assert "mistake" in data["videos"]["vid1"]["categories"]
    conn.close()


def test_render_report():
    conn = get_connection(TEST_DB)
    init_db(conn)
    seed_db(conn)
    data = build_report_data(conn)
    html = render_report(data)
    assert "YouTube Comments Report" in html
    assert "Test Video" in html
    assert "3" in html  # total comments count
    conn.close()


def test_build_report_data_empty_db():
    conn = get_connection(TEST_DB)
    init_db(conn)
    data = build_report_data(conn)
    assert data["total_comments"] == 0
    assert data["video_count"] == 0
    conn.close()
