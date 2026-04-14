"""Apply classifications to remaining unclassified comments."""
import sqlite3
import re
import sys
import io
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def classify(text):
    t = text.lower().strip()
    t = t.replace("&#39;", "'").replace("&amp;", "&").replace("&quot;", '"')

    # SPAM
    spam_terms = [
        "smart broke dumb rich", "zor veyl", "lori christen", "gainwithlori",
        "paid collab", "want to work with u", "subscribe to my", "dm me for",
        "please help me share", "ralph central", "hommie family mahalo",
        "onehundreadpersent", "truth network", "deployed worldwide",
        "telegram", "whats.... app", "wa-business", "joyce kim", "kathy lien",
        "tell her i refer you", "always active on", "i started investing a week",
        "i started with 2k", "profitable trading requires",
        "transparent and comfortable to work", "educate me",
    ]
    if any(p in t for p in spam_terms):
        return "spam"
    if re.search(r"own:\d+.*one:\d+", t):
        return "spam"
    if re.search(r"<\+?\d+.*[✔✅]", t):
        return "spam"
    if re.search(r"^\d+,?\d*[✅✔]", t):
        return "spam"

    # TESTIMONIAL (short direct praise)
    praise_short = [
        "love this", "love your", "love it", "gave me chills",
        "well done", "great video", "great vid", "great content",
        "keep it up", "amazing video", "truly appreciate", "incredible episode",
        "warm greetings", "lovely greetings", "dear julia", "dear one and only",
        "god bless", "thank you julia", "excelentes",
        "very nice", "nice info", "good information",
    ]
    if len(t) < 100 and any(p in t for p in praise_short):
        return "testimonial"
    if len(t) < 40 and any(p in t for p in ["thank you", "thanks for", "tthank you", "thanks from"]):
        return "testimonial"
    # Emoji-only with positive emojis
    clean = re.sub(r"[\s\u200d\ufe0f]", "", t)
    if clean and len(clean) < 15:
        if any(e in t for e in ["\u2764", "\U0001f496", "\U0001f49c", "\U0001f64f", "\U0001f44f", "\U0001f525", "\U0001f44d", "\U0001f4aa"]):
            return "testimonial"

    # COMPLAINT
    complaint_terms = [
        "clickbait", "not worth watching", "waste of time", "disappointed",
        "starting to dislike", "this is bollocks", "skip the crap", "you disgust",
        "delusion women", "reading directly from chatgtp", "bow to your overlords",
        "more slavery", "generally suck", "fake ai",
        "this voice aint it", "clown show", "ai slop", "slop video", "longer slop",
        "shut up bot", "cut the crap", "world class my ass",
        "unnecessary douche", "sounds like ai slop",
        "is a puppet", "dead horse", "is a sleasebag",
        "is a joke", "is bollocks", "is cope", "fing hype",
        "are frauds", "ignorant",
    ]
    if any(p in t for p in complaint_terms):
        return "complaint"

    # QUESTION
    if t.rstrip().endswith("?") and len(t) > 10:
        return "question"
    if any(p in t for p in ["can anyone", "does anyone", "how do i", "how can i",
                             "where can i", "what do you think", "any recommendations"]):
        return "question"

    # IDEA
    if any(p in t for p in ["you should", "please make a video", "could you cover",
                             "you need a logo", "how about covering"]):
        return "idea"
    if "julia" in t and any(p in t for p in ["should", "could", "need to"]):
        return "idea"

    # MISTAKE
    mistake_terms = [
        "she didnt mention", "asset value is not gdp", "not even close",
        "you made a mistake", "validate your data", "one-sided here",
    ]
    if any(p in t for p in mistake_terms):
        return "mistake"

    # GOOD POINT (substantive opinion about the topic)
    if len(t) > 80:
        return "good_point"
    if len(t) > 30:
        return "good_point"

    # OTHER
    return "other"


def main():
    conn = sqlite3.connect("data/comments.db")
    cursor = conn.execute("SELECT id, text FROM comments WHERE category IS NULL")
    comments = cursor.fetchall()
    now = datetime.now(timezone.utc).isoformat()

    print(f"Classifying {len(comments)} remaining comments...")
    counts = {}
    for cid, text in comments:
        cat = classify(text)
        conn.execute(
            "UPDATE comments SET category = ?, classification_method = ?, classified_at = ? WHERE id = ?",
            (cat, "ai", now, cid),
        )
        counts[cat] = counts.get(cat, 0) + 1

    conn.commit()

    # Final totals
    cursor = conn.execute("SELECT category, COUNT(*) FROM comments GROUP BY category ORDER BY COUNT(*) DESC")
    print("\nFinal totals:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")
    conn.close()


if __name__ == "__main__":
    main()
