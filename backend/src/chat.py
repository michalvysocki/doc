import uuid
from collections import defaultdict

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .courses import get_course, get_topic
from .database import SessionLocal
from .models import ChatMessage, Conversation, Document, Topic
from .openrouter import TOPIC_CHAT_SYSTEM_PROMPT, send_query
from .schemas import (
    AttachmentOut,
    ChatMessageOut,
    ImageIn,
    TopicChatReply,
    TopicDetail,
    TopicOut,
)
from .vectorstore import get_course_document_ids, retrieve_chunks

HISTORY_LIMIT = 20


def get_or_create_topic_conversation(topic_id: uuid.UUID) -> uuid.UUID | None:
    """
    Returns the id of the topic's conversation, creating it if needed.

    Returns:
        uuid.UUID | None: conversation id, or None if the topic does not exist
    """

    try:
        with SessionLocal() as session, session.begin():
            conversation_id = session.scalar(
                select(Conversation.id).where(Conversation.topic_id == topic_id)
            )
            if conversation_id is not None:
                return conversation_id

            course_id = session.scalar(
                select(Topic.course_id).where(Topic.id == topic_id)
            )
            if course_id is None:
                return None

            conversation_id = uuid.uuid4()
            session.add(
                Conversation(id=conversation_id, course_id=course_id, topic_id=topic_id)
            )
            return conversation_id
    except IntegrityError:
        with SessionLocal() as session:
            return session.scalar(
                select(Conversation.id).where(Conversation.topic_id == topic_id)
            )


def list_topic_messages(topic_id: uuid.UUID) -> list[ChatMessageOut]:
    """
    Returns all messages of the topic's conversation in order, with attachments.
    """

    with SessionLocal() as session:
        messages = session.scalars(
            select(ChatMessage)
            .join(Conversation, ChatMessage.conversation_id == Conversation.id)
            .where(Conversation.topic_id == topic_id)
            .order_by(ChatMessage.id)
        ).all()

        attachments = defaultdict(list)
        message_ids = [message.id for message in messages]
        if message_ids:
            documents = session.execute(
                select(Document.id, Document.filename, Document.message_id).where(
                    Document.message_id.in_(message_ids)
                )
            ).all()
            for document in documents:
                attachments[document.message_id].append(
                    AttachmentOut(file_uuid=document.id, filename=document.filename)
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
            select(Document.id, Document.filename).where(
                Document.message_id == message.id
            )
        ).all()

        return ChatMessageOut(
            id=message.id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
            attachments=[
                AttachmentOut(file_uuid=d.id, filename=d.filename) for d in documents
            ],
        )


def format_course_outline(
    topics: list[TopicOut], current_topic_id: uuid.UUID, depth: int = 0
) -> str:
    """
    Formats the topic tree as an indented list, marking the current topic.
    """

    lines = []
    for topic in topics:
        marker = "   <- current lesson" if topic.id == current_topic_id else ""
        lines.append(f"{'  ' * depth}- {topic.title}{marker}")
        if topic.children:
            lines.append(
                format_course_outline(topic.children, current_topic_id, depth + 1)
            )

    return "\n".join(lines)


def build_topic_chat_messages(
    topic: TopicDetail,
    outline: str,
    fragments: list[dict],
    history: list[ChatMessageOut],
) -> list[dict]:
    """
    Builds the messages for the model: a system prompt with the course and lesson
    context, followed by the most recent messages of the conversation.
    """

    path = " > ".join([*(link.title for link in topic.path), topic.title])
    lesson = topic.explanation or "(The lesson has not been generated yet.)"

    sections = [
        TOPIC_CHAT_SYSTEM_PROMPT,
        f"COURSE: {topic.course_title}",
        f"COURSE OUTLINE:\n{outline}",
        f"CURRENT LESSON: {path}\n{topic.description}\n\n{lesson}",
    ]
    if fragments:
        fragment_texts = [
            f"--- Fragment of the document: {f['metadata']['filename']} ---\n{f['text']}"
            for f in fragments
        ]
        sections.append("DOCUMENT FRAGMENTS:\n" + "\n\n".join(fragment_texts))

    messages = [{"role": "system", "content": "\n\n".join(sections)}]

    for message in history[-HISTORY_LIMIT:]:
        content = message.content
        if message.attachments:
            names = ", ".join(a.filename for a in message.attachments)
            content += f"\n\n[Attached files: {names}]"
        messages.append({"role": message.role, "content": content})

    return messages


def send_topic_message(
    topic_id: uuid.UUID,
    content: str,
    file_uuids: list[uuid.UUID],
    images: list[ImageIn],
) -> TopicChatReply | None:
    """
    Saves the user's message, asks the model with the lesson context
    and saves its reply.

    Returns:
        TopicChatReply | None: both messages, or None if the topic does not exist

    Raises:
        OpenRouterError: if the model or embeddings request fails; the user's
            message stays saved
    """

    topic = get_topic(topic_id)
    if topic is None:
        return None

    conversation_id = get_or_create_topic_conversation(topic_id)

    stored_content = content + "".join(f"\n\n[Image: {i.filename}]" for i in images)
    user_message = add_message(conversation_id, "user", stored_content, file_uuids)

    course = get_course(topic.course_id)
    outline = format_course_outline(course.topics, topic.id)
    fragments = retrieve_chunks(
        query=content, file_uuids=get_course_document_ids(topic.course_id)
    )
    history = list_topic_messages(topic_id)
    messages = build_topic_chat_messages(topic, outline, fragments, history)

    if images:
        messages[-1]["content"] = [
            {"type": "text", "text": messages[-1]["content"]},
            *(
                {"type": "file", "file": {"filename": i.filename, "file_data": i.data}}
                for i in images
            ),
        ]

    reply = send_query(messages)
    assistant_message = add_message(conversation_id, "assistant", reply)

    return TopicChatReply(
        user_message=user_message, assistant_message=assistant_message
    )
