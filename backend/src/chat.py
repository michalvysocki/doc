import logging
import os
import uuid
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError

from .course_tools import COURSE_TOOLS, TOPIC_TOOLS, run_course_tool, run_topic_tool
from .courses import get_course, get_topic
from .database import SessionLocal
from .learner_profile import format_learner_profile
from .models import ChatMessage, Conversation, Document
from .openrouter import (
    COURSE_CHAT_SYSTEM_PROMPT,
    TOPIC_CHAT_SYSTEM_PROMPT,
    OpenRouterError,
    append_sources,
    image_part,
    rewrite_search_query,
    send_query,
    send_query_with_tools,
    summarize_conversation,
)
from .outline import format_course_outline, format_outline_with_progress
from .schemas import (
    AttachmentOut,
    ChatMessageOut,
    ChatReply,
    CourseOut,
    TaskOut,
    TopicDetail,
)
from .tasks import get_tasks
from .vectorstore import (
    format_course_files,
    format_fragments,
    get_course_document_ids,
    get_image,
    retrieve_chunks,
)

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 20
SUMMARY_BATCH = 10
MAX_HISTORY_MESSAGES = HISTORY_LIMIT + SUMMARY_BATCH
SEARCH_CONTEXT_MESSAGES = 6
CONTEXT_BUDGET_TOKENS = int(os.getenv("CONTEXT_BUDGET_TOKENS", "60000"))
CHARS_PER_TOKEN = 3
IMAGE_TOKENS = 1500
MAX_LESSON_CHARS_IN_CONTEXT = 40_000
MAX_OUTLINE_CHARS_IN_CONTEXT = 20_000
MAX_TOOL_ROUNDS = 3
MAX_CHARS_IN_TASK_CONTEXT = 1500


def _conversation_condition(course_id: uuid.UUID | None, topic_id: uuid.UUID | None):
    """
    WHERE condition for a topic conversation (topic_id given) or for the course
    conversation (topic_id is None).
    """

    if topic_id is not None:
        return Conversation.topic_id == topic_id
    return and_(Conversation.course_id == course_id, Conversation.topic_id.is_(None))


def get_or_create_conversation(
    course_id: uuid.UUID, topic_id: uuid.UUID | None = None
) -> uuid.UUID:
    """
    Returns the id of the topic conversation (if topic_id is given) or of the
    course conversation, creating it if needed.
    """

    query = select(Conversation.id).where(_conversation_condition(course_id, topic_id))

    try:
        with SessionLocal() as session, session.begin():
            conversation_id = session.scalar(query)
            if conversation_id is not None:
                return conversation_id

            conversation_id = uuid.uuid4()
            session.add(
                Conversation(id=conversation_id, course_id=course_id, topic_id=topic_id)
            )
            return conversation_id
    except IntegrityError:
        with SessionLocal() as session:
            return session.scalar(query)


def _list_messages(condition) -> list[ChatMessageOut]:
    """
    Returns messages matching the condition (on conversations or messages)
    in order, with attachments.
    """

    with SessionLocal() as session:
        messages = session.scalars(
            select(ChatMessage)
            .join(Conversation, ChatMessage.conversation_id == Conversation.id)
            .where(condition)
            .order_by(ChatMessage.id)
        ).all()

        attachments = defaultdict(list)
        message_ids = [message.id for message in messages]
        if message_ids:
            documents = session.execute(
                select(
                    Document.id,
                    Document.filename,
                    Document.media_type,
                    Document.message_id,
                ).where(Document.message_id.in_(message_ids))
            ).all()
            for document in documents:
                attachments[document.message_id].append(
                    AttachmentOut(
                        file_uuid=document.id,
                        filename=document.filename,
                        media_type=document.media_type,
                    )
                )

        return [
            ChatMessageOut(
                id=message.id,
                role=message.role,
                content=message.content,
                created_at=message.created_at,
                attachments=attachments[message.id],
            )
            for message in messages
        ]


def list_topic_messages(topic_id: uuid.UUID) -> list[ChatMessageOut]:
    """
    Returns all messages of the topic's conversation in order, with attachments.
    """

    return _list_messages(_conversation_condition(None, topic_id))


def list_course_messages(course_id: uuid.UUID) -> list[ChatMessageOut]:
    """
    Returns all messages of the course conversation in order, with attachments.
    """

    return _list_messages(_conversation_condition(course_id, None))


def add_message(
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    file_uuids: list[uuid.UUID] | None = None,
) -> ChatMessageOut:
    """
    Saves a message and attaches the given documents of the same course to it.
    """

    with SessionLocal() as session, session.begin():
        message = ChatMessage(
            conversation_id=conversation_id, role=role, content=content
        )
        session.add(message)
        session.flush()

        if file_uuids:
            course_id = select(Conversation.course_id).where(
                Conversation.id == conversation_id
            )
            session.execute(
                update(Document)
                .where(
                    Document.id.in_(file_uuids),
                    Document.course_id == course_id.scalar_subquery(),
                    Document.message_id.is_(None),
                )
                .values(message_id=message.id)
            )

        documents = session.execute(
            select(Document.id, Document.filename, Document.media_type).where(
                Document.message_id == message.id
            )
        ).all()

        return ChatMessageOut(
            id=message.id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
            attachments=[
                AttachmentOut(
                    file_uuid=d.id, filename=d.filename, media_type=d.media_type
                )
                for d in documents
            ],
        )


def _shorten(text: str, limit: int = MAX_CHARS_IN_TASK_CONTEXT) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def format_tasks_for_chat(tasks: list[TaskOut]) -> str:
    """
    Formats the topic's tasks with the learner's latest attempt for the chat prompt.
    """

    lines = []
    for index, task in enumerate(tasks, start=1):
        lines.append(f"Task {index}: {_shorten(task.question)}")

        latest = task.attempts[-1] if task.attempts else None
        if latest is None:
            lines.append("  Not attempted yet.")
            continue

        verdict = latest.verdict or "not graded"
        lines.append(
            f"  Learner's latest answer ({verdict}): {_shorten(latest.answer)}"
        )
        if latest.feedback:
            lines.append(f"  Feedback: {_shorten(latest.feedback)}")

    return "\n".join(lines)


def _cap(text: str, limit: int) -> str:
    """Cuts a prompt section to the limit, marking that it was cut."""

    return text if len(text) <= limit else text[:limit] + "\n[...truncated]"


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """
    Roughly estimates the prompt size: text length / CHARS_PER_TOKEN, plus a
    fixed cost per image.
    """

    total = 0
    for message in messages:
        content = message["content"]
        parts = (
            content
            if isinstance(content, list)
            else [{"type": "text", "text": content}]
        )
        for part in parts:
            if part["type"] == "text":
                total += len(part["text"]) // CHARS_PER_TOKEN
            else:
                total += IMAGE_TOKENS
    return total


def fit_to_budget(
    messages: list[dict[str, Any]], budget: int | None = None
) -> list[dict[str, Any]]:
    """
    Drops the oldest history messages until the prompt fits the budget, always
    keeping the system prompt and the learner's last message.
    """

    budget = CONTEXT_BUDGET_TOKENS if budget is None else budget
    system, history = messages[0], messages[1:]
    while len(history) > 1 and estimate_tokens([system, *history]) > budget:
        history = history[1:]
    dropped = len(messages) - 1 - len(history)
    if dropped:
        logger.info("Dropped %d old messages to fit the context budget", dropped)
    return [system, *history]


def _search_query(history: list[ChatMessageOut], topic: str | None = None) -> str:
    """
    Returns the query for RAG: the learner's last message rewritten with the
    recent conversation, or the message itself if there is nothing before it
    or rewriting fails.
    """

    question = history[-1].content
    recent = history[:-1][-SEARCH_CONTEXT_MESSAGES:]
    if not recent:
        return question
    try:
        return rewrite_search_query(
            _history_messages(recent, limit=None), question, topic
        )
    except OpenRouterError:
        logger.warning("Could not rewrite the search query", exc_info=True)
        return question


def split_for_summary(
    messages: list[ChatMessageOut],
    limit: int = HISTORY_LIMIT,
    batch: int = SUMMARY_BATCH,
) -> tuple[list[ChatMessageOut], list[ChatMessageOut]]:
    """
    Returns (to_summarize, to_keep): when there are more than limit + batch
    messages, all but the last `limit` go into the summary.
    """

    if len(messages) <= limit + batch:
        return [], messages
    return messages[:-limit], messages[-limit:]


def _conversation_window(
    conversation_id: uuid.UUID,
) -> tuple[str | None, list[ChatMessageOut]]:
    """
    Returns the conversation summary and the messages after it, first folding
    older messages into the summary when there are too many. If summarizing
    fails, the window simply stays longer until the next message.
    """

    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        summary = conversation.summary
        summary_until_id = conversation.summary_until_id

    condition = ChatMessage.conversation_id == conversation_id
    if summary_until_id is not None:
        condition = and_(condition, ChatMessage.id > summary_until_id)
    messages = _list_messages(condition)

    to_summarize, to_keep = split_for_summary(messages)
    if not to_summarize:
        return summary, messages

    try:
        summary = summarize_conversation(
            summary, _history_messages(to_summarize, limit=None)
        )
    except OpenRouterError:
        logger.warning(
            "Could not summarize conversation %s", conversation_id, exc_info=True
        )
        return summary, messages

    with SessionLocal() as session, session.begin():
        session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(summary=summary, summary_until_id=to_summarize[-1].id)
        )
    return summary, to_keep


def _history_messages(
    history: list[ChatMessageOut], limit: int | None = MAX_HISTORY_MESSAGES
) -> list[dict]:
    messages = []
    for message in history if limit is None else history[-limit:]:
        content = message.content
        if message.attachments:
            names = ", ".join(a.filename for a in message.attachments)
            content += f"\n\n[Attached files: {names}]"
        messages.append({"role": message.role, "content": content})
    return messages


def build_topic_chat_messages(
    topic: TopicDetail,
    outline: str,
    fragments: list[dict],
    history: list[ChatMessageOut],
    tasks: list[TaskOut],
    goal: str | None = None,
    summary: str | None = None,
    course_files: str | None = None,
    learner_profile: str | None = None,
) -> list[dict]:
    """
    Builds the messages for the model: a system prompt with the course and lesson
    context, followed by the most recent messages of the conversation.
    """

    path = " > ".join([*(link.title for link in topic.path), topic.title])
    lesson = topic.explanation or "(The lesson has not been generated yet.)"
    level = len(topic.path) + 1
    subtopics = "\n".join(f"- {link.title} (id: {link.id})" for link in topic.subtopics)

    sections = [
        TOPIC_CHAT_SYSTEM_PROMPT,
        f"COURSE: {topic.course_title}",
        *([f"LEARNER'S GOAL: {goal}"] if goal else []),
        f"COURSE OUTLINE:\n{_cap(outline, MAX_OUTLINE_CHARS_IN_CONTEXT)}",
        f"CURRENT LESSON: {path}\n{topic.description}\n\n"
        + _cap(lesson, MAX_LESSON_CHARS_IN_CONTEXT),
        f"SUBTOPICS OF THIS LESSON (lesson level {level} of max 3):\n"
        + (subtopics or "(none)"),
    ]
    if learner_profile:
        sections.append(learner_profile)
    if course_files:
        sections.append(course_files)
    if summary:
        sections.append(f"EARLIER CONVERSATION (summary):\n{summary}")
    if fragments:
        sections.append(format_fragments(fragments))
    if tasks:
        sections.append(f"PRACTICE TASKS:\n{format_tasks_for_chat(tasks)}")

    return [
        {"role": "system", "content": "\n\n".join(sections)},
        *_history_messages(history),
    ]


def build_course_chat_messages(
    course: CourseOut,
    outline: str,
    fragments: list[dict],
    history: list[ChatMessageOut],
    summary: str | None = None,
    course_files: str | None = None,
    learner_profile: str | None = None,
) -> list[dict]:
    """
    Builds the messages for the model: a system prompt with the course goal,
    progress and outline, followed by the most recent messages of the conversation.
    """

    progress = course.progress
    completed = f"{progress.topics_completed} / {progress.topics_total}"
    sections = [
        COURSE_CHAT_SYSTEM_PROMPT,
        f"COURSE: {course.title}",
        f"LEARNER'S GOAL: {course.initial_prompt}",
        f"PROGRESS: {completed} topics completed",
        f"COURSE OUTLINE:\n{_cap(outline, MAX_OUTLINE_CHARS_IN_CONTEXT)}",
    ]
    if learner_profile:
        sections.append(learner_profile)
    if course_files:
        sections.append(course_files)
    if summary:
        sections.append(f"EARLIER CONVERSATION (summary):\n{summary}")
    if fragments:
        sections.append(format_fragments(fragments))

    return [
        {"role": "system", "content": "\n\n".join(sections)},
        *_history_messages(history),
    ]


ToolRunner = Callable[[str, str], tuple[str, bool]]


def _ask_with_tools(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]], run_tool: ToolRunner
) -> tuple[str, bool]:
    """
    Lets the model call tools until it answers with text.

    Returns:
        tuple[str, bool]: the final answer, and whether any tool changed the course

    Raises:
        OpenRouterError: if the model fails or keeps calling tools
    """

    changed = False
    for _ in range(MAX_TOOL_ROUNDS):
        message = send_query_with_tools(messages, tools)
        tool_calls = message.get("tool_calls")
        if not tool_calls:
            if not message.get("content"):
                raise OpenRouterError("Model returned an empty answer")
            return append_sources(
                message["content"], message.get("annotations")
            ), changed

        messages.append(message)
        for call in tool_calls:
            result, call_changed = run_tool(
                call["function"]["name"], call["function"]["arguments"]
            )
            changed = changed or call_changed
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": result}
            )

    raise OpenRouterError("Model called tools too many times")


class NothingToRetryError(Exception):
    """Raised when the conversation has no unanswered message of the learner."""


def _last_unanswered_message(conversation_id: uuid.UUID) -> ChatMessageOut | None:
    """Returns the last message if it is the learner's and has no reply yet."""

    with SessionLocal() as session:
        last = session.execute(
            select(ChatMessage.id, ChatMessage.role)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.id.desc())
            .limit(1)
        ).first()
    if last is None or last.role != "user":
        return None
    return _list_messages(ChatMessage.id == last.id)[0]


def _exchange(
    conversation_id: uuid.UUID,
    content: str | None,
    file_uuids: list[uuid.UUID],
    build_messages: Callable[[list[ChatMessageOut], str | None], list[dict[str, Any]]],
    tools: list[dict[str, Any]] | None = None,
    run_tool: ToolRunner | None = None,
) -> ChatReply:
    """
    Saves the learner's message (or, with content None, takes the last
    unanswered one again), builds the model messages from the conversation
    history, asks the model and saves its reply.

    Raises:
        NothingToRetryError: if content is None and there is nothing to answer
        OpenRouterError: if the model or embeddings request fails; the user's
            message stays saved
    """

    if content is None:
        user_message = _last_unanswered_message(conversation_id)
        if user_message is None:
            raise NothingToRetryError()
    else:
        user_message = add_message(conversation_id, "user", content, file_uuids)

    summary, history = _conversation_window(conversation_id)
    messages = build_messages(history, summary)

    image_parts = [
        image_part(*image)
        for attachment in user_message.attachments
        if attachment.media_type and (image := get_image(attachment.file_uuid))
    ]
    if image_parts:
        messages[-1]["content"] = [
            {"type": "text", "text": messages[-1]["content"]},
            *image_parts,
        ]
    messages = fit_to_budget(messages)

    if tools:
        reply, changed = _ask_with_tools(messages, tools, run_tool)
    else:
        reply, changed = send_query(messages), False
    assistant_message = add_message(conversation_id, "assistant", reply)

    return ChatReply(
        user_message=user_message,
        assistant_message=assistant_message,
        course_changed=changed,
    )


def add_course_note(
    course_id: uuid.UUID, text: str, role: str = "user"
) -> ChatMessageOut:
    """
    Adds a note to the course conversation, so the model knows about it in the
    next message: the learner's action (e.g. a confirmed deletion) or, with the
    assistant role, information such as the sources used to plan the course.
    """

    return add_message(get_or_create_conversation(course_id), role, text)


def add_topic_note(topic_id: uuid.UUID, text: str) -> ChatMessageOut | None:
    """
    Adds a note about the learner's action (e.g. a confirmed regeneration) to
    the topic conversation, so the model knows about it in the next message.

    Returns:
        ChatMessageOut | None: the note, or None if the topic does not exist
    """

    topic = get_topic(topic_id)
    if topic is None:
        return None
    return add_message(
        get_or_create_conversation(topic.course_id, topic_id), "user", text
    )


def send_topic_message(
    topic_id: uuid.UUID,
    content: str | None,
    file_uuids: list[uuid.UUID],
) -> ChatReply | None:
    """
    Sends a message in the topic's conversation, with the lesson as context.
    With content None, answers the last unanswered message again.

    Returns:
        ChatReply | None: both messages, or None if the topic does not exist

    Raises:
        OpenRouterError: if the model or embeddings request fails; the user's
            message stays saved
    """

    topic = get_topic(topic_id)
    if topic is None:
        return None

    course = get_course(topic.course_id)
    outline = format_course_outline(course.topics, topic.id)
    tasks = get_tasks(topic_id)

    def build(
        history: list[ChatMessageOut], summary: str | None
    ) -> list[dict[str, Any]]:
        fragments = retrieve_chunks(
            query=_search_query(history, topic=topic.title),
            file_uuids=get_course_document_ids(
                topic.course_id, exclude_topic_id=topic_id
            ),
        )
        return build_topic_chat_messages(
            topic,
            outline,
            fragments,
            history,
            tasks,
            goal=course.initial_prompt,
            summary=summary,
            course_files=format_course_files(topic.course_id),
            learner_profile=format_learner_profile(topic.course_id),
        )

    return _exchange(
        get_or_create_conversation(topic.course_id, topic_id),
        content,
        file_uuids,
        build,
        tools=TOPIC_TOOLS,
        run_tool=lambda name, arguments: run_topic_tool(
            topic.course_id, topic_id, name, arguments
        ),
    )


def send_course_message(
    course_id: uuid.UUID,
    content: str | None,
    file_uuids: list[uuid.UUID],
) -> ChatReply | None:
    """
    Sends a message in the course conversation, with the outline and progress
    as context. With content None, answers the last unanswered message again.

    Returns:
        ChatReply | None: both messages, or None if the course does not exist

    Raises:
        OpenRouterError: if the model or embeddings request fails; the user's
            message stays saved
    """

    course = get_course(course_id)
    if course is None:
        return None

    outline = format_outline_with_progress(
        course.topics, include_ids=True, include_descriptions=True
    )

    def build(
        history: list[ChatMessageOut], summary: str | None
    ) -> list[dict[str, Any]]:
        fragments = retrieve_chunks(
            query=_search_query(history), file_uuids=get_course_document_ids(course_id)
        )
        return build_course_chat_messages(
            course,
            outline,
            fragments,
            history,
            summary=summary,
            course_files=format_course_files(course_id),
            learner_profile=format_learner_profile(course_id),
        )

    return _exchange(
        get_or_create_conversation(course_id),
        content,
        file_uuids,
        build,
        tools=COURSE_TOOLS,
        run_tool=lambda name, arguments: run_course_tool(course_id, name, arguments),
    )


def retry_topic_message(topic_id: uuid.UUID) -> ChatReply | None:
    """Asks the model again to answer the last unanswered message of a topic chat."""

    return send_topic_message(topic_id, None, [])


def retry_course_message(course_id: uuid.UUID) -> ChatReply | None:
    """Asks the model again to answer the last unanswered message of a course chat."""

    return send_course_message(course_id, None, [])
