"""Checks of generated content that need no model; the issues go to the reviewer."""

import re
import uuid
from difflib import SequenceMatcher

from .schemas import GeneratedTaskSet, RebuildPlan, TopicMap

MAX_DEPTH = 3
# " ([doc.rust-lang.org](https://...))": a citation added by web search
CITATION = re.compile(r"\s*\(\[[^\]]*\]\([^)]*\)\)")
# "[text](https://...)": a Markdown link; titles and descriptions are plain text
LINK = re.compile(r"\[([^\]]+)\]\(https?://[^)]*\)")
# "1. Basics", "2) Loops", "Module 3: ...", "Lesson 4 - ..."
NUMBERED_TITLE = re.compile(
    r"^\s*(\d+[.)]|(module|lesson|part|chapter)\s+\d+\b)", re.IGNORECASE
)


def _check_nodes(
    nodes, issues: list[str], titles: dict[str, int], depth: int = 1
) -> None:
    for node in nodes:
        title = node.title.strip()
        if depth > MAX_DEPTH:
            issues.append(f'"{title}" is deeper than {MAX_DEPTH} levels.')
        if not node.description.strip():
            issues.append(f'"{title}" has no description.')
        if NUMBERED_TITLE.match(title):
            issues.append(f'"{title}" is numbered; titles must not be numbered.')
        key = title.casefold()
        titles[key] = titles.get(key, 0) + 1
        if titles[key] == 2:
            issues.append(f'"{title}" appears more than once.')
        _check_nodes(node.children, issues, titles, depth + 1)


def check_topic_map(topic_map: TopicMap) -> list[str]:
    issues: list[str] = []
    if not topic_map.topics:
        issues.append("The map has no topics.")
    _check_nodes(topic_map.topics, issues, {})
    return issues


def _canonical_id(value: str) -> str:
    """The id in the form the database uses, so differently written ids match."""

    try:
        return str(uuid.UUID(value))
    except ValueError:
        return value


def check_rebuild_plan(plan: RebuildPlan, existing_ids: set[str]) -> list[str]:
    issues: list[str] = []
    if not plan.topics:
        issues.append("The plan has no topics.")
    _check_nodes(plan.topics, issues, {})

    used: set[str] = set()

    def check_ids(nodes) -> None:
        for node in nodes:
            topic_id = node.existing_topic_id
            if topic_id is not None:
                topic_id = _canonical_id(topic_id)
                if topic_id not in existing_ids:
                    issues.append(
                        f'"{node.title}" points to an unknown topic id {topic_id}.'
                    )
                elif topic_id in used:
                    issues.append(f"Topic id {topic_id} is used more than once.")
                used.add(topic_id)
            check_ids(node.children)

    check_ids(plan.topics)
    return issues


def check_lesson(lesson: str, topic_title: str) -> list[str]:
    issues: list[str] = []
    if not lesson.strip():
        return ["The lesson is empty."]

    first_heading = re.search(r"^#{1,6}\s+(.+)$", lesson, re.MULTILINE)
    if (
        first_heading
        and first_heading.group(1).strip().casefold() == topic_title.strip().casefold()
    ):
        issues.append("The lesson starts with a heading that repeats the topic title.")
    if lesson.count("```") % 2:
        issues.append("A fenced code block is not closed.")
    # Display math outside code blocks must come in pairs of $$.
    text_only = re.sub(r"```.*?```", "", lesson, flags=re.DOTALL)
    if text_only.count("$$") % 2:
        issues.append("A $$ display formula is not closed.")
    return issues


def check_tasks(task_set: GeneratedTaskSet) -> list[str]:
    issues: list[str] = []
    if not task_set.tasks:
        return ["There are no tasks."]

    seen: set[str] = set()
    for number, task in enumerate(task_set.tasks, start=1):
        if not task.question.strip():
            issues.append(f"Task {number} has no question.")
        if not task.grading_notes.strip():
            issues.append(f"Task {number} has no grading notes.")
        key = " ".join(task.question.casefold().split())
        if key and key in seen:
            issues.append(f"Task {number} repeats an earlier question.")
        seen.add(key)
    return issues


# Above this a follow-up task is a reworded copy of the original task.
MAX_FOLLOW_UP_SIMILARITY = 0.6


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def check_follow_up(task_set: GeneratedTaskSet, original_question: str) -> list[str]:
    """Checks a follow-up task like other tasks, and that it is not the original again."""

    issues = check_tasks(task_set)
    original = _normalized(original_question)
    for task in task_set.tasks:
        ratio = SequenceMatcher(None, _normalized(task.question), original).ratio()
        if ratio > MAX_FOLLOW_UP_SIMILARITY:
            issues.append(
                "The task repeats the original task instead of targeting what the "
                "answer missed."
            )
    return issues


def strip_links(text: str) -> str:
    """Removes web search citations and Markdown links from plain text."""

    return LINK.sub(r"\1", CITATION.sub("", text)).strip()


def strip_links_from_tree(nodes) -> None:
    """Cleans titles and descriptions of a topic tree in place."""

    for node in nodes:
        node.title = strip_links(node.title)
        node.description = strip_links(node.description)
        strip_links_from_tree(node.children)
