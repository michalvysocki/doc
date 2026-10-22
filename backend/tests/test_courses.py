import uuid
from types import SimpleNamespace

from src.courses import _build_tree, _course_progress, _flatten_topics, merge_sources
from src.schemas import TopicNode


def make_node(title: str, children: list[TopicNode] | None = None) -> TopicNode:
    return TopicNode(
        title=title, description=f"{title} description", children=children or []
    )


def make_row(
    title: str,
    parent=None,
    has_explanation: bool = False,
    tasks_total: int = 0,
    tasks_solved: int = 0,
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        parent_id=parent.id if parent else None,
        title=title,
        description=f"{title} description",
        has_explanation=has_explanation,
        tasks_total=tasks_total,
        tasks_solved=tasks_solved,
    )


def titles_tree(nodes) -> list:
    return [(node.title, titles_tree(node.children)) for node in nodes]


def test_flatten_empty_tree():
    assert _flatten_topics([], uuid.uuid4()) == []


def test_flatten_sets_parents_positions_and_course():
    course_id = uuid.uuid4()
    tree = [make_node("A", [make_node("A1"), make_node("A2")]), make_node("B")]

    topics = _flatten_topics(tree, course_id)
    by_title = {topic.title: topic for topic in topics}

    assert [topic.title for topic in topics] == ["A", "A1", "A2", "B"]
    assert by_title["A"].parent_id is None
    assert by_title["B"].parent_id is None
    assert by_title["A1"].parent_id == by_title["A"].id
    assert by_title["A2"].parent_id == by_title["A"].id
    assert [by_title[t].position for t in ["A", "A1", "A2", "B"]] == [0, 0, 1, 1]
    assert all(topic.course_id == course_id for topic in topics)


def test_flatten_puts_parents_before_children():
    tree = [make_node("A", [make_node("A1", [make_node("A1a")])]), make_node("B")]

    topics = _flatten_topics(tree, uuid.uuid4())

    seen_ids = set()
    for topic in topics:
        assert topic.parent_id is None or topic.parent_id in seen_ids
        seen_ids.add(topic.id)


def test_flatten_gives_unique_ids():
    tree = [make_node("A", [make_node("A1"), make_node("A2")]), make_node("B")]

    topics = _flatten_topics(tree, uuid.uuid4())

    assert len({topic.id for topic in topics}) == len(topics)


def test_build_tree_empty():
    assert _build_tree([]) == []


def test_build_tree_nests_children_in_order():
    a = make_row("A")
    a1 = make_row("A1", parent=a)
    a2 = make_row("A2", parent=a)
    b = make_row("B")

    tree = _build_tree([a, a1, a2, b])

    assert titles_tree(tree) == [("A", [("A1", []), ("A2", [])]), ("B", [])]


def test_build_tree_works_when_child_comes_before_parent():
    a = make_row("A")
    a1 = make_row("A1", parent=a)

    tree = _build_tree([a1, a])

    assert titles_tree(tree) == [("A", [("A1", [])])]


def test_build_tree_keeps_has_explanation():
    a = make_row("A", has_explanation=True)
    b = make_row("B")

    tree = _build_tree([a, b])

    assert [node.has_explanation for node in tree] == [True, False]


def test_flatten_then_build_gives_back_the_same_tree():
    original = [
        make_node("A", [make_node("A1", [make_node("A1a")]), make_node("A2")]),
        make_node("B"),
    ]

    topics = _flatten_topics(original, uuid.uuid4())
    rows = [
        SimpleNamespace(
            id=t.id,
            parent_id=t.parent_id,
            title=t.title,
            description=t.description,
            has_explanation=False,
            tasks_total=0,
            tasks_solved=0,
        )
        for t in topics
    ]

    assert titles_tree(_build_tree(rows)) == titles_tree(original)


def test_build_tree_keeps_task_counts():
    a = make_row("A", tasks_total=7, tasks_solved=3)

    tree = _build_tree([a])

    assert (tree[0].tasks_total, tree[0].tasks_solved) == (7, 3)


def test_course_progress_empty():
    progress = _course_progress([])

    assert (progress.topics_total, progress.topics_completed) == (0, 0)


def test_course_progress_counts_nested_topics_and_completed_ones():
    a = make_row("A", tasks_total=2, tasks_solved=2)
    a1 = make_row("A1", parent=a, tasks_total=3, tasks_solved=1)
    a2 = make_row("A2", parent=a, tasks_total=1, tasks_solved=1)
    b = make_row("B")

    progress = _course_progress(_build_tree([a, a1, a2, b]))

    assert progress.topics_total == 4
    assert progress.topics_completed == 2


def test_topic_without_tasks_is_not_completed():
    progress = _course_progress(_build_tree([make_row("A", has_explanation=True)]))

    assert progress.topics_completed == 0


def test_merge_sources_keeps_first_of_duplicates():
    first = [
        {"kind": "web", "title": "A", "url": "https://a.dev"},
        {"kind": "file", "title": "notes.pdf"},
    ]
    second = [
        {"kind": "web", "title": "A again", "url": "https://a.dev"},
        {"kind": "file", "title": "notes.pdf"},
        {"kind": "file", "title": "exam.pdf"},
    ]

    assert merge_sources(first, None, second) == [*first, second[2]]
