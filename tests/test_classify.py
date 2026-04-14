import os
import json
import pytest
from unittest.mock import MagicMock, patch
from tools.classify_comments import load_categories, classify_by_keywords, classify_by_ai, classify_comment
from tools.db import get_connection, init_db, insert_channel, insert_video, insert_comment, get_unclassified_comments

TEST_DB = "data/test_comments.db"


@pytest.fixture(autouse=True)
def clean_db():
    os.makedirs("data", exist_ok=True)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_load_categories():
    categories = load_categories("config/categories.json")
    assert isinstance(categories, list)
    names = [c["name"] for c in categories]
    assert "mistake" in names
    assert "spam" in names
    assert "other" in names


def test_classify_by_keywords_question_mark():
    categories = load_categories("config/categories.json")
    result = classify_by_keywords("How do I use this tool?", categories)
    assert result == "question"


def test_classify_by_keywords_spam():
    categories = load_categories("config/categories.json")
    result = classify_by_keywords("Check out my channel for free stuff http://spam.com/free", categories)
    assert result == "spam"


def test_classify_by_keywords_mistake():
    categories = load_categories("config/categories.json")
    result = classify_by_keywords("You said the wrong thing at 3:20, actually it's different", categories)
    assert result == "mistake"


def test_classify_by_keywords_no_match():
    categories = load_categories("config/categories.json")
    result = classify_by_keywords("Nice video", categories)
    assert result is None


def test_classify_by_ai():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="testimonial")]
    )
    categories = load_categories("config/categories.json")
    result = classify_by_ai(mock_client, "This changed my life, I tried it and got amazing results!", categories)
    assert result == "testimonial"


def test_classify_by_ai_falls_back_to_other():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="unknown_category")]
    )
    categories = load_categories("config/categories.json")
    result = classify_by_ai(mock_client, "Random text", categories)
    assert result == "other"


def test_classify_comment_uses_keyword_first():
    categories = load_categories("config/categories.json")
    mock_client = MagicMock()
    category, method = classify_comment("What is this?", categories, mock_client)
    assert category == "question"
    assert method == "keyword"
    mock_client.messages.create.assert_not_called()


def test_classify_comment_falls_to_ai():
    categories = load_categories("config/categories.json")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="good_point")]
    )
    category, method = classify_comment("I really appreciate the depth here", categories, mock_client)
    assert category == "good_point"
    assert method == "ai"
