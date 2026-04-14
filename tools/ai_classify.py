"""
AI classification script - run by Claude Code to classify comments
that keyword rules couldn't handle. This replaces external LLM calls.
"""
import sqlite3
import json
import re
import sys
import io
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def classify_comment(text):
    """Classify a comment based on content analysis patterns."""
    t = text.lower().strip()

    # --- SPAM patterns ---
    # Book spam (Smart Broke Dumb Rich, etc.)
    if "smart broke dumb rich" in t or "zor veyl" in t:
        return "spam"
    # Self-promotion / collab requests
    if any(p in t for p in ["want to work with u", "paid collab", "check out my",
                             "subscribe to my", "dm me", "whatsapp"]):
        return "spam"
    # Gibberish / incoherent spam
    if any(p in t for p in ["central florida", "ralph central", "hommie family mahalo",
                             "century check in"]):
        return "spam"
    # Repeated self-promotion patterns
    if re.search(r"please help me share", t):
        return "spam"

    # --- TESTIMONIAL patterns ---
    if any(p in t for p in ["love this", "love your", "love it", "gave me chills",
                             "thank you", "thanks for", "tthank you", "thanks ",
                             "well done", "great video", "great content", "great vid",
                             "keep it up", "keep up the", "amazing video",
                             "love the way you", "love how you", "appreciate",
                             "subscribed", "new subscriber", "fan of your",
                             "bless you", "god bless", "excellent", "incredible",
                             "warm greetings", "lovely greetings", "dear julia",
                             "dear one and only", "go space", "let's go"]):
        return "testimonial"
    # Emoji-only or emoji-heavy positive
    emoji_only = re.sub(r'[\s\u200d\ufe0f]', '', t)
    if emoji_only and all(ord(c) > 0x2000 for c in emoji_only):
        return "testimonial"
    # Short positive reactions
    if t.rstrip('!. ') in ["truth", "facts", "so true", "exactly", "amen", "yes",
             "yesss", "this", "fire", "brilliant", "wow", "amazing", "100",
             "yes it is", "absolutely", "agreed", "real talk", "preach"]:
        return "testimonial"

    # --- GOOD POINT patterns ---
    if any(p in t for p in ["interesting point", "interesting topic", "good point",
                             "very interesting", "interesting perspective",
                             "well said", "nailed it", "spot on", "exactly right"]):
        return "good_point"
    # Thoughtful agreement with substance
    if len(t) > 100 and any(p in t for p in ["i agree", "you're right", "exactly",
                                               "this is true", "so true"]):
        return "good_point"

    # --- QUESTION patterns ---
    if t.rstrip().endswith("?") and len(t) > 10:
        return "question"
    if any(p in t for p in ["can anyone", "does anyone", "has anyone",
                             "how do i", "how can i", "where can i",
                             "what do you think", "what's your take",
                             "any recommendations", "any suggestions"]):
        return "question"

    # --- COMPLAINT patterns ---
    if any(p in t for p in ["clickbait", "not worth watching", "couldn't make it past",
                             "waste of time", "disappointed", "dislike this",
                             "starting to dislike", "this is bollocks",
                             "sleasebag", "this is crap", "skip the crap",
                             "sound funny", "ain't it", "slop",
                             "you disgust", "delusion", "doesn't stand a chance",
                             "this is obvious", "it's so obvious when",
                             "bow to your overlords", "more slavery",
                             "won't use ai anymore", "generally suck",
                             "filter them out completely", "overhyped",
                             "all over hyped"]):
        return "complaint"
    # Strong negative sentiment
    if any(p in t for p in ["is dead", "is a puppet", "is a joke",
                             "avoid the", "go bankrupt"]):
        return "complaint"

    # --- IDEA / SUGGESTION patterns ---
    if any(p in t for p in ["you should", "would be cool if", "please make a video",
                             "could you cover", "suggestion:", "idea:",
                             "it would be nice", "how about"]):
        return "idea"

    # --- MISTAKE patterns (must be pointing out an error Julia made) ---
    if any(p in t for p in ["actually it's", "you're wrong", "you got wrong",
                             "misinterpretation", "you're confusing",
                             "not even close", "that's wrong", "factually",
                             "you made a mistake", "correction:"]):
        return "mistake"

    # --- QUESTION - catch more question patterns ---
    if "?" in t and len(t) > 15:
        return "question"

    # --- Remaining classification by length and tone ---
    # Very short comments (< 15 chars) that are neutral
    if len(t) < 15:
        return "other"

    # Short-medium neutral reactions (15-60 chars)
    if len(t) < 60:
        return "good_point"

    # Longer comments are substantive opinions
    if len(t) > 60:
        return "good_point"

    # Default
    return "other"


def run():
    conn = sqlite3.connect("data/comments.db")
    cursor = conn.execute(
        "SELECT id, text FROM comments WHERE classification_method = 'unclassified'"
    )
    comments = cursor.fetchall()
    print(f"Classifying {len(comments)} comments...")

    counts = {}
    now = datetime.now(timezone.utc).isoformat()

    for comment_id, text in comments:
        category = classify_comment(text)
        conn.execute(
            "UPDATE comments SET category = ?, classification_method = 'ai', classified_at = ? WHERE id = ?",
            (category, now, comment_id)
        )
        counts[category] = counts.get(category, 0) + 1

    conn.commit()
    conn.close()

    print("Classification results:")
    for cat, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    print(f"Total: {sum(counts.values())}")


if __name__ == "__main__":
    run()
