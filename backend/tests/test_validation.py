from src.schemas import (
    GeneratedTask,
    GeneratedTaskSet,
    RebuildPlan,
    RebuildTopicNode,
    TopicMap,
    TopicNode,
)
from src.validation import (
    check_lesson,
    check_rebuild_plan,
    check_tasks,
    check_topic_map,
)


def node(title: str, *children: TopicNode, description: str = "About it") -> TopicNode:
    return TopicNode(title=title, description=description, children=list(children))


def rebuild_node(title: str, topic_id: str | None) -> RebuildTopicNode:
    return RebuildTopicNode(
        existing_topic_id=topic_id, title=title, description="About it", children=[]
    )


def test_good_map_has_no_issues():
    topic_map = TopicMap(
        course_title="Stats",
        topics=[node("Basics", node("Mean", node("Weighted mean"))), node("Tests")],
    )

    assert check_topic_map(topic_map) == []


def test_map_problems_are_reported():
    topic_map = TopicMap(
        course_title="Stats",
        topics=[
            node("A", node("B", node("C", node("Too deep")))),
            node("1. Basics"),
            node("Empty", description="  "),
            node("a"),
        ],
    )

    assert check_topic_map(topic_map) == [
        '"Too deep" is deeper than 3 levels.',
        '"1. Basics" is numbered; titles must not be numbered.',
        '"Empty" has no description.',
        '"a" appears more than once.',
    ]


def test_titles_with_numbers_inside_are_not_numbering():
    topic_map = TopicMap(
        course_title="Code",
        topics=[node("Python 3"), node("3D grafika"), node("Module 2: Loops")],
    )

    assert check_topic_map(topic_map) == [
        '"Module 2: Loops" is numbered; titles must not be numbered.'
    ]


def test_rebuild_plan_reports_unknown_and_repeated_ids():
    plan = RebuildPlan(
        topics=[
            rebuild_node("Kept", "id-1"),
            rebuild_node("Copy", "id-1"),
            rebuild_node("Lost", "id-9"),
            rebuild_node("New", None),
        ]
    )

    assert check_rebuild_plan(plan, {"id-1", "id-2"}) == [
        "Topic id id-1 is used more than once.",
        '"Lost" points to an unknown topic id id-9.',
    ]


def test_lesson_problems_are_reported():
    lesson = "## Borrowing\n\nText $$ x\n\n```rust\nlet a = 1;\n"

    assert check_lesson(lesson, "borrowing") == [
        "The lesson starts with a heading that repeats the topic title.",
        "A fenced code block is not closed.",
        "A $$ display formula is not closed.",
    ]


def test_dollars_inside_code_are_not_formulas():
    lesson = "## Why\n\n```bash\necho $$\n```\n\n$$\nx^2\n$$\n"

    assert check_lesson(lesson, "Borrowing") == []


def test_empty_lesson():
    assert check_lesson("  \n", "Borrowing") == ["The lesson is empty."]


def test_task_problems_are_reported():
    task_set = GeneratedTaskSet(
        tasks=[
            GeneratedTask(question="Explain the mean.", grading_notes="Sum / n"),
            GeneratedTask(question="Explain  the MEAN.", grading_notes="Sum / n"),
            GeneratedTask(question="Explain the median.", grading_notes=" "),
        ]
    )

    assert check_tasks(task_set) == [
        "Task 2 repeats an earlier question.",
        "Task 3 has no grading notes.",
    ]
