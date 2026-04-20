import json
import logging
import os
import urllib.request
import urllib.error
from collections import OrderedDict
from datetime import datetime, timezone
from html import escape

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

from tools.db import get_connection, init_db, get_classified_comments_for_report

load_dotenv()

logger = logging.getLogger(__name__)

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

    # Escape HTML in comment text to prevent XSS
    for c in comments:
        c["text"] = escape(c["text"])
        c["author"] = escape(c["author"])

    videos = OrderedDict()
    category_totals = OrderedDict()
    for c in comments:
        vid_key = c["video_id"]
        if vid_key not in videos:
            videos[vid_key] = {
                "title": escape(c["video_title"]),
                "url": c["video_url"],
                "total_comments": 0,
                "categories": OrderedDict(),
            }
        videos[vid_key]["total_comments"] += 1
        cat = c["category"]
        if cat not in videos[vid_key]["categories"]:
            videos[vid_key]["categories"][cat] = {
                "icon": CATEGORY_ICONS.get(cat, "📌"),
                "comments": [],
            }
        videos[vid_key]["categories"][cat]["comments"].append(c)
        category_totals[cat] = category_totals.get(cat, 0) + 1

    for vid in videos.values():
        sorted_cats = OrderedDict()
        for cat_name in CATEGORY_ORDER:
            if cat_name in vid["categories"]:
                sorted_cats[cat_name] = vid["categories"][cat_name]
        vid["categories"] = sorted_cats

    sorted_totals = OrderedDict()
    for cat_name in CATEGORY_ORDER:
        if cat_name in category_totals:
            sorted_totals[cat_name] = {
                "icon": CATEGORY_ICONS.get(cat_name, "📌"),
                "count": category_totals[cat_name],
            }

    return {
        "report_date": datetime.now(timezone.utc).strftime("%B %d, %Y"),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "total_comments": len(comments),
        "video_count": len(videos),
        "category_count": len(sorted_totals),
        "category_totals": sorted_totals,
        "videos": videos,
        "all_categories": CATEGORY_ORDER,
        "category_icons": CATEGORY_ICONS,
        "full_report_url": f"https://vyom-cd.github.io/julia-mccoy-youtube/report/?v={int(datetime.now(timezone.utc).timestamp())}",
    }


def render_report(data, template_dir="templates"):
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    template = env.get_template("report.html")
    return template.render(**data)


def send_email(html_content, subject=None):
    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    recipients = os.getenv("REPORT_RECIPIENTS")

    if not webhook_url:
        raise ValueError("N8N_WEBHOOK_URL not set in .env")
    if not recipients:
        raise ValueError("REPORT_RECIPIENTS not set in .env")

    if not subject:
        subject = f"YouTube Comments Report - {datetime.now(timezone.utc).strftime('%b %d, %Y')}"

    payload = json.dumps({
        "to": recipients.strip(),
        "subject": subject,
        "html": html_content,
    }, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        logger.info("Report sent to: %s (status %s)", recipients, resp.status)
        print(f"Report sent to: {recipients}")
    except urllib.error.URLError as e:
        logger.error("Failed to send report via webhook: %s", e)
        print(f"ERROR: Failed to send report: {e}")
        raise
    except urllib.error.HTTPError as e:
        logger.error("Webhook returned HTTP %s: %s", e.code, e.reason)
        print(f"ERROR: Webhook returned {e.code}: {e.reason}")
        raise


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
