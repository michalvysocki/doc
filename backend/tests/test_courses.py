import uuid
from types import SimpleNamespace

from src.courses import _build_tree, _flatten_topics
from src.schemas import TopicNode


def make_node(title: str, children: list[TopicNode] | None = None) -> TopicNode:
    return TopicNode(
        title=title, description=f"{title} description", children=children or []
    )


def make_row(title: str, parent=None, has_explanation: bool = False):
    return SimpleNamespace(
        id=uuid.uuid4(),
        parent_id=parent.id if parent else None,
        title=title,
        description=f"{title} description",
        has_explanation=has_explanation,
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
        )
        for t in topics
    ]

    assert titles_tree(_build_tree(rows)) == titles_tree(original)
