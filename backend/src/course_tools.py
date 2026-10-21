import uuid

from pydantic import ValidationError

from .courses import TopicPlacementError, add_topics
from .schemas import AddTopicsArgs

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

COURSE_TOOLS = [ADD_TOPICS_TOOL]


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

    if name != "add_topics":
        return f"Error: unknown tool {name}", False

    try:
        args = AddTopicsArgs.model_validate_json(arguments)
        titles = add_topics(
            course_id,
            _parse_id(args.parent_topic_id),
            _parse_id(args.after_topic_id),
            args.topics,
        )
    except ValidationError as e:
        return f"Error: invalid arguments: {e}", False
    except (ValueError, TopicPlacementError) as e:
        return f"Error: {e}", False

    return f"Added {len(titles)} topics: {', '.join(titles)}", True
