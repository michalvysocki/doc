import uuid

from .schemas import TopicOut


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


def format_outline_with_progress(
    topics: list[TopicOut],
    depth: int = 0,
    include_ids: bool = False,
    include_descriptions: bool = False,
    include_requires: bool = False,
    titles: dict[uuid.UUID, str] | None = None,
) -> str:
    """
    Formats the topic tree as an indented list with lesson and task progress,
    optionally with topic ids (needed by tools that change the course) and
    descriptions (to tell similar topics apart).
    """

    if include_requires and titles is None:
        titles = _titles(topics)

    lines = []
    for topic in topics:
        status = []
        if topic.has_explanation:
            status.append("lesson ready")
        if topic.tasks_total > 0 and topic.tasks_solved == topic.tasks_total:
            status.append("completed")
        elif topic.tasks_total > 0:
            status.append(f"tasks {topic.tasks_solved}/{topic.tasks_total}")

        suffix = f" [{', '.join(status)}]" if status else ""
        topic_id = f" (id: {topic.id})" if include_ids else ""
        description = f": {topic.description}" if include_descriptions else ""
        required = [titles[i] for i in topic.requires if i in titles] if titles else []
        requires = f" (requires: {', '.join(required)})" if required else ""
        lines.append(
            f"{'  ' * depth}- {topic.title}{suffix}{topic_id}{requires}{description}"
        )
        if topic.children:
            lines.append(
                format_outline_with_progress(
                    topic.children,
                    depth + 1,
                    include_ids,
                    include_descriptions,
                    include_requires,
                    titles,
                )
            )

    return "\n".join(lines)


def _titles(topics: list[TopicOut]) -> dict[uuid.UUID, str]:
    titles = {}
    for topic in topics:
        titles[topic.id] = topic.title
        titles.update(_titles(topic.children))
    return titles


def required_titles(topics: list[TopicOut], topic_id: uuid.UUID) -> list[str]:
    """Returns the titles of the topics that the given topic requires."""

    topic = _find(topics, topic_id)
    if topic is None:
        return []
    titles = _titles(topics)
    return [titles[i] for i in topic.requires if i in titles]


def _find(topics: list[TopicOut], topic_id: uuid.UUID) -> TopicOut | None:
    for topic in topics:
        if topic.id == topic_id:
            return topic
        if (found := _find(topic.children, topic_id)) is not None:
            return found
    return None
