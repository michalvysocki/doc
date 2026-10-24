import uuid
from datetime import UTC, datetime

import pytest

from src import chat
from src.chat import (
    MAX_CHARS_IN_TASK_CONTEXT,
    MAX_HISTORY_MESSAGES,
    build_course_chat_messages,
    build_topic_chat_messages,
    format_course_outline,
    format_outline_with_progress,
    format_tasks_for_chat,
    split_for_summary,
)
from src.openrouter import OpenRouterError
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
        for i in range(1, 36)
    ]

    messages = build_topic_chat_messages(make_topic_detail(), "", [], history, [])

    assert len(messages) == 1 + MAX_HISTORY_MESSAGES
    assert messages[1]["content"] == "message 6"
    assert messages[-1]["content"] == "message 35"


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
    history = [make_message(i, "user", f"message {i}") for i in range(1, 36)]
    fragments = [{"text": "chunk", "metadata": {"filename": "notes.pdf"}}]

    messages = build_course_chat_messages(make_course([]), "", fragments, history)

    assert (
        "--- Fragment of the document: notes.pdf ---\nchunk" in messages[0]["content"]
    )
    assert len(messages) == 1 + MAX_HISTORY_MESSAGES
    assert messages[-1]["content"] == "message 35"


def test_fragments_are_labelled_as_lesson_or_document():
    fragments = [
        {"text": "a", "metadata": {"filename": "Borrowing", "is_lesson": True}},
        {"text": "b", "metadata": {"filename": "notes.pdf", "is_lesson": False}},
    ]

    messages = build_course_chat_messages(make_course([]), "", fragments, [])
    system = messages[0]["content"]

    assert "COURSE MATERIALS:\n--- Fragment of the lesson: Borrowing ---\na" in system
    assert "--- Fragment of the document: notes.pdf ---\nb" in system


def test_topic_prompt_lists_subtopics_with_ids_and_level():
    topic = make_topic_detail()
    without = build_topic_chat_messages(topic, "", [], [], [])
    subtopic = TopicLink(id=uuid.uuid4(), title="Lifetimes")
    with_subtopics = build_topic_chat_messages(
        topic.model_copy(update={"subtopics": [subtopic]}), "", [], [], []
    )

    header = "SUBTOPICS OF THIS LESSON (lesson level 2 of max 3):\n"
    assert header + "(none)" in without[0]["content"]
    assert f"{header}- Lifetimes (id: {subtopic.id})" in with_subtopics[0]["content"]


def test_topic_prompt_has_goal_only_when_given():
    without = build_topic_chat_messages(make_topic_detail(), "- Basics", [], [], [])
    with_goal = build_topic_chat_messages(
        make_topic_detail(), "- Basics", [], [], [], goal="Rust for ML"
    )

    assert "LEARNER'S GOAL" not in without[0]["content"]
    assert (
        "COURSE: Rust\n\nLEARNER'S GOAL: Rust for ML\n\nCOURSE OUTLINE:"
        in (with_goal[0]["content"])
    )


def test_outline_can_include_descriptions():
    topic = make_topic_out("Basics", [make_topic_out("Borrowing")])

    outline = format_outline_with_progress([topic], include_descriptions=True)

    assert outline == (
        "- Basics: Basics description\n  - Borrowing: Borrowing description"
    )


def test_split_for_summary_keeps_short_conversations_whole():
    messages = [make_message(i, "user", f"m{i}") for i in range(1, 31)]

    assert split_for_summary(messages) == ([], messages)


def test_split_for_summary_folds_all_but_the_last_twenty():
    messages = [make_message(i, "user", f"m{i}") for i in range(1, 32)]

    to_summarize, to_keep = split_for_summary(messages)

    assert [m.id for m in to_summarize] == list(range(1, 12))
    assert [m.id for m in to_keep] == list(range(12, 32))


def test_summary_section_only_when_summary_exists():
    without = build_topic_chat_messages(make_topic_detail(), "", [], [], [])
    with_summary = build_course_chat_messages(
        make_course([]), "", [], [], summary="- asked about borrowing"
    )

    assert "EARLIER CONVERSATION" not in without[0]["content"]
    assert (
        "EARLIER CONVERSATION (summary):\n- asked about borrowing"
        in with_summary[0]["content"]
    )


def test_search_query_of_the_first_message_is_the_message(monkeypatch):
    monkeypatch.setattr(
        chat, "rewrite_search_query", lambda *args: pytest.fail("no rewrite")
    )

    assert chat._search_query([make_message(1, "user", "What is borrowing?")]) == (
        "What is borrowing?"
    )


def test_search_query_is_rewritten_with_recent_messages(monkeypatch):
    received = {}

    def fake_rewrite(recent, question, topic):
        received.update(recent=[m["content"] for m in recent], question=question)
        received["topic"] = topic
        return "mutable borrowing rules"

    monkeypatch.setattr(chat, "rewrite_search_query", fake_rewrite)
    history = [make_message(i, "user", f"m{i}") for i in range(1, 10)]

    query = chat._search_query(history, topic="Borrowing")

    assert query == "mutable borrowing rules"
    assert received == {
        "recent": ["m3", "m4", "m5", "m6", "m7", "m8"],
        "question": "m9",
        "topic": "Borrowing",
    }


def test_search_query_falls_back_to_the_message(monkeypatch):
    def fail(*args):
        raise chat.OpenRouterError("timeout")

    monkeypatch.setattr(chat, "rewrite_search_query", fail)
    history = [make_message(1, "user", "Hi"), make_message(2, "user", "and that?")]

    assert chat._search_query(history) == "and that?"


def test_course_files_section_only_when_given():
    without = build_course_chat_messages(make_course([]), "", [], [])
    with_files = build_topic_chat_messages(
        make_topic_detail(), "", [], [], [], course_files="COURSE FILES:\n- a.pdf: A"
    )

    assert "COURSE FILES" not in without[0]["content"]
    assert "COURSE FILES:\n- a.pdf: A" in with_files[0]["content"]


def msg(role: str, chars: int) -> dict:
    return {"role": role, "content": "x" * chars}


def test_estimate_tokens_counts_text_and_images():
    image_message = {
        "role": "user",
        "content": [
            {"type": "text", "text": "x" * 300},
            {"type": "image_url", "image_url": {"url": "data:"}},
        ],
    }

    assert chat.estimate_tokens([msg("user", 3000)]) == 1000
    assert chat.estimate_tokens([image_message]) == 100 + chat.IMAGE_TOKENS


def test_fit_to_budget_keeps_messages_that_fit():
    messages = [msg("system", 300), msg("user", 300), msg("assistant", 300)]

    assert chat.fit_to_budget(messages, budget=1000) == messages


def test_fit_to_budget_drops_the_oldest_history_first():
    messages = [msg("system", 300)] + [
        {"role": "user", "content": f"{i}" + "x" * 299} for i in range(5)
    ]

    fitted = chat.fit_to_budget(messages, budget=400)

    assert [m["content"][0] for m in fitted[1:]] == ["2", "3", "4"]
    assert fitted[0] == messages[0]


def test_fit_to_budget_always_keeps_system_and_last_message():
    messages = [msg("system", 3000), msg("user", 3000), msg("user", 3000)]

    fitted = chat.fit_to_budget(messages, budget=1)

    assert fitted == [messages[0], messages[-1]]


def test_cap_marks_cut_sections():
    assert chat._cap("short", 10) == "short"
    assert chat._cap("x" * 20, 10) == "x" * 10 + "\n[...truncated]"


def test_long_lesson_is_cut_in_the_topic_prompt():
    lesson = "y" * 100_000

    messages = build_topic_chat_messages(make_topic_detail(lesson), "", [], [], [])
    system = messages[0]["content"]

    assert "y" * chat.MAX_LESSON_CHARS_IN_CONTEXT + "\n[...truncated]" in system
    assert "y" * (chat.MAX_LESSON_CHARS_IN_CONTEXT + 1) not in system


def test_retry_without_an_unanswered_message_raises(monkeypatch):
    monkeypatch.setattr(chat, "_last_unanswered_message", lambda conversation_id: None)

    with pytest.raises(chat.NothingToRetryError):
        chat._user_message(uuid.uuid4(), None, [])


def fake_exchange_world(monkeypatch, last, stream):
    """Replaces the database and the model around _exchange; returns saved roles."""

    saved = []
    monkeypatch.setattr(
        chat, "_conversation_window", lambda conversation_id: (None, [last])
    )
    monkeypatch.setattr(
        chat,
        "add_message",
        lambda conversation_id, role, content, file_uuids=None: (
            saved.append(role),
            make_message(8, role, content),
        )[1],
    )
    monkeypatch.setattr(chat, "stream_query_with_tools", stream)
    return saved


def build_simple(history, summary):
    return [
        {"role": "system", "content": "S"},
        {"role": "user", "content": history[-1].content},
    ]


def test_retry_answers_the_saved_message_without_saving_it_again(monkeypatch):
    last = make_message(7, "user", "Explain borrowing")
    monkeypatch.setattr(chat, "_last_unanswered_message", lambda conversation_id: last)

    def stream(messages, tools):
        yield "delta", "Answer"
        yield "message", {"content": "Answer"}

    saved = fake_exchange_world(monkeypatch, last, stream)

    user_message = chat._user_message(uuid.uuid4(), None, [])
    events = list(
        chat._exchange(
            uuid.uuid4(), user_message, build_simple, [], lambda name, args: ("", False)
        )
    )

    assert saved == ["assistant"]
    reply = events[-1]["reply"]
    assert reply.user_message == last
    assert reply.assistant_message.content == "Answer"


def test_exchange_streams_text_and_ends_with_the_saved_reply(monkeypatch):
    last = make_message(7, "user", "Newest Rust?")

    def stream(messages, tools):
        yield "delta", "Rust "
        yield "delta", "1.90"
        yield (
            "message",
            {
                "content": "Rust 1.90",
                "annotations": [
                    {
                        "type": "url_citation",
                        "url_citation": {"url": "https://x.dev", "title": "X"},
                    }
                ],
            },
        )

    fake_exchange_world(monkeypatch, last, stream)

    events = list(
        chat._exchange(
            uuid.uuid4(), last, build_simple, [], lambda name, args: ("", False)
        )
    )

    assert [event["type"] for event in events] == [
        "user_message",
        "delta",
        "delta",
        "done",
    ]
    assert events[0]["message"] == last
    assert events[-1]["reply"].assistant_message.content == (
        "Rust 1.90\n\n**Sources**\n- [X](https://x.dev)"
    )
    assert events[-1]["reply"].course_changed is False


def test_exchange_error_mid_stream_saves_no_partial_answer(monkeypatch):
    last = make_message(7, "user", "Explain borrowing")

    def stream(messages, tools):
        yield "delta", "Borrowing is"
        raise OpenRouterError("OpenRouter stream broke off")

    saved = fake_exchange_world(monkeypatch, last, stream)

    with pytest.raises(OpenRouterError, match="broke off"):
        list(
            chat._exchange(
                uuid.uuid4(), last, build_simple, [], lambda name, args: ("", False)
            )
        )

    assert saved == []


def test_send_course_message_for_missing_course_returns_none_at_once(monkeypatch):
    monkeypatch.setattr(chat, "get_course", lambda course_id: None)

    assert chat.send_course_message(uuid.uuid4(), "Hi", []) is None


def test_learner_profile_section_in_both_chats():
    profile = "LEARNER PROFILE (from practice tasks):\n- Strong: Variables"

    topic = build_topic_chat_messages(
        make_topic_detail(), "", [], [], [], learner_profile=profile
    )
    course = build_course_chat_messages(make_course([]), "", [], [])

    assert profile in topic[0]["content"]
    assert "LEARNER PROFILE" not in course[0]["content"]
