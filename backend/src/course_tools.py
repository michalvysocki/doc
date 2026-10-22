import uuid

from pydantic import ValidationError

from .courses import FIRST, TopicPlacementError, add_topics, move_topic, rename_topic
from .schemas import (
    AddSubtopicsArgs,
    AddTasksArgs,
    AddTopicsArgs,
    MoveTopicArgs,
    ProposeTopicDeletionArgs,
    RenameTopicArgs,
)
from .tasks import LessonMissingError, add_tasks
from .topic_deletions import propose_topic_deletion

ADD_TOPICS_TOOL = {
    "type": "function",
    "function": {
        "name": "add_topics",
        "description": (
            "Add new topics, optionally with subtopics, to the course map. Use topic "
            "ids from the course outline."
        ),
        "parameters": AddTopicsArgs.model_json_schema(),
    },
}

RENAME_TOPIC_TOOL = {
    "type": "function",
    "function": {
        "name": "rename_topic",
        "description": (
            "Rename a topic of the course and optionally change its description."
        ),
        "parameters": RenameTopicArgs.model_json_schema(),
    },
}

MOVE_TOPIC_TOOL = {
    "type": "function",
    "function": {
        "name": "move_topic",
        "description": (
            "Move a topic with its subtopics under another parent or change its "
            "place among its siblings. Use topic ids from the course outline."
        ),
        "parameters": MoveTopicArgs.model_json_schema(),
    },
}

PROPOSE_TOPIC_DELETION_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_topic_deletion",
        "description": (
            "Propose deleting a topic with its subtopics. Deletes nothing: the "
            "learner confirms or cancels with a button."
        ),
        "parameters": ProposeTopicDeletionArgs.model_json_schema(),
    },
}

COURSE_TOOLS = [
    ADD_TOPICS_TOOL,
    RENAME_TOPIC_TOOL,
    MOVE_TOPIC_TOOL,
    PROPOSE_TOPIC_DELETION_TOOL,
]

ADD_SUBTOPICS_TOOL = {
    "type": "function",
    "function": {
        "name": "add_subtopics",
        "description": (
            "Add subtopics to the current lesson. Use subtopic ids from the "
            "current lesson section."
        ),
        "parameters": AddSubtopicsArgs.model_json_schema(),
    },
}

ADD_TASKS_TOOL = {
    "type": "function",
    "function": {
        "name": "add_tasks",
        "description": "Add practice tasks to the current lesson.",
        "parameters": AddTasksArgs.model_json_schema(),
    },
}

TOPIC_TOOLS = [ADD_SUBTOPICS_TOOL, ADD_TASKS_TOOL]


def _parse_id(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None


def run_course_tool(
    course_id: uuid.UUID, name: str, arguments: str
) -> tuple[str, bool]:
    """
    Runs a tool requested by the model in the course chat.

    Returns:
        tuple[str, bool]: the result for the model, and whether the course changed.
            Errors are returned as text so the model can correct itself.
    """

    try:
        if name == "add_topics":
            args = AddTopicsArgs.model_validate_json(arguments)
            titles = add_topics(
                course_id,
                _parse_id(args.parent_topic_id),
                _parse_id(args.after_topic_id),
                args.topics,
            )
            return f"Added {len(titles)} topics: {', '.join(titles)}", True
        if name == "rename_topic":
            args = RenameTopicArgs.model_validate_json(arguments)
            old_title = rename_topic(
                course_id, uuid.UUID(args.topic_id), args.title, args.description
            )
            if old_title is None:
                return "Error: topic not found in this course", False
            return f"Renamed '{old_title}' to '{args.title}'", True
        if name == "move_topic":
            args = MoveTopicArgs.model_validate_json(arguments)
            after = (
                FIRST
                if args.after_topic_id == FIRST
                else _parse_id(args.after_topic_id)
            )
            title = move_topic(
                course_id,
                uuid.UUID(args.topic_id),
                _parse_id(args.parent_topic_id),
                after,
            )
            return f"Moved '{title}'", True
        if name == "propose_topic_deletion":
            args = ProposeTopicDeletionArgs.model_validate_json(arguments)
            deletion = propose_topic_deletion(course_id, uuid.UUID(args.topic_id))
            if deletion is None:
                return "Error: topic not found in this course", False
            summary = (
                f"Deletion of '{deletion.topic_title}' proposed; nothing is deleted "
                "yet. The learner must confirm it with the button shown in the "
                f"chat. It would delete {deletion.subtopics} subtopics, "
                f"{deletion.lessons} lessons, {deletion.tasks} tasks and "
                f"{deletion.attempts} attempts."
            )
            return summary, True
    except ValidationError as e:
        return f"Error: invalid arguments: {e}", False
    except (ValueError, TopicPlacementError) as e:
        return f"Error: {e}", False

    return f"Error: unknown tool {name}", False


def run_topic_tool(
    course_id: uuid.UUID, topic_id: uuid.UUID, name: str, arguments: str
) -> tuple[str, bool]:
    """
    Runs a tool requested by the model in the topic chat. New topics are always
    added under the current topic and new tasks to the current topic.

    Returns:
        tuple[str, bool]: the result for the model, and whether the course changed.
            Errors are returned as text so the model can correct itself.
    """

    try:
        if name == "add_subtopics":
            args = AddSubtopicsArgs.model_validate_json(arguments)
            titles = add_topics(
                course_id, topic_id, _parse_id(args.after_topic_id), args.topics
            )
            return f"Added {len(titles)} topics: {', '.join(titles)}", True
        if name == "add_tasks":
            args = AddTasksArgs.model_validate_json(arguments)
            numbers = add_tasks(topic_id, args.tasks)
            return f"Added tasks: {', '.join(map(str, numbers))}", True
    except ValidationError as e:
        return f"Error: invalid arguments: {e}", False
    except (ValueError, TopicPlacementError) as e:
        return f"Error: {e}", False
    except LessonMissingError:
        return "Error: the lesson has not been generated yet", False

    return f"Error: unknown tool {name}", False
