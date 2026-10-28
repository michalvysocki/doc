import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Topic, TopicLink

logger = logging.getLogger(__name__)

# A topic placed in the course: (title, topic id, titles it requires, ids of its modules)
Placed = tuple[str, uuid.UUID, list[str], tuple[uuid.UUID, ...]]


def resolve_links(placed: list[Placed]) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """
    Turns prerequisite titles into (topic, required topic) id pairs. Topics come
    in outline order; a link is kept only to an earlier topic that is not the
    topic itself or one of its modules, so links can never form a cycle.
    A link to the previous topic of the same module is dropped, because the
    outline order already says it. Skipped links are logged.
    """

    position: dict[str, int] = {}
    ids: dict[str, uuid.UUID] = {}
    previous: dict[uuid.UUID, uuid.UUID] = {}
    last_in_module: dict[tuple[uuid.UUID, ...], uuid.UUID] = {}
    for index, (title, topic_id, _, ancestors) in enumerate(placed):
        key = title.casefold()
        position.setdefault(key, index)
        ids.setdefault(key, topic_id)
        if ancestors in last_in_module:
            previous[topic_id] = last_in_module[ancestors]
        last_in_module[ancestors] = topic_id

    pairs: list[tuple[uuid.UUID, uuid.UUID]] = []
    for index, (title, topic_id, requires, ancestors) in enumerate(placed):
        for required in requires:
            key = required.casefold()
            earlier = position.get(key, index) < index
            if not earlier or ids[key] == topic_id or ids[key] in ancestors:
                logger.warning('Skipped link: "%s" requires "%s"', title, required)
                continue
            if previous.get(topic_id) == ids[key]:
                logger.info('Dropped link to the previous topic: "%s"', title)
                continue
            pair = (topic_id, ids[key])
            if pair not in pairs:
                pairs.append(pair)
    return pairs


def replace_course_links(
    session: Session,
    course_id: uuid.UUID,
    pairs: list[tuple[uuid.UUID, uuid.UUID]],
) -> None:
    """Replaces all prerequisite links of a course's topics with the given pairs."""

    course_topics = select(Topic.id).where(Topic.course_id == course_id)
    session.execute(delete(TopicLink).where(TopicLink.from_topic_id.in_(course_topics)))
    session.add_all(
        TopicLink(from_topic_id=from_id, to_topic_id=to_id) for from_id, to_id in pairs
    )


def links_by_topic(
    session: Session, course_id: uuid.UUID
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """Returns, for each topic of a course, the ids of the topics it requires."""

    links: dict[uuid.UUID, list[uuid.UUID]] = {}
    for from_id, to_id in session.execute(
        select(TopicLink.from_topic_id, TopicLink.to_topic_id)
        .join(Topic, Topic.id == TopicLink.from_topic_id)
        .where(Topic.course_id == course_id)
        .order_by(TopicLink.id)
    ):
        links.setdefault(from_id, []).append(to_id)
    return links
