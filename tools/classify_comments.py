import json
import os
import re
from typing import Optional

import anthropic
from dotenv import load_dotenv

from tools.db import get_connection, init_db, get_unclassified_comments, update_comment_category

load_dotenv()


def load_categories(config_path: str = "config/categories.json") -> list:
    with open(config_path, "r") as f:
        data = json.load(f)
    return data["categories"]


def classify_by_keywords(text: str, categories: list) -> Optional[str]:
    text_lower = text.lower()
    for cat in categories:
        if cat["name"] == "other":
            continue
        for keyword in cat.get("keywords", []):
            if keyword.lower() in text_lower:
                return cat["name"]
        for pattern in cat.get("patterns", []):
            if re.search(pattern, text, re.IGNORECASE):
                return cat["name"]
    return None


def classify_by_ai(client: anthropic.Anthropic, text: str, categories: list) -> str:
    category_descriptions = "\n".join(
        f'- "{cat["name"]}": {cat["description"]}'
        for cat in categories
    )
    prompt = f"""Classify this YouTube comment into exactly one category. Reply with ONLY the category name, nothing else.

Categories:
{category_descriptions}

Comment: "{text}"

Category:"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
        messages=[{"role": "user", "content": prompt}],
    )
    result = response.content[0].text.strip().lower().replace('"', "")
    valid_names = {cat["name"] for cat in categories}
    if result in valid_names:
        return result
    return "other"


def classify_comment(text: str, categories: list, ai_client: anthropic.Anthropic) -> tuple[str, str]:
    keyword_result = classify_by_keywords(text, categories)
    if keyword_result:
        return keyword_result, "keyword"
    ai_result = classify_by_ai(ai_client, text, categories)
    return ai_result, "ai"


def run(db_path: Optional[str] = None) -> None:
    conn = get_connection(db_path)
    init_db(conn)
    categories = load_categories()
    client = anthropic.Anthropic()
    comments = get_unclassified_comments(conn)
    print(f"Found {len(comments)} unclassified comments")
    keyword_count = 0
    ai_count = 0
    for comment in comments:
        category, method = classify_comment(comment["text"], categories, client)
        update_comment_category(conn, comment_id=comment["id"], category=category, method=method)
        if method == "keyword":
            keyword_count += 1
        else:
            ai_count += 1
    conn.close()
    print(f"Classified: {keyword_count} by keywords, {ai_count} by AI")


if __name__ == "__main__":
    run()
