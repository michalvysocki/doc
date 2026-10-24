import uuid

import pytest

from src.course_rebuilds import (
    RebuildError,
    _count_nodes,
    _kept_ids,
    _preview,
    insert_topics,
    sanitize_plan,
)
from src.courses import TopicPlacementError
from src.schemas import RebuildTopicNode, TopicOut


def node(
    title: str,
    existing_topic_id: str | None = None,
    children: list[RebuildTopicNode] | None = None,
) -> RebuildTopicNode:
    return RebuildTopicNode(
        existing_topic_id=existing_topic_id,
        title=title,
        description="",
        children=children or [],
    )


def ids_by_title(nodes: list[RebuildTopicNode]) -> dict[str, str | None]:
    result = {}
    for item in nodes:
        result[item.title] = item.existing_topic_id
        result.update(ids_by_title(item.children))
    return result


def test_sanitize_keeps_valid_and_normalizes_case():
    kept = str(uuid.uuid4())

    result = sanitize_plan([node("A", kept.upper())], {kept})

    assert ids_by_title(result) == {"A": kept}


@pytest.mark.parametrize("bad_id", ["not-a-uuid", str(uuid.uuid4())])
def test_sanitize_turns_unknown_ids_into_new_topics(bad_id):
    result = sanitize_plan([node("A", bad_id)], {str(uuid.uuid4())})

    assert ids_by_title(result) == {"A": None}


def test_sanitize_keeps_only_first_use_of_an_id():
    kept = str(uuid.uuid4())
    plan = [node("A", kept, [node("A1", kept)]), node("B", kept)]

    result = sanitize_plan(plan, {kept})

    assert ids_by_title(result) == {"A": kept, "A1": None, "B": None}


def test_sanitize_allows_three_levels():
    plan = [node("A", children=[node("A1", children=[node("A1a")])])]

    result = sanitize_plan(plan, set())

    assert ids_by_title(result) == {"A": None, "A1": None, "A1a": None}


def test_sanitize_rejects_four_levels():
    plan = [node("A", children=[node("B", children=[node("C", children=[node("D")])])])]

    with pytest.raises(RebuildError, match="deeper than 3"):
        sanitize_plan(plan, set())


def topic_out(title: str, **progress) -> TopicOut:
    return TopicOut(
        id=uuid.uuid4(),
        title=title,
        description="",
        has_explanation=progress.get("has_explanation", False),
        tasks_total=progress.get("tasks_total", 0),
        tasks_solved=progress.get("tasks_solved", 0),
        children=[],
    )


def test_kept_ids_and_count_cover_the_whole_tree():
    kept = str(uuid.uuid4())
    plan = [node("A", children=[node("A1", kept)]), node("B")]

    assert _kept_ids(plan) == {kept}
    assert _count_nodes(plan) == 3


def test_preview_shows_progress_and_old_title_of_kept_topics():
    basics = topic_out("Basics", has_explanation=True, tasks_total=3, tasks_solved=1)
    plan = [node("Rust basics", str(basics.id), [node("Brand new")])]

    [kept] = _preview(plan, {basics.id: basics})
    [new] = kept.children

    assert (kept.topic_id, kept.old_title) == (basics.id, "Basics")
    assert (kept.has_explanation, kept.tasks_total, kept.tasks_solved) == (True, 3, 1)
    assert (new.topic_id, new.old_title, new.tasks_total) == (None, None, 0)


def test_preview_has_no_old_title_when_title_is_unchanged():
    basics = topic_out("Basics")

    [kept] = _preview([node("Basics", str(basics.id))], {basics.id: basics})

    assert kept.old_title is None


def plan_node(title, topic_id=None, *children):
    return RebuildTopicNode(
        existing_topic_id=topic_id,
        title=title,
        description="d",
        children=list(children),
    )


def plan_titles(nodes):
    return [(node.title, plan_titles(node.children)) for node in nodes]


def test_insert_topics_at_the_end_of_the_top_level():
    tree = [plan_node("Basics", "id-a"), plan_node("Async", "id-b")]

    where = insert_topics(tree, None, None, [plan_node("Networking")])

    assert where == 'at the top level, after "Async"'
    assert [title for title, _ in plan_titles(tree)] == [
        "Basics",
        "Async",
        "Networking",
    ]


def test_insert_topics_under_a_parent_after_a_sibling():
    tree = [
        plan_node(
            "Concurrency",
            "id-c",
            plan_node("Threads", "id-t"),
            plan_node("Channels", "id-ch"),
        )
    ]

    where = insert_topics(tree, "id-c", "id-t", [plan_node("Atomics")])

    assert where == 'under "Concurrency", after "Threads"'
    assert plan_titles(tree)[0][1] == [
        ("Threads", []),
        ("Atomics", []),
        ("Channels", []),
    ]


def test_insert_topics_as_the_first_child_of_an_empty_parent():
    tree = [plan_node("Macros", "id-m")]

    where = insert_topics(tree, "id-m", None, [plan_node("macro_rules!")])

    assert where == 'under "Macros", as the first'


@pytest.mark.parametrize(
    ("parent", "after", "message"),
    [
        ("id-unknown", None, "parent topic not found"),
        ("id-c", "id-other", "sibling topic not found"),
    ],
)
def test_insert_topics_rejects_a_wrong_place(parent, after, message):
    tree = [
        plan_node("Concurrency", "id-c", plan_node("Threads", "id-t")),
        plan_node("Other", "id-other"),
    ]

    with pytest.raises(TopicPlacementError, match=message):
        insert_topics(tree, parent, after, [plan_node("New")])
