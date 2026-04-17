"""
Comment classifier for Julia McCoy YouTube Comment Monitor.

Single authoritative classifier that:
1. Uses Claude API for accurate classification (primary, if ANTHROPIC_API_KEY set)
2. Falls back to pattern matching when Claude is unavailable
3. Loads additional keywords from config/categories.json
4. Never resets existing classifications unless explicitly asked

Usage:
    # Classify only unclassified comments (uses Claude if API key available)
    python -c "from tools.classify_comments import run; run()"

    # Force pattern-only (no Claude API)
    python -c "from tools.classify_comments import run; run(use_ai=False)"

    # Re-classify everything (requires --reset flag)
    python -c "from tools.classify_comments import run; run(reset=True)"
"""
import json
import os
import re
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

from tools.db import get_connection, init_db, get_unclassified_comments, update_comment_category

load_dotenv()

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

CATEGORIES = [
    "mistake",
    "good_point",
    "idea",
    "question",
    "testimonial",
    "complaint",
    "spam",
    "other",
]

# --- Hardcoded patterns (merged from ai_classify.py, classify_all.py, apply_remaining.py) ---

SPAM_TERMS = [
    "smart broke dumb rich", "zor veyl", "lori christen", "gainwithlori",
    "paid collab", "want to work with u", "subscribe to my", "dm me for",
    "please help me share", "ralph central", "hommie family mahalo",
    "onehundreadpersent", "truth network", "deployed worldwide",
    "telegram", "whats.... app", "wa-business", "joyce kim", "kathy lien",
    "tell her i refer you", "always active on", "i started investing a week",
    "i started with 2k", "profitable trading requires",
    "transparent and comfortable to work", "educate me",
    "hit a goal that once felt impossible", "check out my",
    "i would like to chat with u private", "do u have a number",
    "she's the best i have ever seen she's so transparent",
    "century check in",
]

SPAM_REGEX = [
    re.compile(r"own:\d+.*one:\d+"),
    re.compile(r"<\+?\d+.*[✔✅]"),
    re.compile(r"^\d+,?\d*[✅✔]"),
    re.compile(r"https?://(?!youtube\.com|youtu\.be)\S+"),
]

TESTIMONIAL_SHORT = [
    "love this", "love your", "love it", "gave me chills",
    "well done", "great video", "great vid", "great content",
    "keep it up", "keep up the", "amazing video", "amazing content",
    "love the way you", "love how you", "appreciate your",
    "new subscriber", "fan of your",
    "god bless", "truly appreciate", "incredible episode",
    "warm greetings", "lovely greetings", "dear julia",
    "dear one and only", "very nice", "nice info", "good information",
]

TESTIMONIAL_THANKS = ["thank you", "thanks for", "tthank you", "thanks from", "thank you julia"]

TESTIMONIAL_EXCLAIM = [
    "truth", "facts", "so true", "exactly", "amen", "yes",
    "yesss", "this", "fire", "brilliant", "wow", "amazing", "100",
    "yes it is", "absolutely", "agreed", "real talk", "preach",
    "spot on", "well said", "awesome",
]

POSITIVE_EMOJI = ["❤", "💖", "💜", "🙏", "👏", "🔥", "✨", "💪", "👍"]

COMPLAINT_TERMS = [
    "clickbait", "not worth watching", "couldn't make it past",
    "waste of time", "disappointed", "starting to dislike",
    "this is bollocks", "sleasebag", "skip the crap", "you disgust",
    "delusion women", "delusion", "reading directly from chatgtp",
    "bow to your overlords", "more slavery", "generally suck", "fake ai",
    "this voice aint it", "clown show", "ai slop", "slop video", "longer slop",
    "shut up bot", "cut the crap", "world class my ass",
    "unnecessary douche", "sounds like ai slop",
    "is a puppet", "dead horse", "is a sleasebag",
    "is a joke", "is bollocks", "is cope", "fing hype",
    "are frauds", "ignorant", "won't use ai anymore",
    "ur being u safe", "so much for workers",
    "doesn't stand a chance", "this is crap",
    "dislike this", "overhyped", "all over hyped",
    # Patterns from old classify_all.py that were missing
    "sound funny", "ain't it", "this is obvious",
    "it's so obvious when", "some bs", "ai clone",
    "nonsense", "ai script", "unsubscribing",
    "lacks authenticity", "ai does not exist",
    "ai robot", "bullshit", "bull shit", "fuck",
    "shit", "crap", "go bankrupt", "avoid the",
    "is dead", "doesn't work", "not helpful",
    "terrible", "horrible", "pathetic", "ridiculous",
    "propaganda", "scam", "grifter", "snake oil",
]

QUESTION_PHRASES = [
    "can anyone", "does anyone", "has anyone",
    "how do i", "how can i", "where can i",
    "what do you think", "what's your take",
    "any recommendations", "any suggestions",
    "am i talking about",
]

IDEA_PHRASES = [
    "you should", "would be cool if", "please make a video",
    "could you cover", "you need a logo",
    "it would be nice", "how about covering",
    "should really validate", "don't you think",
]

MISTAKE_PHRASES = [
    "actually it's", "you're wrong", "you got wrong",
    "that's wrong", "factually", "you made a mistake",
    "correction:", "misinterpretation",
    "not even close", "she didnt mention",
    "asset value is not gdp", "one-sided here",
    "you're confusing",
]

GOOD_POINT_PHRASES = [
    "interesting point", "interesting topic", "good point",
    "very interesting", "interesting perspective",
    "well said", "nailed it", "spot on", "exactly right",
]

OPINION_SIGNALS = [
    "i think", "i believe", "i predict",
    "in my opinion", "the reason",
    "the problem", "interesting",
    "the real", "actually", "true but",
    "that said", "however",
]


def load_categories(config_path="config/categories.json"):
    """Load category definitions from config file."""
    with open(config_path, "r") as f:
        data = json.load(f)
    return data.get("categories", data)


def classify_comment(text, categories=None):
    """
    Classify a single comment. Returns (category, method).

    Uses pattern matching rules. The categories parameter accepts the
    loaded config for additional keyword matching.
    """
    t = text.lower().strip()
    t = t.replace("&#39;", "'").replace("&amp;", "&").replace("&quot;", '"')

    # --- SPAM ---
    if any(p in t for p in SPAM_TERMS):
        return "spam", "pattern"
    for regex in SPAM_REGEX:
        if regex.search(t):
            return "spam", "pattern"

    # Config-based spam keywords
    if categories:
        spam_cat = next((c for c in categories if c["name"] == "spam"), None)
        if spam_cat:
            for kw in spam_cat.get("keywords", []):
                if kw.lower() in t:
                    return "spam", "keyword"

    # --- TESTIMONIAL ---
    if len(t) < 150 and any(p in t for p in TESTIMONIAL_SHORT):
        return "testimonial", "pattern"
    if len(t) < 50 and any(p in t for p in TESTIMONIAL_THANKS):
        return "testimonial", "pattern"

    # Emoji-only with positive emoji
    clean = re.sub(r"[\s\u200d\ufe0f]", "", t)
    if clean and len(clean) < 20:
        # Check if mostly emoji (characters above basic multilingual plane)
        if all(ord(c) > 0x2000 or ord(c) > 0x1F000 for c in clean):
            if any(e in text for e in POSITIVE_EMOJI):
                return "testimonial", "pattern"
            return "other", "pattern"

    # Short enthusiastic one-word praise
    stripped = t.rstrip("!. ")
    if stripped in TESTIMONIAL_EXCLAIM:
        return "testimonial", "pattern"

    # Short positive reactions (under 30 chars, no negative words)
    if len(t) < 30 and any(p in t for p in [
        "interesting", "very nice", "nice", "cool", "good one",
        "so exciting", "real good", "not bad", "pretty good",
    ]):
        return "testimonial", "pattern"

    # --- COMPLAINT (check BEFORE question — rhetorical complaints contain "?") ---
    if any(p in t for p in COMPLAINT_TERMS):
        return "complaint", "pattern"

    # Config-based complaint keywords
    if categories:
        comp_cat = next((c for c in categories if c["name"] == "complaint"), None)
        if comp_cat:
            for kw in comp_cat.get("keywords", []):
                if kw.lower() in t:
                    return "complaint", "keyword"

    # Negative tone signals — snarky/dismissive short comments
    if len(t) < 80 and any(p in t for p in [
        "lying", "lies", "liar", "trash", "slow", "old news",
        "money grab", "don't believe", "not believe", "wouldn't believe",
        "would not believe", "slavery", "no sign of", "addicted",
        "another ad", "affiliate marketing", "brought to you",
        "didn't need", "you still", "thought you",
        "are you slow", "are you serious", "give me a break",
        "get real", "yeah right", "sure thing",
        "doom and gloom", "nothing positive", "nothing new",
        "nothing unique", "too general", "use to do it",
        "used to be better", "you use to",
    ]):
        return "complaint", "pattern"

    # Longer negative-toned comments (80+ chars with strong negative signals)
    if len(t) > 80 and any(p in t for p in [
        "pure evil", "death spiral", "doom and gloom", "nothing positive",
        "enough with", "too general", "nothing unique",
        "useless toys", "used to be better", "use to do it much better",
        "must be prosecuted", "put out of action",
        "fear pitch", "not helpful", "stop pretending",
    ]):
        return "complaint", "pattern"

    # --- QUESTION ---
    # Only classify as question if it ends with "?" (direct question)
    # Mid-text "?" in long comments is usually rhetorical
    if t.rstrip().endswith("?") and len(t) > 10:
        return "question", "pattern"
    if any(p in t for p in QUESTION_PHRASES):
        return "question", "pattern"

    # --- IDEA ---
    if any(p in t for p in IDEA_PHRASES):
        return "idea", "pattern"
    if "julia" in t and any(p in t for p in ["should", "could", "need to", "consider"]):
        return "idea", "pattern"

    # --- MISTAKE ---
    if any(p in t for p in MISTAKE_PHRASES):
        return "mistake", "pattern"

    # Config-based mistake keywords
    if categories:
        mist_cat = next((c for c in categories if c["name"] == "mistake"), None)
        if mist_cat:
            for kw in mist_cat.get("keywords", []):
                if kw.lower() in t:
                    return "mistake", "keyword"

    # --- GOOD POINT ---
    if any(p in t for p in GOOD_POINT_PHRASES):
        return "good_point", "pattern"
    # Long comments with real substance (>100 chars)
    if len(t) > 100:
        return "good_point", "pattern"
    # Medium comments with opinion signals
    if len(t) > 40 and any(p in t for p in OPINION_SIGNALS):
        return "good_point", "pattern"
    # Medium-length statements (80+ chars, likely substantive)
    if len(t) > 80:
        return "good_point", "pattern"

    # --- OTHER (short/neutral comments under 80 chars with no pattern match) ---
    return "other", "pattern"


def classify_by_keywords(text, categories):
    """
    Classify using only config/categories.json keywords.
    Returns category name or None if no match.
    """
    t = text.lower().strip()
    for cat in categories:
        for kw in cat.get("keywords", []):
            if kw.lower() in t:
                return cat["name"]
        for pat in cat.get("patterns", []):
            if re.search(pat, t):
                return cat["name"]
    return None


def ai_classify_batch(comments_batch, api_key):
    """Use Claude API to classify a batch of comments. Returns dict of {index: category}."""
    if not HAS_ANTHROPIC or not api_key:
        return None

    client = anthropic.Anthropic(api_key=api_key)

    comments_text = ""
    for i, c in enumerate(comments_batch):
        text_preview = c["text"][:300].replace("\n", " ")
        comments_text += f"[{i}] {text_preview}\n"

    prompt = f"""Classify each YouTube comment from Julia McCoy's AI/technology channel.

For EACH comment, return a JSON array where each item has:
- "index": the comment number [0], [1], etc.
- "category": ONE from: "mistake", "good_point", "idea", "question", "testimonial", "complaint", "spam", "other"

Category definitions:
- mistake: Points out a factual error Julia made in the video
- good_point: Substantive comment or opinion about the topic discussed
- idea: Suggestion for Julia (video topics, improvements, things to cover)
- question: Asking for clarification, help, or information
- testimonial: Short direct praise for Julia or her content (love this, great video, thank you, etc.)
- complaint: Negative feedback about Julia, her content, or strong criticism/hostility
- spam: Promotional, bot, scam, gibberish, investment schemes, self-promotion
- other: Very short neutral comments, emojis only, doesn't fit any category

Rules:
- "complaint" = genuine dissatisfaction, hostility, or criticism of Julia/content. NOT casual disagreement.
- "testimonial" = short praise. Long thoughtful positive comments = "good_point"
- "spam" = bot-like, promotional, scam patterns, gibberish numerology
- Short neutral reactions (under 15 chars, no strong signal) = "other"

Comments:
{comments_text}

Return ONLY valid JSON array, no other text."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        result_text = response.content[0].text.strip()
        if result_text.startswith("```"):
            result_text = re.sub(r"^```(?:json)?\n?", "", result_text)
            result_text = re.sub(r"\n?```$", "", result_text)
        parsed = json.loads(result_text)
        return {item["index"]: item["category"] for item in parsed if item.get("category") in CATEGORIES}
    except Exception as e:
        print(f"  AI classification error: {e}")
        return None


def get_unclassified_for_review(db_path=None):
    """Export unclassified comments for manual review."""
    conn = get_connection(db_path)
    init_db(conn)
    comments = get_unclassified_comments(conn)
    conn.close()
    return comments


def apply_classifications(classifications, db_path=None):
    """Apply a dict of {comment_id: category} to the database."""
    conn = get_connection(db_path)
    init_db(conn)
    applied = 0
    for comment_id, category in classifications.items():
        if category in CATEGORIES:
            update_comment_category(conn, comment_id=comment_id, category=category, method="manual")
            applied += 1
    conn.close()
    print(f"Applied {applied} classifications")


def run(db_path=None, reset=False, use_ai=True):
    """
    Classify comments in the database.

    Args:
        db_path: Optional database path override.
        reset: If True, re-classify ALL comments. If False (default),
               only classify comments where category IS NULL.
        use_ai: If True (default), use Claude API for classification.
                Falls back to pattern matching if API key not available.
    """
    conn = get_connection(db_path)
    init_db(conn)

    categories = load_categories()

    if reset:
        print("WARNING: Resetting all classifications...")
        conn.execute(
            "UPDATE comments SET category = NULL, classification_method = NULL, classified_at = NULL"
        )
        conn.commit()

    comments = get_unclassified_comments(conn)
    if not comments:
        print("No unclassified comments found.")
        conn.close()
        return

    print(f"Classifying {len(comments)} comments...")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    counts = {}

    # Try Claude AI classification first
    if use_ai and api_key and HAS_ANTHROPIC:
        print("Using Claude API for classification...")
        batch_size = 20
        ai_classified = 0
        for i in range(0, len(comments), batch_size):
            batch = comments[i:i + batch_size]
            print(f"  Batch {i + 1}-{min(i + batch_size, len(comments))} of {len(comments)}...")
            results = ai_classify_batch(batch, api_key)
            if results:
                for idx, category in results.items():
                    comment = batch[idx]
                    update_comment_category(conn, comment_id=comment["id"], category=category, method="ai")
                    counts[category] = counts.get(category, 0) + 1
                    ai_classified += 1
            time.sleep(0.3)

        print(f"  AI classified: {ai_classified}/{len(comments)}")

        # Pattern fallback for any the AI missed
        remaining = get_unclassified_comments(conn)
        if remaining:
            print(f"  Pattern fallback for {len(remaining)} remaining...")
            for comment in remaining:
                category, method = classify_comment(comment["text"], categories)
                update_comment_category(conn, comment_id=comment["id"], category=category, method=method)
                counts[category] = counts.get(category, 0) + 1
    else:
        if use_ai and not api_key:
            print("No ANTHROPIC_API_KEY set — using pattern classification.")
        elif use_ai and not HAS_ANTHROPIC:
            print("anthropic package not installed — using pattern classification.")
            print("  Install with: pip install anthropic")
        else:
            print("Using pattern classification (AI disabled).")

        for comment in comments:
            category, method = classify_comment(comment["text"], categories)
            update_comment_category(conn, comment_id=comment["id"], category=category, method=method)
            counts[category] = counts.get(category, 0) + 1

    conn.close()

    print("\nClassification results:")
    for cat, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    print(f"Total: {sum(counts.values())}")


if __name__ == "__main__":
    import sys
    reset = "--reset" in sys.argv
    no_ai = "--no-ai" in sys.argv
    run(reset=reset, use_ai=not no_ai)
