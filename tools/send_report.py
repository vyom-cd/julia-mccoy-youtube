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
