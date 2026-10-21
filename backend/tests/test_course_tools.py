import json
import uuid

import pytest

from src import chat, course_tools
from src.courses import TopicPlacementError, _flatten_topics
from src.openrouter import OpenRouterError
from src.schemas import TopicNode, TopicOut


def tool_call(call_id: str, arguments: dict) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": "add_topics", "arguments": json.dumps(arguments)},
    }


def test_flatten_topics_starts_top_level_at_given_position():
    nodes = [
        TopicNode(
            title="A",
            description="",
            children=[TopicNode(title="A1", description="", children=[])],
        ),
        TopicNode(title="B", description="", children=[]),
    ]

    topics = _flatten_topics(nodes, uuid.uuid4(), start_position=5)
    positions = {topic.title: topic.position for topic in topics}

    assert positions == {"A": 5, "A1": 0, "B": 6}


def test_outline_can_include_topic_ids():
    topic = TopicOut(
        id=uuid.uuid4(),
        title="Basics",
        description="",
        has_explanation=False,
        tasks_total=0,
        tasks_solved=0,
        children=[],
    )

    outline = chat.format_outline_with_progress([topic], include_ids=True)

    assert outline == f"- Basics (id: {topic.id})"


def test_ask_with_tools_returns_text_answer_without_tools(monkeypatch):
    monkeypatch.setattr(
        chat, "send_query_with_tools", lambda messages, tools: {"content": "Hi"}
    )

    answer, changed = chat._ask_with_tools([], [], lambda name, args: ("", False))

    assert (answer, changed) == ("Hi", False)


def test_ask_with_tools_runs_tool_and_sends_result_back(monkeypatch):
    responses = iter(
        [
            {"content": None, "tool_calls": [tool_call("call_1", {"x": 1})]},
            {"content": "Added it"},
        ]
    )
    seen = []

    def fake_send(messages, tools):
        seen.append([dict(m) for m in messages])
        return next(responses)

    monkeypatch.setattr(chat, "send_query_with_tools", fake_send)
    calls = []

    def run_tool(name, arguments):
        calls.append((name, json.loads(arguments)))
        return "Added 1 topics: X", True

    messages = [{"role": "user", "content": "add X"}]
    answer, changed = chat._ask_with_tools(messages, ["tool"], run_tool)

    assert (answer, changed) == ("Added it", True)
    assert calls == [("add_topics", {"x": 1})]
    assert seen[1][-1] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "Added 1 topics: X",
    }


def test_ask_with_tools_stops_after_too_many_rounds(monkeypatch):
    monkeypatch.setattr(
        chat,
        "send_query_with_tools",
        lambda messages, tools: {"tool_calls": [tool_call("c", {})]},
    )

    with pytest.raises(OpenRouterError, match="too many times"):
        chat._ask_with_tools([], ["tool"], lambda name, args: ("ok", False))


def test_ask_with_tools_rejects_empty_answer(monkeypatch):
    monkeypatch.setattr(
        chat, "send_query_with_tools", lambda messages, tools: {"content": None}
    )

    with pytest.raises(OpenRouterError, match="empty answer"):
        chat._ask_with_tools([], ["tool"], lambda name, args: ("", False))


def test_run_course_tool_rejects_unknown_tool():
    assert course_tools.run_course_tool(uuid.uuid4(), "delete_course", "{}") == (
        "Error: unknown tool delete_course",
        False,
    )


def test_run_course_tool_reports_invalid_arguments():
    result, changed = course_tools.run_course_tool(uuid.uuid4(), "add_topics", "{}")

    assert result.startswith("Error: invalid arguments")
    assert changed is False


def test_run_course_tool_reports_bad_id():
    arguments = json.dumps(
        {"parent_topic_id": "not-a-uuid", "after_topic_id": None, "topics": []}
    )

    result, changed = course_tools.run_course_tool(
        uuid.uuid4(), "add_topics", arguments
    )

    assert result.startswith("Error:")
    assert changed is False


def test_run_course_tool_reports_placement_error(monkeypatch):
    def fail(*args):
        raise TopicPlacementError("parent topic not found in this course")

    monkeypatch.setattr(course_tools, "add_topics", fail)
    arguments = json.dumps(
        {"parent_topic_id": str(uuid.uuid4()), "after_topic_id": None, "topics": []}
    )

    result, changed = course_tools.run_course_tool(
        uuid.uuid4(), "add_topics", arguments
    )

    assert result == "Error: parent topic not found in this course"
    assert changed is False


def test_run_course_tool_adds_topics(monkeypatch):
    received = {}

    def fake_add(course_id, parent_id, after_id, nodes):
        received.update(parent=parent_id, after=after_id, count=len(nodes))
        return ["Async Rust", "Futures"]

    monkeypatch.setattr(course_tools, "add_topics", fake_add)
    parent = uuid.uuid4()
    arguments = json.dumps(
        {
            "parent_topic_id": str(parent),
            "after_topic_id": None,
            "topics": [
                {
                    "title": "Async Rust",
                    "description": "d",
                    "children": [
                        {"title": "Futures", "description": "d", "children": []}
                    ],
                }
            ],
        }
    )

    result, changed = course_tools.run_course_tool(
        uuid.uuid4(), "add_topics", arguments
    )

    assert (result, changed) == ("Added 2 topics: Async Rust, Futures", True)
    assert received == {"parent": parent, "after": None, "count": 1}
