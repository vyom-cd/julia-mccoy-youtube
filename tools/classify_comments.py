"""
Comment classifier — designed to be run by Claude Code.

When run via /schedule, Claude reads each comment and classifies it
using actual language understanding, not keyword matching.

When run standalone (python tools/classify_comments.py), it uses
keyword rules as a basic fallback.
"""
import json
import os
import re
import sqlite3
from datetime import datetime, timezone

from dotenv import load_dotenv

from tools.db import get_connection, init_db, get_unclassified_comments, update_comment_category

load_dotenv()

CATEGORIES = [
    "mistake",      # Points out an error Julia made in the video
    "good_point",   # Substantive comment or opinion about the topic
    "idea",         # Suggestion for Julia (video topics, improvements)
    "question",     # Asking something
    "testimonial",  # Short, direct praise for Julia or her content
    "complaint",    # Negative feedback about Julia, her content, or strong negativity
    "spam",         # Promotional, bot, scam, or gibberish content
    "other",        # Doesn't fit any category (emojis only, very short neutral)
]


def get_unclassified_for_review(db_path=None):
    """Export unclassified comments for Claude to review."""
    conn = get_connection(db_path)
    init_db(conn)
    comments = get_unclassified_comments(conn)
    conn.close()
    return comments


def apply_classifications(classifications, db_path=None):
    """Apply a dict of {comment_id: category} to the database."""
    conn = get_connection(db_path)
    init_db(conn)
    for comment_id, category in classifications.items():
        if category in CATEGORIES:
            update_comment_category(conn, comment_id=comment_id, category=category, method="ai")
    conn.close()
    print(f"Applied {len(classifications)} classifications")


def run(db_path=None):
    """
    Fallback classifier using keyword rules.
    When Claude Code runs this via /schedule, it should instead:
    1. Call get_unclassified_for_review() to get comments
    2. Read through them and classify each one
    3. Call apply_classifications() with the results
    """
    conn = get_connection(db_path)
    init_db(conn)
    comments = get_unclassified_comments(conn)
    print(f"Found {len(comments)} unclassified comments")
    print("NOTE: For best results, run this through Claude Code /schedule")
    print("      which classifies each comment with actual understanding.")
    print("      Using keyword fallback for now...\n")

    for comment in comments:
        category = _keyword_fallback(comment["text"])
        update_comment_category(conn, comment_id=comment["id"], category=category, method="keyword")

    conn.close()


def _keyword_fallback(text):
    """Basic keyword classification — used only when Claude isn't available."""
    t = text.lower().strip()

    # Spam
    if any(p in t for p in ["check out my", "subscribe to", "dm me", "whatsapp",
                             "smart broke dumb rich", "zor veyl", "paid collab"]):
        return "spam"
    if re.search(r"https?://(?!youtube\.com|youtu\.be)\S+", t):
        return "spam"

    # Question
    if t.rstrip().endswith("?") and len(t) > 10:
        return "question"

    # Everything else needs Claude's judgment
    return "other"


if __name__ == "__main__":
    run()
