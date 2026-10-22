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
    topics: list[TopicOut], depth: int = 0, include_ids: bool = False
) -> str:
    """
    Formats the topic tree as an indented list with lesson and task progress,
    optionally with topic ids (needed by tools that change the course).
    """

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
        lines.append(f"{'  ' * depth}- {topic.title}{suffix}{topic_id}")
        if topic.children:
            lines.append(
                format_outline_with_progress(topic.children, depth + 1, include_ids)
            )

    return "\n".join(lines)
