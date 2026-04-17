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
    result = classify_by_keywords("ok", categories)
    assert result is None


def test_classify_comment_question():
    category, method = classify_comment("What is this tool about?")
    assert category == "question"


def test_classify_comment_spam():
    category, method = classify_comment("Check out my channel subscribe to my page")
    assert category == "spam"


def test_classify_comment_testimonial():
    category, method = classify_comment("Love this video, great content!")
    assert category == "testimonial"


def test_classify_comment_complaint():
    category, method = classify_comment("This is such a waste of time")
    assert category == "complaint"


def test_classify_comment_idea():
    category, method = classify_comment("You should make a video about SEO tools")
    assert category == "idea"


def test_classify_comment_mistake():
    category, method = classify_comment("Actually it's not what you said, you made a mistake there")
    assert category == "mistake"


def test_classify_comment_short_other():
    category, method = classify_comment("ok")
    assert category == "other"


def test_classify_comment_good_point_long():
    category, method = classify_comment(
        "I think the real issue here is that most people don't understand how AI tools "
        "actually work under the hood, and they end up using them incorrectly which leads "
        "to poor results and frustration with the technology."
    )
    assert category == "good_point"
