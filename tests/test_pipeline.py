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
