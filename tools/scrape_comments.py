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


def load_channels(config_path: str = "config/channels.json") -> list[dict]:
    with open(config_path, "r") as f:
        return json.load(f)


def get_youtube_client(api_key: str | None = None):
    key = api_key or YOUTUBE_API_KEY
    if not key:
        raise ValueError("YOUTUBE_API_KEY not set in .env")
    return build("youtube", "v3", developerKey=key)


def fetch_recent_videos(youtube, channel_id: str, days_back: int = 7) -> list[dict]:
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


def fetch_comments_for_video(youtube, video_id: str) -> list[dict]:
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
        if "commentsDisabled" in e.content.decode("utf-8", errors="ignore"):
            return []
        raise
    return comments


def run(db_path: str | None = None, days_back: int = 7) -> None:
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
