import os
import pytest
from tools.classify_comments import load_categories, classify_by_keywords, classify_comment

TEST_DB = "data/test_comments.db"


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


def test_classify_comment_uses_keyword():
    categories = load_categories("config/categories.json")
    category, method = classify_comment("What is this?", categories)
    assert category == "question"
    assert method == "keyword"


def test_classify_comment_falls_to_other():
    categories = load_categories("config/categories.json")
    category, method = classify_comment("Nice video", categories)
    assert category == "other"
    assert method == "unclassified"
