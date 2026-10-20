import uuid

from sqlalchemy import delete, select

from .database import SessionLocal
from .models import Course, Topic
from .schemas import CourseOut, CourseSummary, TopicMap, TopicNode, TopicOut


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

        topics = session.scalars(
            select(Topic).where(Topic.course_id == course_id).order_by(Topic.position)
        ).all()

        nodes = {
            topic.id: TopicOut(
                id=topic.id,
                title=topic.title,
                description=topic.description,
                children=[],
            )
            for topic in topics
        }

        roots = []
        for topic in topics:
            node = nodes[topic.id]
            if topic.parent_id is None:
                roots.append(node)
            else:
                nodes[topic.parent_id].children.append(node)

        return CourseOut(
            id=course.id,
            title=course.title,
            initial_prompt=course.initial_prompt,
            created_at=course.created_at,
            topics=roots,
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
