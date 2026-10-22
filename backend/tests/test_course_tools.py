import json
import uuid

import pytest

from src import chat, course_tools
from src.course_rebuilds import RebuildError
from src.courses import TopicPlacementError, _flatten_topics
from src.openrouter import OpenRouterError
from src.schemas import (
    CourseRebuildOut,
    RebuildDeletedTopic,
    TopicDeletionOut,
    TopicNode,
    TopicOut,
)


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


def test_run_topic_tool_rejects_unknown_tool():
    result = course_tools.run_topic_tool(uuid.uuid4(), uuid.uuid4(), "add_topics", "{}")

    assert result == ("Error: unknown tool add_topics", False)


def test_run_topic_tool_adds_under_current_topic(monkeypatch):
    received = {}

    def fake_add(course_id, parent_id, after_id, nodes):
        received.update(parent=parent_id, after=after_id, count=len(nodes))
        return ["Lifetimes"]

    monkeypatch.setattr(course_tools, "add_topics", fake_add)
    topic_id = uuid.uuid4()
    arguments = json.dumps(
        {
            "after_topic_id": None,
            "topics": [{"title": "Lifetimes", "description": "d", "children": []}],
        }
    )

    result = course_tools.run_topic_tool(
        uuid.uuid4(), topic_id, "add_subtopics", arguments
    )

    assert result == ("Added 1 topics: Lifetimes", True)
    assert received == {"parent": topic_id, "after": None, "count": 1}


def test_run_topic_tool_does_not_accept_parent(monkeypatch):
    monkeypatch.setattr(course_tools, "add_topics", lambda *args: ["X"])
    arguments = json.dumps(
        {"parent_topic_id": str(uuid.uuid4()), "after_topic_id": None, "topics": []}
    )

    result, changed = course_tools.run_topic_tool(
        uuid.uuid4(), uuid.uuid4(), "add_subtopics", arguments
    )

    assert result.startswith("Error: invalid arguments")
    assert changed is False


def tasks_arguments(count: int) -> str:
    return json.dumps(
        {"tasks": [{"question": "Q", "grading_notes": "N"} for _ in range(count)]}
    )


def test_run_topic_tool_adds_tasks_to_current_topic(monkeypatch):
    received = {}

    def fake_add(topic_id, tasks):
        received.update(topic=topic_id, count=len(tasks))
        return [4, 5]

    monkeypatch.setattr(course_tools, "add_tasks", fake_add)
    topic_id = uuid.uuid4()

    result = course_tools.run_topic_tool(
        uuid.uuid4(), topic_id, "add_tasks", tasks_arguments(2)
    )

    assert result == ("Added tasks: 4, 5", True)
    assert received == {"topic": topic_id, "count": 2}


@pytest.mark.parametrize("count", [0, 6])
def test_run_topic_tool_limits_number_of_tasks(monkeypatch, count):
    monkeypatch.setattr(course_tools, "add_tasks", lambda *args: [1])

    result, changed = course_tools.run_topic_tool(
        uuid.uuid4(), uuid.uuid4(), "add_tasks", tasks_arguments(count)
    )

    assert result.startswith("Error: invalid arguments")
    assert changed is False


def test_run_topic_tool_reports_missing_lesson(monkeypatch):
    def fail(*args):
        raise course_tools.LessonMissingError()

    monkeypatch.setattr(course_tools, "add_tasks", fail)

    result = course_tools.run_topic_tool(
        uuid.uuid4(), uuid.uuid4(), "add_tasks", tasks_arguments(1)
    )

    assert result == ("Error: the lesson has not been generated yet", False)


def rename_arguments(title: str, topic_id: str | None = None) -> str:
    return json.dumps(
        {
            "topic_id": topic_id or str(uuid.uuid4()),
            "title": title,
            "description": None,
        }
    )


def test_run_course_tool_renames_topic(monkeypatch):
    received = {}

    def fake_rename(course_id, topic_id, title, description):
        received.update(topic=topic_id, title=title, description=description)
        return "Old"

    monkeypatch.setattr(course_tools, "rename_topic", fake_rename)
    topic_id = uuid.uuid4()

    result = course_tools.run_course_tool(
        uuid.uuid4(), "rename_topic", rename_arguments("  New  ", str(topic_id))
    )

    assert result == ("Renamed 'Old' to 'New'", True)
    assert received == {"topic": topic_id, "title": "New", "description": None}


def test_run_course_tool_reports_topic_outside_course(monkeypatch):
    monkeypatch.setattr(course_tools, "rename_topic", lambda *args: None)

    result = course_tools.run_course_tool(
        uuid.uuid4(), "rename_topic", rename_arguments("New")
    )

    assert result == ("Error: topic not found in this course", False)


@pytest.mark.parametrize("title", ["   ", "x" * 256])
def test_run_course_tool_rejects_bad_title(monkeypatch, title):
    monkeypatch.setattr(course_tools, "rename_topic", lambda *args: "Old")

    result, changed = course_tools.run_course_tool(
        uuid.uuid4(), "rename_topic", rename_arguments(title)
    )

    assert result.startswith("Error: invalid arguments")
    assert changed is False


@pytest.mark.parametrize("after", [None, "first"])
def test_run_course_tool_moves_topic(monkeypatch, after):
    received = {}

    def fake_move(course_id, topic_id, parent_id, after_id):
        received.update(topic=topic_id, parent=parent_id, after=after_id)
        return "Lifetimes"

    monkeypatch.setattr(course_tools, "move_topic", fake_move)
    topic_id, parent_id = uuid.uuid4(), uuid.uuid4()
    arguments = json.dumps(
        {
            "topic_id": str(topic_id),
            "parent_topic_id": str(parent_id),
            "after_topic_id": after,
        }
    )

    result = course_tools.run_course_tool(uuid.uuid4(), "move_topic", arguments)

    assert result == ("Moved 'Lifetimes'", True)
    assert received == {"topic": topic_id, "parent": parent_id, "after": after}


def test_run_course_tool_reports_move_error(monkeypatch):
    def fail(*args):
        raise TopicPlacementError("a topic cannot be moved inside itself")

    monkeypatch.setattr(course_tools, "move_topic", fail)
    arguments = json.dumps(
        {"topic_id": str(uuid.uuid4()), "parent_topic_id": None, "after_topic_id": None}
    )

    result = course_tools.run_course_tool(uuid.uuid4(), "move_topic", arguments)

    assert result == ("Error: a topic cannot be moved inside itself", False)


def deletion_arguments(topic_id: uuid.UUID) -> str:
    return json.dumps({"topic_id": str(topic_id)})


def test_run_course_tool_proposes_deletion(monkeypatch):
    topic_id = uuid.uuid4()
    deletion = TopicDeletionOut(
        id=uuid.uuid4(),
        topic_id=topic_id,
        topic_title="Async",
        subtopics=2,
        lessons=1,
        tasks=3,
        attempts=4,
    )
    monkeypatch.setattr(
        course_tools, "propose_topic_deletion", lambda course_id, topic: deletion
    )

    result, changed = course_tools.run_course_tool(
        uuid.uuid4(), "propose_topic_deletion", deletion_arguments(topic_id)
    )

    assert result.startswith("Deletion of 'Async' proposed; nothing is deleted yet.")
    assert "2 subtopics, 1 lessons, 3 tasks and 4 attempts" in result
    assert changed is True


def test_run_course_tool_reports_deletion_outside_course(monkeypatch):
    monkeypatch.setattr(course_tools, "propose_topic_deletion", lambda *args: None)

    result = course_tools.run_course_tool(
        uuid.uuid4(), "propose_topic_deletion", deletion_arguments(uuid.uuid4())
    )

    assert result == ("Error: topic not found in this course", False)


def rebuild_out(deleted_titles: list[str]) -> CourseRebuildOut:
    return CourseRebuildOut(
        id=uuid.uuid4(),
        topics=[],
        deleted=[
            RebuildDeletedTopic(
                topic_id=uuid.uuid4(),
                title=title,
                has_explanation=False,
                tasks=0,
                attempts=0,
            )
            for title in deleted_titles
        ],
        kept_count=4,
        new_count=2,
    )


def rebuild_arguments(instructions: str | None = "More async") -> str:
    return json.dumps({"instructions": instructions, "use_files": True})


def test_run_course_tool_proposes_rebuild(monkeypatch):
    received = {}

    def fake_propose(course_id, instructions, use_files):
        received.update(instructions=instructions, use_files=use_files)
        return uuid.uuid4()

    monkeypatch.setattr(course_tools, "propose_course_rebuild", fake_propose)
    monkeypatch.setattr(
        course_tools, "get_course_rebuild", lambda course_id: rebuild_out(["Old"])
    )

    result, changed = course_tools.run_course_tool(
        uuid.uuid4(), "propose_course_rebuild", rebuild_arguments()
    )

    assert result.startswith("Course rebuild proposed; nothing is changed yet.")
    assert "keep 4 topics, add 2 and delete 1. Deleted topics include: Old." in result
    assert changed is True
    assert received == {"instructions": "More async", "use_files": True}


def test_rebuild_summary_lists_at_most_ten_deleted_titles():
    summary = course_tools._rebuild_summary(rebuild_out([f"T{i}" for i in range(12)]))

    assert "delete 12." in summary
    assert "T9." in summary
    assert "T10" not in summary


@pytest.mark.parametrize(
    "error", [OpenRouterError("timeout"), RebuildError("the plan has no topics")]
)
def test_run_course_tool_reports_rebuild_failure(monkeypatch, error):
    def fail(*args):
        raise error

    monkeypatch.setattr(course_tools, "propose_course_rebuild", fail)

    result, changed = course_tools.run_course_tool(
        uuid.uuid4(), "propose_course_rebuild", rebuild_arguments()
    )

    assert result == f"Error: generating the new course map failed: {error}"
    assert changed is False


def test_run_course_tool_rejects_too_long_rebuild_instructions():
    result, changed = course_tools.run_course_tool(
        uuid.uuid4(), "propose_course_rebuild", rebuild_arguments("x" * 2001)
    )

    assert result.startswith("Error: invalid arguments")
    assert changed is False


def regeneration_arguments(instructions: str | None = "Simpler") -> str:
    return json.dumps({"instructions": instructions, "use_files": True})


@pytest.mark.parametrize(
    ("tool", "kind"),
    [
        ("propose_lesson_regeneration", "lesson"),
        ("propose_tasks_regeneration", "tasks"),
    ],
)
def test_run_topic_tool_proposes_regeneration(monkeypatch, tool, kind):
    received = {}

    def fake_propose(topic_id, kind, instructions, use_files):
        received.update(topic=topic_id, kind=kind, instructions=instructions)
        received["use_files"] = use_files

    monkeypatch.setattr(course_tools, "propose_regeneration", fake_propose)
    topic_id = uuid.uuid4()

    result, changed = course_tools.run_topic_tool(
        uuid.uuid4(), topic_id, tool, regeneration_arguments()
    )

    assert result.startswith(f"Regeneration of the {kind} proposed;")
    assert changed is True
    assert received == {
        "topic": topic_id,
        "kind": kind,
        "instructions": "Simpler",
        "use_files": True,
    }


def test_run_topic_tool_reports_missing_lesson_for_task_regeneration(monkeypatch):
    def fail(*args):
        raise course_tools.LessonMissingError()

    monkeypatch.setattr(course_tools, "propose_regeneration", fail)

    result = course_tools.run_topic_tool(
        uuid.uuid4(),
        uuid.uuid4(),
        "propose_tasks_regeneration",
        regeneration_arguments(),
    )

    assert result == ("Error: the lesson has not been generated yet", False)


def test_run_topic_tool_rejects_too_long_regeneration_instructions():
    result, changed = course_tools.run_topic_tool(
        uuid.uuid4(),
        uuid.uuid4(),
        "propose_lesson_regeneration",
        regeneration_arguments("x" * 2001),
    )

    assert result.startswith("Error: invalid arguments")
    assert changed is False


def test_ask_with_tools_appends_sources_of_the_final_answer(monkeypatch):
    message = {
        "content": "Rust 1.90 is the latest",
        "annotations": [
            {
                "type": "url_citation",
                "url_citation": {"url": "https://x.dev", "title": "X"},
            }
        ],
    }
    monkeypatch.setattr(chat, "send_query_with_tools", lambda messages, tools: message)

    answer, changed = chat._ask_with_tools([], ["tool"], lambda name, args: ("", False))

    assert answer == "Rust 1.90 is the latest\n\n**Sources**\n- [X](https://x.dev)"
    assert changed is False
