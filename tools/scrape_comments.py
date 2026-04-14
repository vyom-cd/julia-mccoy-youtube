import json
import os
from datetime import datetime, timedelta, timezone

from apify_client import ApifyClient
from dotenv import load_dotenv

from tools.db import get_connection, init_db, insert_channel, insert_video, insert_comment

load_dotenv()

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
ACTOR_ID = "streamers/youtube-comments-scraper"


def load_channels(config_path="config/channels.json"):
    with open(config_path, "r") as f:
        return json.load(f)


def get_video_urls_for_channel(channel_handle, days_back=7):
    """Use Apify YouTube scraper to get recent video URLs for a channel."""
    client = ApifyClient(APIFY_API_TOKEN)
    run = client.actor("streamers/youtube-scraper").call(run_input={
        "startUrls": [{"url": f"https://www.youtube.com/{channel_handle}/videos"}],
        "maxResults": 50,
        "maxResultsShorts": 0,
    })
    videos = []
    since = datetime.now(timezone.utc) - timedelta(days=days_back)
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        if item.get("date"):
            try:
                pub_date = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
                if pub_date < since:
                    continue
            except (ValueError, TypeError):
                pass
        videos.append({
            "id": item.get("id", ""),
            "title": item.get("title", ""),
            "published_at": item.get("date", ""),
            "url": item.get("url", f"https://www.youtube.com/watch?v={item.get('id', '')}"),
        })
    return videos


def fetch_comments_for_videos(video_urls, max_comments=500):
    """Fetch comments for a list of video URLs using Apify."""
    client = ApifyClient(APIFY_API_TOKEN)
    start_urls = [{"url": url} for url in video_urls]
    run = client.actor(ACTOR_ID).call(run_input={
        "startUrls": start_urls,
        "maxComments": max_comments,
    })
    comments = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        comments.append({
            "id": item.get("cid", ""),
            "video_id": item.get("videoId", ""),
            "video_title": item.get("title", ""),
            "video_url": item.get("pageUrl", ""),
            "author": item.get("author", ""),
            "text": item.get("comment", ""),
            "likes": item.get("voteCount", 0),
            "published_at": item.get("publishedAt", datetime.now(timezone.utc).isoformat()),
            "is_reply": bool(item.get("replyToCid")),
            "parent_id": item.get("replyToCid"),
        })
    return comments


def run(db_path=None, days_back=7):
    if not APIFY_API_TOKEN:
        raise ValueError("APIFY_API_TOKEN not set in .env")

    conn = get_connection(db_path)
    init_db(conn)
    channels = load_channels()
    total_comments = 0

    for channel in channels:
        insert_channel(conn, id=channel["id"], name=channel["name"], handle=channel.get("handle", ""))

        print(f"Fetching recent videos for {channel['name']}...")
        videos = get_video_urls_for_channel(channel["handle"], days_back=days_back)
        print(f"Found {len(videos)} recent videos")

        if not videos:
            continue

        for video in videos:
            insert_video(
                conn,
                id=video["id"],
                channel_id=channel["id"],
                title=video["title"],
                published_at=video["published_at"],
                url=video["url"],
            )

        video_urls = [v["url"] for v in videos]
        print(f"Scraping comments from {len(video_urls)} videos...")
        comments = fetch_comments_for_videos(video_urls)

        for comment in comments:
            vid_id = comment["video_id"]
            if not vid_id:
                continue
            insert_comment(
                conn,
                id=comment["id"],
                video_id=vid_id,
                author=comment["author"],
                text=comment["text"],
                likes=comment["likes"],
                published_at=comment["published_at"],
                is_reply=comment["is_reply"],
                parent_id=comment["parent_id"],
            )
        total_comments += len(comments)
        print(f"Scraped {len(comments)} comments")

    conn.close()
    print(f"\nTotal comments scraped: {total_comments}")


if __name__ == "__main__":
    run()
