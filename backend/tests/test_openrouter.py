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

    result, sources = openrouter.generate_topic_map("Learn Rust")

    assert isinstance(result, TopicMap)
    assert result.course_title == "Rust"
    assert sources == []


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


def test_explanation_request_has_goal_and_outline_before_extras(monkeypatch):
    content = capture_explanation_request(
        monkeypatch,
        goal="Rust for ML",
        outline="- Basics\n  - Borrowing   <- current lesson",
        instructions="Simpler",
    )

    assert content == (
        "Course: Rust\n"
        "Learner's goal: Rust for ML\n"
        "Topic path: Basics > Borrowing\n"
        "Topic: Borrowing\n"
        "Topic description: References\n"
        "\nCOURSE OUTLINE:\n- Basics\n  - Borrowing   <- current lesson\n"
        "\nLEARNER'S INSTRUCTIONS:\nSimpler"
    )


def test_tasks_request_has_goal_under_course(monkeypatch):
    content = capture_tasks_request(monkeypatch, goal="Rust for ML")

    assert content == (
        "Course: Rust\nLearner's goal: Rust for ML\n"
        "Topic path: Basics > Borrowing\n\nLESSON:\nText"
    )


def citation(url: str, title: str | None = "Page") -> dict:
    return {"type": "url_citation", "url_citation": {"url": url, "title": title}}


def test_append_sources_leaves_content_without_citations():
    assert openrouter.append_sources("Answer", None) == "Answer"
    assert openrouter.append_sources("Answer", [{"type": "other"}]) == "Answer"


def test_append_sources_lists_unique_pages_in_order():
    annotations = [
        citation("https://a.dev", "A [docs]"),
        citation("https://b.dev", None),
        citation("https://a.dev", "A again"),
    ]

    result = openrouter.append_sources("Answer", annotations)

    assert result == (
        "Answer\n\n**Sources**\n"
        "- [A (docs)](https://a.dev)\n"
        "- [https://b.dev](https://b.dev)"
    )


def test_append_sources_keeps_at_most_max_sources():
    annotations = [citation(f"https://site{i}.dev") for i in range(12)]

    result = openrouter.append_sources("Answer", annotations)

    assert result.count("\n- [") == openrouter.MAX_SOURCES


def test_with_web_search_respects_the_switch(monkeypatch):
    monkeypatch.setattr(openrouter, "WEB_SEARCH_ENABLED", True)
    assert openrouter.with_web_search(["mine"]) == ["mine", openrouter.WEB_SEARCH_TOOL]

    monkeypatch.setattr(openrouter, "WEB_SEARCH_ENABLED", False)
    assert openrouter.with_web_search(["mine"]) == ["mine"]


def test_chat_request_offers_web_search_next_to_own_tools(monkeypatch):
    sent = {}

    def capture(url, payload, timeout):
        sent.update(payload)
        return {"choices": [{"message": {"content": "Hi"}}]}

    monkeypatch.setattr(openrouter, "WEB_SEARCH_ENABLED", True)
    monkeypatch.setattr(openrouter, "_post_to_openrouter", capture)
    openrouter.send_query_with_tools([], [{"type": "function"}])

    assert sent["tools"] == [{"type": "function"}, openrouter.WEB_SEARCH_TOOL]


@pytest.mark.parametrize("enabled", [True, False])
def test_lesson_request_uses_web_search_only_when_enabled(monkeypatch, enabled):
    sent = {}

    def capture(url, payload, timeout):
        sent.update(payload)
        message = {"content": "Lesson", "annotations": [citation("https://a.dev")]}
        return {"choices": [{"message": message}]}

    monkeypatch.setattr(openrouter, "WEB_SEARCH_ENABLED", enabled)
    monkeypatch.setattr(openrouter, "_post_to_openrouter", capture)
    lesson, sources = openrouter.generate_topic_explanation(
        "Rust", [], "Borrowing", "d", []
    )

    assert ("tools" in sent) is enabled
    assert lesson == "Lesson"
    assert sources == [{"kind": "web", "title": "Page", "url": "https://a.dev"}]


def capture_structured_request(monkeypatch, enabled: bool, **options):
    sent = {}

    def capture(url, payload, timeout):
        sent.update(payload)
        message = {
            "content": json.dumps({"tasks": [{"question": "Q", "grading_notes": "N"}]}),
            "annotations": [citation("https://a.dev")],
        }
        return {"choices": [{"message": message}]}

    monkeypatch.setattr(openrouter, "WEB_SEARCH_ENABLED", enabled)
    monkeypatch.setattr(openrouter, "_post_to_openrouter", capture)
    result = openrouter._structured_query_with_sources(
        [], GeneratedTaskSet, "task_set", 10, **options
    )
    return sent, result


def test_structured_query_can_search_and_return_sources(monkeypatch):
    sent, (result, sources) = capture_structured_request(
        monkeypatch, True, web_search=True
    )

    assert sent["tools"] == [openrouter.WEB_SEARCH_TOOL]
    assert result.tasks[0].question == "Q"
    assert sources == [{"kind": "web", "title": "Page", "url": "https://a.dev"}]


@pytest.mark.parametrize(("enabled", "web_search"), [(True, False), (False, True)])
def test_structured_query_sends_no_tools_without_search(
    monkeypatch, enabled, web_search
):
    sent, _ = capture_structured_request(monkeypatch, enabled, web_search=web_search)

    assert "tools" not in sent


def test_tasks_and_grading_never_search(monkeypatch):
    sent = []

    def capture(url, payload, timeout):
        sent.append(payload)
        content = (
            json.dumps({"tasks": [{"question": "Q", "grading_notes": "N"}]})
            if len(sent) == 1
            else json.dumps({"verdict": "correct", "feedback": "Good"})
        )
        return {"choices": [{"message": {"content": content}}]}

    monkeypatch.setattr(openrouter, "WEB_SEARCH_ENABLED", True)
    monkeypatch.setattr(openrouter, "_post_to_openrouter", capture)
    openrouter.generate_tasks("Rust", [], "Borrowing", "Text")
    openrouter.grade_answer("Q", "N", "A")

    assert all("tools" not in payload for payload in sent)


def test_extract_web_sources_keeps_original_titles():
    annotations = [
        citation("https://a.dev", "A [docs]"),
        citation("https://b.dev", None),
    ]

    assert openrouter.extract_web_sources(annotations) == [
        {"kind": "web", "title": "A [docs]", "url": "https://a.dev"},
        {"kind": "web", "title": "https://b.dev", "url": "https://b.dev"},
    ]


def test_get_embeddings_sends_batches_and_keeps_order(monkeypatch):
    batches = []

    def fake_post(url, payload, timeout):
        batch = payload["input"]
        batches.append(len(batch))
        items = [
            {"index": i, "embedding": [float(text)]} for i, text in enumerate(batch)
        ]
        return {"data": list(reversed(items))}

    monkeypatch.setattr(openrouter, "_post_to_openrouter", fake_post)
    texts = [str(i) for i in range(250)]

    embeddings = openrouter.get_embeddings(texts)

    assert batches == [100, 100, 50]
    assert embeddings == [[float(i)] for i in range(250)]


def test_get_embeddings_single_text_is_one_request(monkeypatch):
    calls = []
    monkeypatch.setattr(
        openrouter,
        "_post_to_openrouter",
        lambda url, payload, timeout: (
            calls.append(1),
            {"data": [{"index": 0, "embedding": [1.0]}]},
        )[1],
    )

    assert openrouter.get_embeddings(["q"]) == [[1.0]]
    assert calls == [1]


def test_get_embeddings_rejects_missing_vectors(monkeypatch):
    monkeypatch.setattr(
        openrouter,
        "_post_to_openrouter",
        lambda url, payload, timeout: {"data": [{"index": 0, "embedding": [1.0]}]},
    )

    with pytest.raises(openrouter.OpenRouterError, match="wrong number of embeddings"):
        openrouter.get_embeddings(["a", "b"])


def test_topic_map_request_adds_materials_after_the_prompt(monkeypatch):
    sent = {}

    def capture(url, payload, timeout):
        sent.update(payload)
        content = json.dumps({"course_title": "Rust", "topics": []})
        return {"choices": [{"message": {"content": content}}]}

    monkeypatch.setattr(openrouter, "_post_to_openrouter", capture)
    openrouter.generate_topic_map("Learn Rust")
    assert sent["messages"][1]["content"] == "Learn Rust"

    openrouter.generate_topic_map("Learn Rust", "COURSE MATERIALS:\n--- F ---")
    assert sent["messages"][1]["content"] == (
        "Learn Rust\n\nCOURSE MATERIALS:\n--- F ---"
    )
