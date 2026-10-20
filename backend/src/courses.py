import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select, update

from .database import SessionLocal
from .models import Course, Topic
from .openrouter import generate_topic_explanation
from .schemas import (
    CourseOut,
    CourseSummary,
    TopicDetail,
    TopicLink,
    TopicMap,
    TopicNode,
    TopicOut,
)


def _flatten_topics(
    nodes: list[TopicNode], course_id: uuid.UUID, parent_id: uuid.UUID | None = None
) -> list[Topic]:
    """
    Converts a nested topic tree into a flat list of Topic rows,
    parents always before their children.
    """

    topics = []

    for position, node in enumerate(nodes):
        topic = Topic(
            id=uuid.uuid4(),
            course_id=course_id,
            parent_id=parent_id,
            title=node.title,
            description=node.description,
            position=position,
        )
        topics.append(topic)
        topics.extend(_flatten_topics(node.children, course_id, topic.id))

    return topics


def _build_tree(rows: Sequence[Any]) -> list[TopicOut]:
    """
    Builds a nested topic tree from flat topic rows.

    Rows need id, parent_id, title, description and has_explanation
    attributes and must be ordered by position.
    """

    nodes = {
        row.id: TopicOut(
            id=row.id,
            title=row.title,
            description=row.description,
            has_explanation=row.has_explanation,
            children=[],
        )
        for row in rows
    }

    roots = []
    for row in rows:
        node = nodes[row.id]
        if row.parent_id is None:
            roots.append(node)
        else:
            nodes[row.parent_id].children.append(node)

    return roots


def save_course(initial_prompt: str, topic_map: TopicMap) -> uuid.UUID:
    """
    Saves a course and its whole topic tree in one transaction.

    Returns:
        uuid.UUID: id of the created course
    """

    course_id = uuid.uuid4()
    course = Course(
        id=course_id, title=topic_map.course_title, initial_prompt=initial_prompt
    )
    topics = _flatten_topics(topic_map.topics, course_id)

    with SessionLocal() as session, session.begin():
        session.add(course)
        session.flush()
        session.add_all(topics)

    return course_id


def get_course(course_id: uuid.UUID) -> CourseOut | None:
    """
    Loads a course with all its topics and builds the topic tree.

    Returns:
        CourseOut | None: the course, or None if it does not exist
    """

    with SessionLocal() as session:
        course = session.get(Course, course_id)
        if course is None:
            return None

        topics = session.execute(
            select(
                Topic.id,
                Topic.parent_id,
                Topic.title,
                Topic.description,
                Topic.explanation.is_not(None).label("has_explanation"),
            )
            .where(Topic.course_id == course_id)
            .order_by(Topic.position)
        ).all()

        return CourseOut(
            id=course.id,
            title=course.title,
            initial_prompt=course.initial_prompt,
            created_at=course.created_at,
            topics=_build_tree(topics),
        )


def list_courses() -> list[CourseSummary]:
    """
    Returns all courses without topics, newest first.
    """

    statement = select(Course.id, Course.title, Course.created_at).order_by(
        Course.created_at.desc()
    )

    with SessionLocal() as session:
        rows = session.execute(statement).all()

    return [
        CourseSummary(id=row.id, title=row.title, created_at=row.created_at)
        for row in rows
    ]


def delete_course(course_id: uuid.UUID) -> bool:
    """
    Deletes a course. Its topics and documents are deleted
    by the database (ON DELETE CASCADE).

    Returns:
        bool: True if deleted, False if the course does not exist
    """

    with SessionLocal() as session, session.begin():
        result = session.execute(delete(Course).where(Course.id == course_id))

    return result.rowcount > 0


def get_topic(topic_id: uuid.UUID) -> TopicDetail | None:
    """
    Loads a topic with its course title, path of parent topics and subtopics.

    Returns:
        TopicDetail | None: the topic, or None if it does not exist
    """

    with SessionLocal() as session:
        topic = session.get(Topic, topic_id)
        if topic is None:
            return None

        course = session.get(Course, topic.course_id)
        course_topics = session.scalars(
            select(Topic)
            .where(Topic.course_id == topic.course_id)
            .order_by(Topic.position)
        ).all()

        topics_by_id = {t.id: t for t in course_topics}

        path = []
        parent_id = topic.parent_id
        while parent_id is not None:
            parent = topics_by_id[parent_id]
            path.insert(0, TopicLink(id=parent.id, title=parent.title))
            parent_id = parent.parent_id

        subtopics = [
            TopicLink(id=t.id, title=t.title)
            for t in course_topics
            if t.parent_id == topic.id
        ]

        return TopicDetail(
            id=topic.id,
            course_id=course.id,
            course_title=course.title,
            path=path,
            title=topic.title,
            description=topic.description,
            explanation=topic.explanation,
            subtopics=subtopics,
        )


def create_explanation(topic_id: uuid.UUID) -> TopicDetail | None:
    """
    Generates and saves an explanation for a topic, unless it already has one.

    Returns:
        TopicDetail | None: the topic with explanation, or None if it does not exist
    """

    topic = get_topic(topic_id)
    if topic is None:
        return None
    if topic.explanation is not None:
        return topic

    explanation = generate_topic_explanation(
        course_title=topic.course_title,
        path=[link.title for link in topic.path],
        title=topic.title,
        description=topic.description,
        subtopics=[link.title for link in topic.subtopics],
    )

    with SessionLocal() as session, session.begin():
        session.execute(
            update(Topic).where(Topic.id == topic_id).values(explanation=explanation)
        )

    return topic.model_copy(update={"explanation": explanation})


def course_exists(course_id: uuid.UUID) -> bool:
    with SessionLocal() as session:
        return session.get(Course, course_id) is not None


def topic_exists(topic_id: uuid.UUID) -> bool:
    with SessionLocal() as session:
        return session.get(Topic, topic_id) is not None
