import json
import logging
import uuid

import pytest

from src import openrouter

DRAFT_MAP = {
    "course_title": "Stats",
    "topics": [{"title": "Basics", "description": "d", "children": []}],
}
REVISED_MAP = {
    "course_title": "Stats",
    "topics": [
        {"title": "Basics", "description": "d", "children": []},
        {"title": "Tests", "description": "d", "children": []},
    ],
}


@pytest.fixture(autouse=True)
def reviews_on(monkeypatch):
    monkeypatch.setattr(openrouter, "REVIEW_ENABLED", True)
    monkeypatch.setattr(openrouter, "WEB_SEARCH_ENABLED", False)


def fake_answers(monkeypatch, *contents):
    """The first call gets the draft, the second the review; returns sent payloads."""

    answers = iter(contents)
    sent = []

    def fake(url, payload, timeout):
        sent.append(payload)
        content = next(answers)
        if not isinstance(content, str):
            content = json.dumps(content)
        return {"choices": [{"message": {"content": content}}]}

    monkeypatch.setattr(openrouter, "_post_to_openrouter", fake)
    return sent


def titles(topic_map):
    return [topic.title for topic in topic_map.topics]


def test_map_review_can_revise_the_map(monkeypatch):
    fake_answers(
        monkeypatch, DRAFT_MAP, {"issues": ["Tests missing"], "revised": REVISED_MAP}
    )

    topic_map, _ = openrouter.generate_topic_map("Statistics")

    assert titles(topic_map) == ["Basics", "Tests"]


def test_map_review_without_changes_keeps_the_draft(monkeypatch, caplog):
    fake_answers(monkeypatch, DRAFT_MAP, {"issues": [], "revised": None})

    with caplog.at_level(logging.INFO, logger="src.openrouter"):
        topic_map, _ = openrouter.generate_topic_map("Statistics")

    assert titles(topic_map) == ["Basics"]
    assert 'Map review for "Stats": 0 issues, kept' in caplog.text


def test_failed_review_keeps_the_draft(monkeypatch, caplog):
    fake_answers(monkeypatch, DRAFT_MAP, "not json")

    with caplog.at_level(logging.WARNING, logger="src.openrouter"):
        topic_map, _ = openrouter.generate_topic_map("Statistics")

    assert titles(topic_map) == ["Basics"]
    assert "failed, keeping the draft" in caplog.text


def test_revision_with_more_problems_is_rejected(monkeypatch, caplog):
    empty = {"course_title": "Stats", "topics": []}
    fake_answers(monkeypatch, DRAFT_MAP, {"issues": ["x"], "revised": empty})

    with caplog.at_level(logging.WARNING, logger="src.openrouter"):
        topic_map, _ = openrouter.generate_topic_map("Statistics")

    assert titles(topic_map) == ["Basics"]
    assert "made it worse" in caplog.text


def test_lesson_review_replaces_the_text_and_keeps_the_sources(monkeypatch):
    citation = {
        "type": "url_citation",
        "url_citation": {"url": "https://a.dev", "title": "A"},
    }
    answers = iter(
        [
            {"content": "## Why\n\nDraft", "annotations": [citation]},
            {
                "content": json.dumps(
                    {"issues": ["x"], "revised_lesson": "## Why\n\nFixed"}
                )
            },
        ]
    )
    monkeypatch.setattr(
        openrouter,
        "_post_to_openrouter",
        lambda url, payload, timeout: {"choices": [{"message": next(answers)}]},
    )

    lesson, sources = openrouter.generate_topic_explanation(
        "Rust", [], "Borrowing", "d", []
    )

    assert lesson == "## Why\n\nFixed"
    assert sources == [{"kind": "web", "title": "A", "url": "https://a.dev"}]


def test_rebuild_review_gets_the_unknown_id_issue(monkeypatch):
    known = uuid.uuid4()
    unknown = uuid.uuid4()

    def node(title, topic_id):
        return {
            "existing_topic_id": topic_id,
            "title": title,
            "description": "d",
            "children": [],
        }

    plan = {"topics": [node("Kept", str(known).upper()), node("Lost", str(unknown))]}
    sent = fake_answers(monkeypatch, plan, {"issues": [], "revised": None})

    openrouter.generate_rebuild_plan(
        "Stats", "Statistics", "- Basics", existing_ids={str(known)}
    )

    checks = sent[1]["messages"][1]["content"].split("AUTOMATIC CHECKS:\n")[1]
    assert checks == f'- "Lost" points to an unknown topic id {unknown}.'


def test_follow_up_review_uses_follow_up_criteria_and_rejects_a_copy(
    monkeypatch, caplog
):
    original = "Explain the role of Cargo, the package and the binary crate."
    draft = {
        "question": "Is an unused function an error?",
        "grading_notes": "A warning",
    }
    copy = {"tasks": [{"question": original, "grading_notes": "N"}]}
    sent = fake_answers(monkeypatch, draft, {"issues": ["x"], "revised": copy})

    with caplog.at_level(logging.WARNING, logger="src.openrouter"):
        task = openrouter.generate_follow_up_task(
            "Rust",
            [],
            "Cargo",
            "Lesson",
            question=original,
            answer="a",
            verdict="partially_correct",
            feedback="f",
        )

    assert "Criteria for a follow-up task" in sent[1]["messages"][0]["content"]
    assert task.question == "Is an unused function an error?"
    assert "made it worse" in caplog.text
