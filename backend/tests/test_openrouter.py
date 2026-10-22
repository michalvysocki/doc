import json

import pytest
from pydantic import ValidationError

from src import openrouter
from src.schemas import GeneratedTaskSet, TaskGrade, TopicMap


def fake_response(content):
    return lambda url, payload, timeout: {
        "choices": [{"message": {"content": content}}]
    }


def test_structured_query_parses_valid_json(monkeypatch):
    content = json.dumps({"tasks": [{"question": "Q1", "grading_notes": "N1"}]})
    monkeypatch.setattr(openrouter, "_post_to_openrouter", fake_response(content))

    result = openrouter._structured_query([], GeneratedTaskSet, "task_set", 10)

    assert isinstance(result, GeneratedTaskSet)
    assert result.tasks[0].question == "Q1"


def test_structured_query_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr(openrouter, "_post_to_openrouter", fake_response('{"x": 1}'))

    with pytest.raises(openrouter.OpenRouterError, match="invalid task_set"):
        openrouter._structured_query([], GeneratedTaskSet, "task_set", 10)


def test_structured_query_sends_strict_schema(monkeypatch):
    sent = {}

    def capture(url, payload, timeout):
        sent.update(payload)
        return {"choices": [{"message": {"content": '{"tasks": []}'}}]}

    monkeypatch.setattr(openrouter, "_post_to_openrouter", capture)
    openrouter._structured_query([], GeneratedTaskSet, "task_set", 10)

    json_schema = sent["response_format"]["json_schema"]
    assert json_schema["name"] == "task_set"
    assert json_schema["strict"] is True
    assert json_schema["schema"] == GeneratedTaskSet.model_json_schema()


def test_generate_topic_map_still_works(monkeypatch):
    content = json.dumps(
        {
            "course_title": "Rust",
            "topics": [{"title": "A", "description": "a", "children": []}],
        }
    )
    monkeypatch.setattr(openrouter, "_post_to_openrouter", fake_response(content))

    result = openrouter.generate_topic_map("Learn Rust")

    assert isinstance(result, TopicMap)
    assert result.course_title == "Rust"


def test_grading_messages_contain_task_notes_and_answer():
    messages = openrouter.build_grading_messages(
        "Explain &mut", "unique access", "My answer"
    )

    assert messages[0] == {
        "role": "system",
        "content": openrouter.GRADING_SYSTEM_PROMPT,
    }
    assert messages[1]["role"] == "user"
    assert "TASK:\nExplain &mut" in messages[1]["content"]
    assert "GRADING NOTES:\nunique access" in messages[1]["content"]
    assert "LEARNER'S ANSWER:\nMy answer" in messages[1]["content"]


def test_task_grade_accepts_only_known_verdicts():
    grade = TaskGrade.model_validate_json('{"verdict": "correct", "feedback": "Good"}')
    assert grade.verdict == "correct"

    with pytest.raises(ValidationError):
        TaskGrade.model_validate_json('{"verdict": "almost", "feedback": "Hm"}')

    with pytest.raises(ValidationError):
        TaskGrade.model_validate_json(
            '{"verdict": "correct", "feedback": "Good", "score": 90}'
        )


def capture_explanation_request(monkeypatch, **options) -> str:
    sent = {}

    def capture(url, payload, timeout):
        sent.update(payload)
        return {"choices": [{"message": {"content": "Lesson"}}]}

    monkeypatch.setattr(openrouter, "_post_to_openrouter", capture)
    openrouter.generate_topic_explanation(
        course_title="Rust",
        path=["Basics"],
        title="Borrowing",
        description="References",
        subtopics=[],
        **options,
    )
    return sent["messages"][1]["content"]


def test_explanation_request_without_extras_is_unchanged(monkeypatch):
    content = capture_explanation_request(monkeypatch)

    assert content == (
        "Course: Rust\n"
        "Topic path: Basics > Borrowing\n"
        "Topic: Borrowing\n"
        "Topic description: References"
    )


def test_explanation_request_ends_with_materials_and_instructions(monkeypatch):
    content = capture_explanation_request(
        monkeypatch,
        instructions="More examples",
        materials="COURSE MATERIALS:\n--- Fragment ---",
    )

    assert content.endswith(
        "Topic description: References\n"
        "\nCOURSE MATERIALS:\n--- Fragment ---\n"
        "\nLEARNER'S INSTRUCTIONS:\nMore examples"
    )


def capture_tasks_request(monkeypatch, **options) -> str:
    sent = {}

    def capture(url, payload, timeout):
        sent.update(payload)
        content = json.dumps({"tasks": [{"question": "Q", "grading_notes": "N"}]})
        return {"choices": [{"message": {"content": content}}]}

    monkeypatch.setattr(openrouter, "_post_to_openrouter", capture)
    openrouter.generate_tasks(
        course_title="Rust",
        path=["Basics"],
        title="Borrowing",
        lesson="Text",
        **options,
    )
    return sent["messages"][1]["content"]


def test_tasks_request_without_extras_is_unchanged(monkeypatch):
    content = capture_tasks_request(monkeypatch)

    assert content == "Course: Rust\nTopic path: Basics > Borrowing\n\nLESSON:\nText"


def test_tasks_request_ends_with_materials_and_instructions(monkeypatch):
    content = capture_tasks_request(
        monkeypatch, instructions="Harder", materials="COURSE MATERIALS:\n--- F ---"
    )

    assert content.endswith(
        "LESSON:\nText\n\nCOURSE MATERIALS:\n--- F ---\n\nLEARNER'S INSTRUCTIONS:\nHarder"
    )


def test_rebuild_request_has_goal_outline_materials_and_instructions(monkeypatch):
    sent = {}

    def capture(url, payload, timeout):
        sent.update(payload)
        return {"choices": [{"message": {"content": json.dumps({"topics": []})}}]}

    monkeypatch.setattr(openrouter, "_post_to_openrouter", capture)
    openrouter.generate_rebuild_plan(
        course_title="Rust",
        initial_prompt="Learn Rust",
        outline="- Basics (id: 1)",
        instructions="More async",
        materials="COURSE MATERIALS:\n--- F ---",
    )

    assert sent["messages"][1]["content"] == (
        "Course: Rust\n"
        "Course goal (the learner's original request): Learn Rust\n\n"
        "CURRENT OUTLINE:\n- Basics (id: 1)\n\n"
        "COURSE MATERIALS:\n--- F ---\n\n"
        "LEARNER'S INSTRUCTIONS:\nMore async"
    )
    assert sent["response_format"]["json_schema"]["name"] == "rebuild_plan"
