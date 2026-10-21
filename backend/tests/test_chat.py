import uuid
from datetime import UTC, datetime

from src.chat import (
    HISTORY_LIMIT,
    MAX_CHARS_IN_TASK_CONTEXT,
    build_course_chat_messages,
    build_topic_chat_messages,
    format_course_outline,
    format_outline_with_progress,
    format_tasks_for_chat,
)
from src.schemas import (
    AttachmentOut,
    AttemptOut,
    ChatMessageOut,
    CourseOut,
    CourseProgress,
    TaskOut,
    TopicDetail,
    TopicLink,
    TopicOut,
)


def make_topic_out(title: str, children: list[TopicOut] | None = None) -> TopicOut:
    return TopicOut(
        id=uuid.uuid4(),
        title=title,
        description=f"{title} description",
        has_explanation=False,
        tasks_total=0,
        tasks_solved=0,
        children=children or [],
    )


def make_topic_detail(explanation: str | None = "Lesson text") -> TopicDetail:
    return TopicDetail(
        id=uuid.uuid4(),
        course_id=uuid.uuid4(),
        course_title="Rust",
        path=[TopicLink(id=uuid.uuid4(), title="Basics")],
        title="Borrowing",
        description="Borrowing description",
        explanation=explanation,
        subtopics=[],
    )


def make_message(
    message_id: int, role: str, content: str, attachments: list[str] | None = None
) -> ChatMessageOut:
    return ChatMessageOut(
        id=message_id,
        role=role,
        content=content,
        created_at=datetime.now(UTC),
        attachments=[
            AttachmentOut(file_uuid=uuid.uuid4(), filename=name)
            for name in attachments or []
        ],
    )


def test_outline_indents_levels_and_marks_current_topic():
    current = make_topic_out("A1a")
    topics = [
        make_topic_out("A", [make_topic_out("A1", [current])]),
        make_topic_out("B"),
    ]

    outline = format_course_outline(topics, current.id)

    assert outline.splitlines() == [
        "- A",
        "  - A1",
        "    - A1a   <- current lesson",
        "- B",
    ]


def test_outline_without_current_topic_has_no_marker():
    outline = format_course_outline([make_topic_out("A")], uuid.uuid4())

    assert "<- current lesson" not in outline


def test_system_prompt_contains_course_outline_and_lesson():
    messages = build_topic_chat_messages(make_topic_detail(), "- Basics", [], [], [])
    system = messages[0]

    assert system["role"] == "system"
    assert "COURSE: Rust" in system["content"]
    assert "COURSE OUTLINE:\n- Basics" in system["content"]
    assert "CURRENT LESSON: Basics > Borrowing" in system["content"]
    assert "Lesson text" in system["content"]


def test_missing_lesson_is_explained_to_the_model():
    messages = build_topic_chat_messages(make_topic_detail(None), "", [], [], [])

    assert "(The lesson has not been generated yet.)" in messages[0]["content"]


def test_fragments_section_only_when_fragments_exist():
    without = build_topic_chat_messages(make_topic_detail(), "", [], [], [])
    with_fragments = build_topic_chat_messages(
        make_topic_detail(),
        "",
        [{"text": "chunk text", "metadata": {"filename": "notes.pdf"}}],
        [],
        [],
    )

    expected = "--- Fragment of the document: notes.pdf ---\nchunk text"

    assert "COURSE MATERIALS" not in without[0]["content"]
    assert expected in with_fragments[0]["content"]


def test_history_is_limited_to_the_most_recent_messages():
    history = [
        make_message(i, "user" if i % 2 else "assistant", f"message {i}")
        for i in range(1, 26)
    ]

    messages = build_topic_chat_messages(make_topic_detail(), "", [], history, [])

    assert len(messages) == 1 + HISTORY_LIMIT
    assert messages[1]["content"] == "message 6"
    assert messages[-1]["content"] == "message 25"


def test_attachments_are_mentioned_in_message_content():
    history = [make_message(1, "user", "Look at this", ["notes.pdf", "plan.docx"])]

    messages = build_topic_chat_messages(make_topic_detail(), "", [], history, [])

    assert messages[1] == {
        "role": "user",
        "content": "Look at this\n\n[Attached files: notes.pdf, plan.docx]",
    }


def make_task(question: str, attempts: list[AttemptOut] | None = None) -> TaskOut:
    return TaskOut(
        id=uuid.uuid4(), position=0, question=question, attempts=attempts or []
    )


def make_attempt(answer: str, verdict=None, feedback=None) -> AttemptOut:
    return AttemptOut(
        id=1,
        answer=answer,
        verdict=verdict,
        feedback=feedback,
        created_at=datetime.now(UTC),
    )


def test_tasks_are_numbered_from_one_with_latest_attempt():
    tasks = [
        make_task(
            "Explain moves",
            [
                make_attempt("first try", "incorrect", "Wrong"),
                make_attempt("second try", "partially_correct", "Almost"),
            ],
        ),
        make_task("Write a function"),
    ]

    assert format_tasks_for_chat(tasks).splitlines() == [
        "Task 1: Explain moves",
        "  Learner's latest answer (partially_correct): second try",
        "  Feedback: Almost",
        "Task 2: Write a function",
        "  Not attempted yet.",
    ]


def test_ungraded_attempt_is_marked_and_has_no_feedback_line():
    text = format_tasks_for_chat([make_task("Q", [make_attempt("A")])])

    assert "Learner's latest answer (not graded): A" in text
    assert "Feedback" not in text


def test_long_texts_are_shortened():
    long_answer = "x" * (MAX_CHARS_IN_TASK_CONTEXT + 100)

    text = format_tasks_for_chat([make_task("Q", [make_attempt(long_answer)])])

    assert ("x" * MAX_CHARS_IN_TASK_CONTEXT + "…") in text
    assert ("x" * (MAX_CHARS_IN_TASK_CONTEXT + 1)) not in text


def test_tasks_section_only_when_tasks_exist():
    without = build_topic_chat_messages(make_topic_detail(), "", [], [], [])
    with_tasks = build_topic_chat_messages(
        make_topic_detail(), "", [], [], [make_task("Explain moves")]
    )

    assert "PRACTICE TASKS" not in without[0]["content"]
    assert "PRACTICE TASKS:\nTask 1: Explain moves" in with_tasks[0]["content"]


def make_progress_topic(
    title: str,
    children: list[TopicOut] | None = None,
    has_explanation: bool = False,
    tasks_total: int = 0,
    tasks_solved: int = 0,
) -> TopicOut:
    return TopicOut(
        id=uuid.uuid4(),
        title=title,
        description="",
        has_explanation=has_explanation,
        tasks_total=tasks_total,
        tasks_solved=tasks_solved,
        children=children or [],
    )


def make_course(topics: list[TopicOut]) -> CourseOut:
    return CourseOut(
        id=uuid.uuid4(),
        title="Rust",
        initial_prompt="I want to learn Rust",
        created_at=datetime.now(UTC),
        topics=topics,
        progress=CourseProgress(topics_total=3, topics_completed=1),
    )


def test_outline_with_progress_shows_markers_only_when_relevant():
    topics = [
        make_progress_topic(
            "Basics",
            [
                make_progress_topic(
                    "Borrowing", has_explanation=True, tasks_total=7, tasks_solved=7
                ),
                make_progress_topic("Cargo", has_explanation=True),
            ],
            has_explanation=True,
            tasks_total=7,
            tasks_solved=2,
        ),
        make_progress_topic("Async"),
    ]

    assert format_outline_with_progress(topics).splitlines() == [
        "- Basics [lesson ready, tasks 2/7]",
        "  - Borrowing [lesson ready, completed]",
        "  - Cargo [lesson ready]",
        "- Async",
    ]


def test_course_chat_system_prompt_contains_goal_progress_and_outline():
    messages = build_course_chat_messages(
        make_course([]), "- Basics [lesson ready]", [], []
    )
    system = messages[0]["content"]

    assert messages[0]["role"] == "system"
    assert "COURSE: Rust" in system
    assert "LEARNER'S GOAL: I want to learn Rust" in system
    assert "PROGRESS: 1 / 3 topics completed" in system
    assert "COURSE OUTLINE:\n- Basics [lesson ready]" in system
    assert "COURSE MATERIALS" not in system


def test_course_chat_includes_fragments_and_limited_history():
    history = [make_message(i, "user", f"message {i}") for i in range(1, 26)]
    fragments = [{"text": "chunk", "metadata": {"filename": "notes.pdf"}}]

    messages = build_course_chat_messages(make_course([]), "", fragments, history)

    assert (
        "--- Fragment of the document: notes.pdf ---\nchunk" in messages[0]["content"]
    )
    assert len(messages) == 1 + HISTORY_LIMIT
    assert messages[-1]["content"] == "message 25"


def test_fragments_are_labelled_as_lesson_or_document():
    fragments = [
        {"text": "a", "metadata": {"filename": "Borrowing", "is_lesson": True}},
        {"text": "b", "metadata": {"filename": "notes.pdf", "is_lesson": False}},
    ]

    messages = build_course_chat_messages(make_course([]), "", fragments, [])
    system = messages[0]["content"]

    assert "COURSE MATERIALS:\n--- Fragment of the lesson: Borrowing ---\na" in system
    assert "--- Fragment of the document: notes.pdf ---\nb" in system
