"""
Manual classification by Claude Code.
Classifies all comments in the database using contextual understanding.
"""
import sqlite3
import re
import sys
import io
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def classify(text):
    t = text.lower().strip()
    # Remove HTML entities
    t = t.replace("&#39;", "'").replace("&amp;", "&").replace("&quot;", '"')

    # ========== SPAM (check first - removes noise) ==========
    # Book spam campaign
    if "smart broke dumb rich" in t or "zor veyl" in t:
        return "spam"
    # Investment/trading scam threads
    if any(p in t for p in ["lori christen", "gainwithlori", "telegram's apps",
                             "profitable trading requires", "she's the best i have ever seen she's so transparent",
                             "i started with 2k", "educate me", "hit a goal that once felt impossible"]):
        return "spam"
    # Self-promotion / collab requests
    if any(p in t for p in ["want to work with u", "paid collab", "i would like to chat with u private",
                             "do u have a number", "subscribe to my", "dm me for",
                             "please help me share"]):
        return "spam"
    # Gibberish / incoherent spam
    if any(p in t for p in ["ralph central", "hommie family mahalo",
                             "century check in", "onehundreadpersent"]):
        return "spam"
    # Numerology / code gibberish
    if re.search(r'own:\d+.*one:\d+.*from:\d+', t):
        return "spam"
    # Network/platform promotion
    if any(p in t for p in ["truth network", "deployed worldwide"]):
        return "spam"

    # ========== TESTIMONIAL (positive about Julia / her content) ==========
    # Only short comments with praise keywords — long comments go to good_point
    if len(t) < 150 and any(p in t for p in ["love this", "love your", "love it", "gave me chills",
                             "well done", "great video", "great vid", "great content",
                             "keep it up", "keep up the", "amazing video", "amazing content",
                             "love the way you", "love how you", "appreciate your",
                             "new subscriber", "fan of your",
                             "god bless", "truly appreciate", "incredible episode",
                             "warm greetings", "lovely greetings", "dear julia",
                             "dear one and only", "estudos e análises são excelentes"]):
        return "testimonial"
    # Thankful short comments only
    if len(t) < 50 and any(p in t for p in ["thank you", "thanks for", "tthank you"]):
        return "testimonial"
    # Emoji-only positive (hearts, claps, prayer) — NOT laughing emojis
    clean = re.sub(r'[\s\u200d\ufe0f]', '', t)
    if clean and len(clean) < 20 and all(ord(c) > 0x2000 for c in clean):
        # Check it's positive emojis, not laughing/neutral
        if any(e in t for e in ['❤', '💖', '💜', '🙏', '👏', '🔥', '✨', '💪', '👍']):
            return "testimonial"
        # Laughing emojis or neutral → other
        return "other"
    # Short enthusiastic praise
    if t.rstrip('!. ') in ["fire", "brilliant", "wow", "preach",
                             "spot on", "well said", "facts", "awesome"]:
        return "testimonial"

    # ========== COMPLAINT (negative about Julia, her content, or strong negativity) ==========
    if any(p in t for p in ["clickbait", "not worth watching", "couldn't make it past",
                             "waste of time", "disappointed", "starting to dislike",
                             "this is bollocks", "sleasebag", "skip the crap",
                             "you disgust", "delusion women", "reading directly from chatgtp",
                             "bow to your overlords", "more slavery with technological",
                             "won't use ai anymore", "generally suck",
                             "some bs unaffiliated", "ai clone", "fake ai",
                             "this voice aint it", "so much for workers",
                             "clown show", "ur being u safe"]):
        return "complaint"

    # ========== QUESTION (asking something) ==========
    if t.rstrip().endswith("?") and len(t) > 10:
        return "question"
    if any(p in t for p in ["can anyone", "does anyone", "has anyone",
                             "how do i", "how can i", "where can i",
                             "what do you think", "what's your take",
                             "any recommendations", "any suggestions",
                             "am i talking about"]):
        return "question"

    # ========== IDEA (suggestion for Julia or about the future) ==========
    if any(p in t for p in ["you should", "would be cool if", "please make a video",
                             "could you cover", "you need a logo",
                             "it would be nice", "how about covering",
                             "should really validate", "don't you think"]):
        return "idea"
    # Suggesting Julia consider something
    if "julia" in t and any(p in t for p in ["should", "could", "need to", "consider"]):
        return "idea"

    # ========== MISTAKE (pointing out a factual error Julia made) ==========
    if any(p in t for p in ["actually it's", "you're wrong", "you got wrong",
                             "that's wrong", "factually", "you made a mistake",
                             "correction:", "misinterpretation",
                             "not even close", "she didnt mention",
                             "asset value is not gdp", "one-sided here"]):
        return "mistake"

    # ========== GOOD POINT (substantive comment about the topic) ==========
    # Long comments with real substance (>100 chars, not spam)
    if len(t) > 100:
        return "good_point"
    # Medium comments with opinion signals
    if len(t) > 40 and any(p in t for p in ["i think", "i believe", "i predict",
                                              "in my opinion", "the reason",
                                              "the problem", "interesting",
                                              "the real", "actually", "true but",
                                              "that said", "however"]):
        return "good_point"
    # Statements about the topic (not about Julia)
    if len(t) > 30:
        return "good_point"

    # ========== OTHER (short, neutral, or unclassifiable) ==========
    return "other"


def run():
    conn = sqlite3.connect("data/comments.db")
    # Reset all classifications
    conn.execute("UPDATE comments SET category = NULL, classification_method = NULL, classified_at = NULL")
    conn.commit()

    cursor = conn.execute("SELECT id, text FROM comments")
    comments = cursor.fetchall()
    print(f"Classifying {len(comments)} comments...")

    counts = {}
    now = datetime.now(timezone.utc).isoformat()

    for comment_id, text in comments:
        category = classify(text)
        conn.execute(
            "UPDATE comments SET category = ?, classification_method = 'ai', classified_at = ? WHERE id = ?",
            (category, now, comment_id)
        )
        counts[category] = counts.get(category, 0) + 1

    conn.commit()
    conn.close()

    print("\nClassification results:")
    for cat, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    print(f"\nTotal: {sum(counts.values())}")


if __name__ == "__main__":
    run()
