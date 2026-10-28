import logging
import uuid

from src.outline import format_outline_with_progress
from src.schemas import TopicOut
from src.topic_links import resolve_links

A, B, C, M = (uuid.uuid4() for _ in range(4))


D, N, P = (uuid.uuid4() for _ in range(3))


def test_links_to_earlier_topics_become_id_pairs():
    placed = [
        ("Ownership", A, [], (M,)),
        ("References", B, ["ownership"], (N,)),
        ("Lifetimes", C, ["References", "Ownership", "References"], (P,)),
    ]

    assert resolve_links(placed) == [(B, A), (C, B), (C, A)]


def test_link_to_the_previous_topic_of_the_same_module_is_dropped():
    placed = [
        ("Basics", M, [], ()),
        ("Ownership", A, [], (M,)),
        ("Borrowing rules", D, [], (M, A)),
        ("References", B, ["Ownership", "Borrowing rules"], (M,)),
        ("Lifetimes", C, ["Ownership", "References"], (M,)),
    ]

    assert resolve_links(placed) == [(B, D), (C, A)]


def test_wrong_links_are_skipped_and_logged(caplog):
    placed = [
        ("Module", M, [], ()),
        ("Ownership", A, ["Lifetimes", "Module", "Ownership", "Macros"], (M,)),
        ("Lifetimes", C, [], ()),
    ]

    with caplog.at_level(logging.WARNING, logger="src.topic_links"):
        assert resolve_links(placed) == []

    assert caplog.text.count("Skipped link") == 4


def topic(topic_id, title, requires=()):
    return TopicOut(
        id=topic_id,
        title=title,
        description="d",
        has_explanation=False,
        tasks_total=0,
        tasks_solved=0,
        requires=list(requires),
        children=[],
    )


def test_outline_lists_required_topics_by_title():
    topics = [topic(A, "Ownership"), topic(B, "References", [A])]

    outline = format_outline_with_progress(topics, include_requires=True)

    assert outline == "- Ownership\n- References (requires: Ownership)"
    assert "requires" not in format_outline_with_progress(topics)


def test_generate_topic_links_uses_the_planning_model(monkeypatch):
    import json

    from src import openrouter

    sent = {}

    def capture(url, payload, timeout):
        sent.update(payload)
        return {"choices": [{"message": {"content": json.dumps({"topics": []})}}]}

    monkeypatch.setattr(openrouter, "PLANNING_MODEL", "planner")
    monkeypatch.setattr(openrouter, "_post_to_openrouter", capture)

    openrouter.generate_topic_links("Rust", "Learn Rust", f"- Ownership (id: {A})")

    assert sent["model"] == "planner"
    assert f"(id: {A})" in sent["messages"][1]["content"]


def test_placed_from_plan_turns_ids_into_titles_and_skips_unknown_ones():
    from src.courses import _placed_from_plan
    from src.schemas import LinkPlan, TopicPrerequisites

    topics = [topic(A, "Ownership"), topic(B, "References"), topic(C, "Lifetimes")]
    plan = LinkPlan(
        topics=[
            TopicPrerequisites(topic_id=str(C), requires=[str(A), str(uuid.uuid4())]),
            TopicPrerequisites(topic_id=str(A), requires=[str(C)]),
        ]
    )

    placed = _placed_from_plan(topics, plan)

    assert placed[2] == ("Lifetimes", C, ["Ownership"], ())
    # Ownership "requires" a later topic: kept here, dropped by resolve_links.
    assert resolve_links(placed) == [(C, A)]


def test_required_titles_of_a_nested_topic():
    from src.outline import required_titles

    module = topic(M, "Basics").model_copy(
        update={
            "children": [topic(B, "References", [A]), topic(C, "Lifetimes", [A, B])]
        }
    )
    topics = [topic(A, "Ownership"), module]

    assert required_titles(topics, C) == ["Ownership", "References"]
    assert required_titles(topics, uuid.uuid4()) == []


def test_lesson_gets_the_topics_it_builds_on(monkeypatch):
    from src import openrouter

    sent = []

    def capture(url, payload, timeout):
        sent.append(payload["messages"][1]["content"])
        return {"choices": [{"message": {"content": "Lesson"}}]}

    monkeypatch.setattr(openrouter, "WEB_SEARCH_ENABLED", False)
    monkeypatch.setattr(openrouter, "REVIEW_ENABLED", False)
    monkeypatch.setattr(openrouter, "_post_to_openrouter", capture)

    openrouter.generate_topic_explanation(
        "Rust", [], "Lifetimes", "d", [], requires=["Ownership", "References"]
    )
    openrouter.generate_topic_explanation("Rust", [], "Lifetimes", "d", [])

    assert "Builds on (earlier topics): Ownership, References" in sent[0]
    assert "Builds on" not in sent[1]
