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
