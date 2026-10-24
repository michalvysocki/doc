import base64
import json
import logging
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from .schemas import (
    GeneratedTaskSet,
    LessonReview,
    RebuildPlan,
    RebuildPlanReview,
    TaskGrade,
    TaskSetReview,
    TopicMap,
    TopicMapReview,
)
from .validation import check_lesson, check_rebuild_plan, check_tasks, check_topic_map

logger = logging.getLogger(__name__)

# Receives short progress messages, e.g. to show them while a course is created.
StatusCallback = Callable[[str], None]

current_dir = Path(__file__).resolve().parent
load_dotenv(current_dir.parent / ".env")

URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("MODEL")
# The course map and rebuild are planned once per course, so they may use a
# stronger (more expensive) model than lessons, tasks and chats.
PLANNING_MODEL = os.getenv("PLANNING_MODEL") or MODEL
# For example "high"; empty means the model's default reasoning.
PLANNING_REASONING_EFFORT = os.getenv("PLANNING_REASONING_EFFORT") or None
# Lessons and tasks are reviewed by a stronger model than the one that writes them.
REVIEW_MODEL = os.getenv("REVIEW_MODEL") or MODEL
# REVIEW=off in .env turns the reviews off (they cost an extra model call each).
REVIEW_ENABLED = os.getenv("REVIEW", "on").lower() != "off"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
EMBEDDING_URL = "https://openrouter.ai/api/v1/embeddings"
WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH", "on").lower() != "off"
MAX_SOURCES = 8
EMBEDDING_BATCH_SIZE = 100

WEB_SEARCH_TOOL = {
    "type": "openrouter:web_search",
    "parameters": {"max_results": 5, "max_uses": 3},
}

DOCUMENT_SUMMARY_PROMPT = (
    "You describe a learner's uploaded file for a study app. Write 2-4 sentences "
    "about what the file is and what it covers, then a line starting with "
    "'Topics:' listing its main topics, comma-separated. Use the language of the "
    "file. Describe only what is in the file."
)
MAX_SUMMARY_INPUT_CHARS = 60_000
SUMMARY_SAMPLES = 12
SUMMARY_SAMPLE_CHARS = 5_000

SEARCH_QUERY_PROMPT = (
    "You prepare searches in a learner's course materials. Rewrite the learner's "
    "last message as a standalone search query: resolve references to earlier "
    "messages (such as 'it', 'the second point', 'this example') and keep the key "
    "terms. Write it in the language of the conversation, at most 30 words. If "
    "the message is already standalone, return it unchanged. Return only the "
    "query."
)
MAX_SEARCH_QUERY_CHARS = 500

SUMMARY_SYSTEM_PROMPT = (
    "You keep the memory of a tutoring conversation in a study app. Update the "
    "summary with the new messages: what the learner asked and wanted, what was "
    "explained, what they struggled with or got wrong, their preferences and "
    "decisions, and the files or images they mentioned. Use short bullet points, "
    "at most about 300 words, in the language of the conversation. Return only "
    "the updated summary."
)

MATH_FORMAT = (
    "Write math in LaTeX, with $...$ for inline formulas and $$...$$ on separate "
    "lines for display formulas. "
)

IMAGE_TRANSCRIPTION_PROMPT = (
    "You turn an image a learner uploaded (for example a photo of notes, a slide, "
    "a screenshot or a diagram) into text for a study app. Transcribe all text "
    "exactly, in its original language, keeping the structure with Markdown "
    "headings and lists. Write code in fenced code blocks. "
    + MATH_FORMAT
    + "Briefly describe diagrams, charts and drawings. Do not add explanations of "
    "your own. If there is nothing to transcribe or describe, answer only with: "
    "(no content)"
)

TOPIC_MAP_SYSTEM_PROMPT = (
    "You are an expert teacher designing a course. Based on the user's request, "
    "create a map of topics the learner should study, ordered from the basics "
    "to advanced topics. Use at most 3 levels of nesting. Each topic should be "
    "specific enough to study in a single session. "
    "When the course has more than about 10 topics, group them into modules "
    "(top-level topics with subtopics). Split a subtopic into its own subtopics "
    "only when it is too big for one study session, so the depth follows the "
    "content, up to 3 levels. "
    "Do not number the topic "
    "titles. Write titles and descriptions in the same language as the user's "
    "request. If course materials are given, base the map on them where they are "
    "relevant and cover what they contain. You can search the web when the course "
    "needs current information, such as new versions or recent tools; do not "
    "search for well-established subjects."
)

REBUILD_SYSTEM_PROMPT = (
    "You are an expert teacher redesigning an existing course. Create the complete "
    "new map of topics, ordered from the basics to advanced topics, at most 3 "
    "levels deep, each topic specific enough to study in a single session. "
    "When the course has more than about 10 topics, group them into modules "
    "(top-level topics with subtopics). Split a subtopic into its own subtopics "
    "only when it is too big for one study session, so the depth follows the "
    "content, up to 3 levels. "
    "For "
    "every topic that covers the same content as an existing topic, set "
    "existing_topic_id to that topic's id from the current outline, so its lesson, "
    "tasks and progress are kept; you may change its title, description and place. "
    "Prefer keeping topics with progress. Use each id at most once and null for "
    "new topics. Existing topics you leave out will be deleted. Do not number the "
    "titles. Write in the language of the course. "
    "You can search the web when the course needs current information, such as "
    "new versions or recent tools; do not search for well-established subjects."
)

TOPIC_EXPLANATION_SYSTEM_PROMPT = (
    "You are an expert teacher writing a lesson about one topic of a course. "
    "Explain the topic clearly for a learner using Markdown with headings, "
    "lists and examples. For technical topics include short code examples in "
    "fenced code blocks. "
    + MATH_FORMAT
    + "Aim for 500-1000 words. If the topic has subtopics, "
    "give only an overview of them, because each subtopic has its own lesson. "
    "Do not start with a heading that repeats the topic title. Write in the "
    "same language as the topic title. If course materials are given, base the "
    "lesson on them where they are relevant and stay consistent with them. If the "
    "learner gives instructions, follow them. If the course outline is given, do "
    "not explain in detail what other topics of the course cover; refer to them by "
    "title instead, and build on the topics listed before this one. If the "
    "learner's goal is given, choose examples that fit it. You can search the web "
    "when the topic needs current information, such as recent versions or "
    "changes; do not search for well-established basics. Do not write a list of "
    "sources; it is added automatically."
)

TOPIC_CHAT_SYSTEM_PROMPT = (
    "You are a patient tutor helping a learner with one lesson of a course. "
    "Use the current lesson as the main context. Use the course outline to relate "
    "this topic to other topics and mention them by title when relevant; if a "
    "question is covered by another topic, say which one. Use the course materials "
    "(fragments of other lessons and of uploaded documents) when they help, and "
    "mention the lesson title when you rely on another lesson. The learner also "
    "has practice tasks for this "
    "lesson; refer to them by their number. When helping with a task, explain "
    "concepts and give hints instead of writing the complete solution, unless the "
    "learner explicitly asks for it after trying. When the learner asks to split "
    "this lesson into smaller parts or to add subtopics, add them under this "
    "lesson with the add_subtopics tool. You may suggest subtopics, but add them "
    "only after the learner agrees. Check the outline to avoid duplicates and keep "
    "the course at most 3 levels deep. After adding, tell the learner what you "
    "added. When the learner wants more practice, add tasks with the add_tasks "
    "tool, at most 5 at a time: open questions or practical exercises (no multiple "
    "choice), each with grading notes listing the key points of a correct answer. "
    "Never reveal grading notes. You may suggest tasks, but add them only after "
    "the learner agrees. After adding, tell the learner the numbers of the new "
    "tasks. When the learner asks to regenerate or rewrite this lesson or its "
    "tasks, use propose_lesson_regeneration or propose_tasks_regeneration with "
    "their instructions; set use_files to true when they mention their files or "
    "materials. Nothing is generated until the learner confirms with the card. "
    "Never say the lesson or tasks were regenerated unless you see a "
    '"[Regenerated lesson]" or "[Regenerated tasks]" note in the conversation. '
    "You can search the web, but only when the question needs current or "
    "external information that the lesson and the course materials do not "
    "cover. Do not write your own list of sources; it is added automatically. "
    "If the learner profile shows they struggled with this or a related topic, "
    "take it into account when explaining. "
    "Answer in the language of the learner's last message and use Markdown. "
    + MATH_FORMAT
)

COURSE_CHAT_SYSTEM_PROMPT = (
    "You are a learning guide for a whole course. Help the learner plan and "
    "understand the course: what to study next, how topics relate to each other "
    "and what to review, using the course outline with progress markers. Use the "
    "course materials (fragments of lessons and of uploaded documents) when they "
    "help, and mention the lesson title when you rely on a lesson. When the "
    "learner asks for new topics, add "
    "them with the add_topics tool, using topic ids from the outline; if the "
    "request is unclear, ask first instead of guessing. Check the outline so you "
    "do not add duplicates, and keep the whole course at most 3 levels deep. "
    "After adding topics, tell the learner what you added. When the learner asks "
    "to rename a topic or change its description, use the rename_topic tool. To "
    "move a topic (with its subtopics) or change the order of topics, use the "
    "move_topic tool, keeping the course at most 3 levels deep. To delete a topic, "
    "use the propose_topic_deletion tool: it deletes nothing, it shows the learner "
    "a card with what would be lost and buttons to confirm or cancel. Tell the "
    "learner to decide with the buttons. Never say a topic was deleted unless you "
    'see a "[Deleted topic: ...]" note in the conversation. When the learner asks '
    "to rebuild or redesign the whole course, for example based on uploaded "
    "materials, use the propose_course_rebuild tool with their instructions; set "
    "use_files to true when they mention their files or materials. It changes "
    "nothing: the learner sees a preview and applies or discards it. For small "
    "changes prefer the other tools. Never say the course was rebuilt unless you "
    'see a "[Rebuilt course: ...]" note in the conversation. '
    "You can search the web, but only when the question needs current or "
    "external information that the lesson and the course materials do not "
    "cover. Do not write your own list of sources; it is added automatically. "
    "Use the learner profile to suggest what to review or study next; when tasks "
    "are due for review, mention it when the learner asks what to do. "
    "Answer in the language of the learner's last message and use Markdown. "
    + MATH_FORMAT
)

TASKS_SYSTEM_PROMPT = (
    "You are an expert teacher creating practice tasks for one lesson of a course. "
    "Create open questions and practical exercises (no multiple choice) that check "
    "real understanding of the lesson, ordered from easier to harder. Choose as "
    "many tasks as the topic needs, usually between 3 and 8. For technical topics "
    "include practical exercises, such as writing or analysing code. For each task "
    "write grading notes listing the key points a correct answer must contain; the "
    "learner never sees them. Write the questions in Markdown. "
    + MATH_FORMAT
    + "Write in the same "
    "language as the lesson. If course materials are given, use them as "
    "inspiration for the style, topics and difficulty of the tasks, but keep the "
    "tasks answerable from the lesson. If the learner gives instructions, follow "
    "them. If the learner's goal is given, prefer practical exercises that fit it."
)

GRADING_SYSTEM_PROMPT = (
    "You are a fair teacher grading a learner's answer to a practice task. Use the "
    "grading notes as the reference for what a correct answer must contain. Judge "
    "understanding, not wording: an answer may be phrased differently than the "
    "notes. Use 'correct' when all key points are covered without mistakes, "
    "'partially_correct' when some key points are covered or there are minor "
    "mistakes, and 'incorrect' otherwise. Write the feedback in the language of the "
    "learner's answer: what is good, what is missing or wrong, and a hint how to "
    "improve. Do not reveal the grading notes or write the full solution. Use "
    "Markdown. " + MATH_FORMAT
)


REVIEW_RULES = (
    "You review content generated for a study app. Check the draft against the "
    "criteria below and the issues found by automatic checks. List every real "
    "problem in issues, briefly. If anything should change, return the complete "
    "corrected version, keeping everything that is good unchanged; if nothing "
    "needs to change, return an empty issues list and null. Do not rewrite only "
    "for style. Keep the language of the draft. "
)

MAP_REVIEW_PROMPT = REVIEW_RULES + (
    "Criteria for a course map: it covers the learner's goal (and the course "
    "materials, if given) at the requested level, without going far beyond it; "
    "topics are ordered so that each builds on earlier ones; no topics are "
    "duplicated or overlap; every topic fits one study session; courses with more "
    "than about 10 topics are grouped into modules; at most 3 levels; titles are "
    "not numbered; each description says what the topic covers."
)

REBUILD_REVIEW_PROMPT = MAP_REVIEW_PROMPT + (
    " The plan must also follow the learner's instructions, keep existing_topic_id "
    "for every topic that keeps the same content, use each id at most once, and "
    "not drop existing topics (especially ones with progress) unless the "
    "instructions ask for it."
)

LESSON_REVIEW_PROMPT = REVIEW_RULES + (
    "Criteria for a lesson: facts, definitions, formulas and code examples are "
    "correct; it fits the learner's goal and level; it does not explain in detail "
    "what other topics of the outline cover; Markdown with headings, no heading "
    "that repeats the topic title; "
    + MATH_FORMAT
    + "code in fenced code blocks; no list of sources."
)

TASKS_REVIEW_PROMPT = REVIEW_RULES + (
    "Criteria for practice tasks: every task can be answered from the lesson; "
    "questions are clear open questions or exercises (no multiple choice); "
    "ordered from easier to harder; grading notes are correct and list the key "
    "points of a correct answer; no task repeats another."
)


class OpenRouterError(Exception):
    """Raised when a request to OpenRouter fails or returns an unexpected response."""


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


def _post_to_openrouter(
    url: str, payload: dict[str, Any], timeout: int
) -> dict[str, Any]:
    """
    Sends a POST request to OpenRouter and returns the parsed JSON response.

    Raises:
        OpenRouterError: if the request fails or OpenRouter returns an error status
    """

    try:
        response = requests.post(
            url=url,
            headers=_headers(),
            data=json.dumps(payload),
            timeout=timeout,
        )
        data = response.json()
    except requests.RequestException as e:
        raise OpenRouterError(f"Request to OpenRouter failed: {e}") from e

    if not response.ok:
        message = data.get("error", {}).get("message", "Unknown error")
        raise OpenRouterError(f"OpenRouter returned {response.status_code}: {message}")

    return data


def _stream_from_openrouter(
    url: str, payload: dict[str, Any], timeout: int
) -> Iterator[dict[str, Any]]:
    """
    Sends a streaming POST request to OpenRouter and yields every parsed chunk
    of the server-sent events, until "[DONE]".

    Raises:
        OpenRouterError: if the request fails, OpenRouter returns an error status,
            or the stream reports an error or breaks off
    """

    try:
        response = requests.post(
            url=url,
            headers=_headers(),
            data=json.dumps({**payload, "stream": True}),
            timeout=timeout,
            stream=True,
        )
    except requests.RequestException as e:
        raise OpenRouterError(f"Request to OpenRouter failed: {e}") from e

    with response:
        if not response.ok:
            try:
                message = (
                    response.json().get("error", {}).get("message", "Unknown error")
                )
            except ValueError:
                message = "Unknown error"
            raise OpenRouterError(
                f"OpenRouter returned {response.status_code}: {message}"
            )

        # Server-sent events carry no charset, so requests would guess ISO-8859-1.
        response.encoding = "utf-8"
        try:
            for line in response.iter_lines(decode_unicode=True):
                # Empty lines separate events; ": OPENROUTER PROCESSING" keeps the
                # connection alive.
                if not line or not line.startswith("data: "):
                    continue
                data = line.removeprefix("data: ")
                if data == "[DONE]":
                    return
                chunk = json.loads(data)
                if "error" in chunk:
                    message = chunk["error"].get("message", "Unknown error")
                    raise OpenRouterError(f"OpenRouter stream failed: {message}")
                yield chunk
        except (requests.RequestException, ValueError) as e:
            raise OpenRouterError(f"OpenRouter stream broke off: {e}") from e


def with_web_search(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adds the web search server tool, unless it is turned off in .env."""

    return [*tools, WEB_SEARCH_TOOL] if WEB_SEARCH_ENABLED else tools


def extract_web_sources(
    annotations: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """
    Returns the web pages the model cited (from the url_citation annotations),
    without duplicates and at most MAX_SOURCES.
    """

    sources: dict[str, str] = {}
    for annotation in annotations or []:
        if annotation.get("type") != "url_citation":
            continue
        citation = annotation.get("url_citation") or {}
        url = citation.get("url")
        if url and url not in sources:
            sources[url] = citation.get("title") or url

    return [
        {"kind": "web", "title": title, "url": url}
        for url, title in list(sources.items())[:MAX_SOURCES]
    ]


def append_sources(content: str, annotations: list[dict[str, Any]] | None) -> str:
    """Appends a Markdown list of the cited web pages (used for chat replies)."""

    sources = extract_web_sources(annotations)
    if not sources:
        return content
    lines = [
        f"- [{source['title'].replace('[', '(').replace(']', ')')}]({source['url']})"
        for source in sources
    ]
    return f"{content}\n\n**Sources**\n" + "\n".join(lines)


def stream_query_with_tools(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> Iterator[tuple[str, Any]]:
    """
    Sends messages with tool definitions and streams the model's answer. Yields
    ("delta", text) for every piece of text as it arrives, and at the end
    ("message", message) with the content, tool_calls and annotations put
    together; a message with tool_calls and no text has content None.
    """

    content: list[str] = []
    tool_calls: dict[int, dict[str, Any]] = {}
    annotations: list[dict[str, Any]] = []

    for chunk in _stream_from_openrouter(
        URL,
        {
            "model": MODEL,
            "messages": messages,
            "tools": with_web_search(tools),
            "plugins": [{"id": "file-parser", "pdf": {"engine": "cloudflare-ai"}}],
        },
        timeout=120,
    ):
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}

        if text := delta.get("content"):
            content.append(text)
            yield "delta", text

        # A tool call arrives in pieces: the id and name first, the arguments split up.
        for piece in delta.get("tool_calls") or []:
            call = tool_calls.setdefault(
                piece.get("index", 0),
                {
                    "id": None,
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                },
            )
            call["id"] = piece.get("id") or call["id"]
            function = piece.get("function") or {}
            call["function"]["name"] += function.get("name") or ""
            call["function"]["arguments"] += function.get("arguments") or ""

        annotations.extend(delta.get("annotations") or [])

    message: dict[str, Any] = {"role": "assistant", "content": "".join(content) or None}
    if tool_calls:
        message["tool_calls"] = [tool_calls[index] for index in sorted(tool_calls)]
    if annotations:
        message["annotations"] = annotations
    yield "message", message


def image_part(data: bytes, media_type: str) -> dict[str, Any]:
    """Returns an image as a message content part (a base64 data URL)."""

    encoded = base64.b64encode(data).decode()
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{media_type};base64,{encoded}"},
    }


def transcribe_image(data: bytes, media_type: str) -> str | None:
    """
    Turns an uploaded image into Markdown text for RAG.

    Returns:
        str | None: the transcription, or None if the image has no content

    Raises:
        OpenRouterError: if the model request fails
    """

    response = _post_to_openrouter(
        URL,
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": IMAGE_TRANSCRIPTION_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Transcribe this image."},
                        image_part(data, media_type),
                    ],
                },
            ],
        },
        timeout=120,
    )
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise OpenRouterError("Unexpected response format from OpenRouter") from e

    if not content or content.strip() == "(no content)":
        return None
    return content


def sample_text(text: str) -> str:
    """Returns the whole text if short, or evenly spaced excerpts of a long one."""

    if len(text) <= MAX_SUMMARY_INPUT_CHARS:
        return text
    last_start = len(text) - SUMMARY_SAMPLE_CHARS
    starts = [
        round(i * last_start / (SUMMARY_SAMPLES - 1)) for i in range(SUMMARY_SAMPLES)
    ]
    excerpts = [text[start : start + SUMMARY_SAMPLE_CHARS] for start in starts]
    return "(Excerpts from a longer document)\n\n" + "\n\n[...]\n\n".join(excerpts)


def summarize_document(filename: str, text: str) -> str:
    """
    Describes an uploaded file in a few sentences with its main topics. Long
    files are described from evenly spaced excerpts.

    Raises:
        OpenRouterError: if the request fails or the summary is empty
    """

    response = _post_to_openrouter(
        URL,
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": DOCUMENT_SUMMARY_PROMPT},
                {
                    "role": "user",
                    "content": f"FILE: {filename}\n\n{sample_text(text)}",
                },
            ],
        },
        timeout=120,
    )
    try:
        summary = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise OpenRouterError("Unexpected response format from OpenRouter") from e
    if not summary or not summary.strip():
        raise OpenRouterError("Model returned an empty file summary")
    return summary.strip()


def rewrite_search_query(
    recent: list[dict[str, str]], question: str, topic: str | None = None
) -> str:
    """
    Turns the learner's message into a standalone query for RAG, using the
    recent messages (dicts with role and content) to resolve references.

    Raises:
        OpenRouterError: if the request fails
    """

    transcript = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in recent)
    context = (f"CURRENT LESSON: {topic}\n\n" if topic else "") + (
        f"RECENT MESSAGES:\n{transcript}\n\nLAST MESSAGE:\n{question}"
    )
    response = _post_to_openrouter(
        URL,
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SEARCH_QUERY_PROMPT},
                {"role": "user", "content": context},
            ],
        },
        timeout=30,
    )
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise OpenRouterError("Unexpected response format from OpenRouter") from e

    query = (content or "").strip()[:MAX_SEARCH_QUERY_CHARS]
    return query or question


def summarize_conversation(previous: str | None, messages: list[dict[str, str]]) -> str:
    """
    Folds older messages (dicts with role and content) into the conversation
    summary.

    Raises:
        OpenRouterError: if the request fails or the summary is empty
    """

    transcript = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
    context = (
        f"CURRENT SUMMARY:\n{previous or '(none yet)'}\n\nNEW MESSAGES:\n{transcript}"
    )
    response = _post_to_openrouter(
        URL,
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
        },
        timeout=120,
    )
    try:
        summary = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise OpenRouterError("Unexpected response format from OpenRouter") from e
    if not summary:
        raise OpenRouterError("Model returned an empty summary")
    return summary


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Returns embeddings for the texts, in the same order, sending them in
    batches of EMBEDDING_BATCH_SIZE so large documents stay within the
    provider's limits per request.

    Raises:
        OpenRouterError: if a request fails or the response is malformed
    """

    embeddings: list[list[float]] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + EMBEDDING_BATCH_SIZE]
        data = _post_to_openrouter(
            EMBEDDING_URL, {"model": EMBEDDING_MODEL, "input": batch}, timeout=60
        )
        try:
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            batch_embeddings = [item["embedding"] for item in sorted_data]
        except (KeyError, TypeError) as e:
            raise OpenRouterError(
                "Unexpected embedding response format from OpenRouter"
            ) from e
        if len(batch_embeddings) != len(batch):
            raise OpenRouterError("OpenRouter returned a wrong number of embeddings")
        embeddings.extend(batch_embeddings)
    return embeddings


def _structured_query_with_sources[T: BaseModel](
    messages: list[dict[str, Any]],
    schema: type[T],
    name: str,
    timeout: int,
    web_search: bool = False,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> tuple[T, list[dict[str, Any]]]:
    """
    Asks the model for a JSON response matching the schema (strict structured
    output), optionally letting it search the web, and validates it.

    Returns:
        tuple[T, list[dict[str, Any]]]: the parsed response and the cited web
            pages

    Raises:
        OpenRouterError: if the request fails or the response does not match
    """

    payload: dict[str, Any] = {
        "model": model or MODEL,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": name,
                "strict": True,
                "schema": schema.model_json_schema(),
            },
        },
    }
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}
    tools = with_web_search([]) if web_search else []
    if tools:
        payload["tools"] = tools
    data = _post_to_openrouter(URL, payload, timeout=timeout)

    try:
        message = data["choices"][0]["message"]
        result = schema.model_validate_json(message["content"])
    except (KeyError, IndexError, ValidationError) as e:
        raise OpenRouterError(f"Model returned an invalid {name}") from e

    return result, extract_web_sources(message.get("annotations"))


def _structured_query[T: BaseModel](
    messages: list[dict[str, Any]],
    schema: type[T],
    name: str,
    timeout: int,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> T:
    """Like _structured_query_with_sources, without web search."""

    return _structured_query_with_sources(
        messages,
        schema,
        name,
        timeout,
        model=model,
        reasoning_effort=reasoning_effort,
    )[0]


def _review[T: BaseModel](
    system_prompt: str,
    context: str,
    draft: str,
    issues: list[str],
    schema: type[T],
    name: str,
    model: str,
    reasoning_effort: str | None = None,
) -> T:
    """
    Asks a model to check a draft against the criteria in the system prompt and
    the issues found by automatic checks.

    Raises:
        OpenRouterError: if the request fails or the answer does not match the schema
    """

    found = "\n".join(f"- {issue}" for issue in issues) or "- none"
    return _structured_query(
        [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"{context}\n\nDRAFT:\n{draft}\n\n"
                f"ISSUES FOUND BY AUTOMATIC CHECKS:\n{found}",
            },
        ],
        schema,
        name=name,
        timeout=300,
        model=model,
        reasoning_effort=reasoning_effort,
    )


def _reviewed[T](
    kind: str,
    label: str,
    draft: T,
    check: Callable[[T], list[str]],
    review: Callable[[list[str]], Any],
    revised_of: Callable[[Any], T | None],
    on_status: StatusCallback | None = None,
) -> T:
    """
    Checks a draft, lets a model review it and returns the revised version.
    Keeps the draft when nothing needs to change, when the review fails or when
    the revision has more problems than the draft: a review must never block
    generating a course, lesson or tasks.
    """

    if not REVIEW_ENABLED:
        return draft

    issues = check(draft)
    if on_status:
        on_status(f"Checking the {kind.lower()}…")
    try:
        result = review(issues)
    except OpenRouterError as e:
        logger.warning(
            '%s review for "%s" failed, keeping the draft: %s', kind, label, e
        )
        return draft

    revised = revised_of(result)
    if revised is not None and len(check(revised)) > len(issues):
        logger.warning(
            '%s review for "%s" made it worse, keeping the draft', kind, label
        )
        revised = None

    logger.info(
        '%s review for "%s": %d issues, %s',
        kind,
        label,
        len(result.issues),
        "revised" if revised is not None else "kept",
    )
    for issue in result.issues:
        logger.info("  - %s", issue)
    return revised if revised is not None else draft


def review_topic_map(
    context: str, topic_map: TopicMap, issues: list[str]
) -> TopicMapReview:
    return _review(
        MAP_REVIEW_PROMPT,
        context,
        topic_map.model_dump_json(indent=1),
        issues,
        TopicMapReview,
        name="topic_map_review",
        model=PLANNING_MODEL,
        reasoning_effort=PLANNING_REASONING_EFFORT,
    )


def review_rebuild_plan(
    context: str, plan: RebuildPlan, issues: list[str]
) -> RebuildPlanReview:
    return _review(
        REBUILD_REVIEW_PROMPT,
        context,
        plan.model_dump_json(indent=1),
        issues,
        RebuildPlanReview,
        name="rebuild_plan_review",
        model=PLANNING_MODEL,
        reasoning_effort=PLANNING_REASONING_EFFORT,
    )


def review_lesson(context: str, lesson: str, issues: list[str]) -> LessonReview:
    return _review(
        LESSON_REVIEW_PROMPT,
        context,
        lesson,
        issues,
        LessonReview,
        name="lesson_review",
        model=REVIEW_MODEL,
    )


def review_tasks(
    context: str, task_set: GeneratedTaskSet, issues: list[str]
) -> TaskSetReview:
    return _review(
        TASKS_REVIEW_PROMPT,
        context,
        task_set.model_dump_json(indent=1),
        issues,
        TaskSetReview,
        name="tasks_review",
        model=REVIEW_MODEL,
    )


def generate_topic_map(
    initial_prompt: str,
    materials: str | None = None,
    on_status: StatusCallback | None = None,
) -> tuple[TopicMap, list[dict[str, Any]]]:
    if on_status:
        on_status("Planning the course map…")
    context = _with_extras(initial_prompt, None, materials)
    topic_map, sources = _structured_query_with_sources(
        [
            {"role": "system", "content": TOPIC_MAP_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        TopicMap,
        name="topic_map",
        timeout=240,
        web_search=True,
        model=PLANNING_MODEL,
        reasoning_effort=PLANNING_REASONING_EFFORT,
    )
    topic_map = _reviewed(
        "Map",
        topic_map.course_title,
        topic_map,
        check_topic_map,
        lambda issues: review_topic_map(context, topic_map, issues),
        lambda result: result.revised,
        on_status=on_status,
    )
    return topic_map, sources


def _with_extras(text: str, instructions: str | None, materials: str | None) -> str:
    """Appends course materials and the learner's instructions (last) to a prompt."""

    if materials:
        text += f"\n\n{materials}"
    if instructions:
        text += f"\n\nLEARNER'S INSTRUCTIONS:\n{instructions}"
    return text


def generate_topic_explanation(
    course_title: str,
    path: list[str],
    title: str,
    description: str,
    subtopics: list[str],
    instructions: str | None = None,
    materials: str | None = None,
    goal: str | None = None,
    outline: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    context_lines = [
        f"Course: {course_title}",
        *([f"Learner's goal: {goal}"] if goal else []),
        f"Topic path: {' > '.join([*path, title])}",
        f"Topic: {title}",
        f"Topic description: {description}",
    ]
    if subtopics:
        context_lines.append(
            "Subtopics covered in separate lessons: " + ", ".join(subtopics)
        )
    if outline:
        context_lines.append(f"\nCOURSE OUTLINE:\n{outline}")

    context = _with_extras("\n".join(context_lines), instructions, materials)
    payload: dict[str, Any] = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": TOPIC_EXPLANATION_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
    }
    tools = with_web_search([])
    if tools:
        payload["tools"] = tools
    data = _post_to_openrouter(URL, payload, timeout=240)

    try:
        message = data["choices"][0]["message"]
        content = message["content"]
    except (KeyError, IndexError) as e:
        raise OpenRouterError("Unexpected response format from OpenRouter") from e

    if not content:
        raise OpenRouterError("Model returned an empty explanation")

    lesson = _reviewed(
        "Lesson",
        title,
        content,
        lambda text: check_lesson(text, title),
        lambda issues: review_lesson(context, content, issues),
        lambda result: result.revised_lesson,
    )
    return lesson, extract_web_sources(message.get("annotations"))


def generate_tasks(
    course_title: str,
    path: list[str],
    title: str,
    lesson: str,
    instructions: str | None = None,
    materials: str | None = None,
    goal: str | None = None,
) -> GeneratedTaskSet:
    context = _with_extras(
        f"Course: {course_title}\n"
        + (f"Learner's goal: {goal}\n" if goal else "")
        + f"Topic path: {' > '.join([*path, title])}\n\n"
        f"LESSON:\n{lesson}",
        instructions,
        materials,
    )
    task_set = _structured_query(
        [
            {"role": "system", "content": TASKS_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        GeneratedTaskSet,
        name="task_set",
        timeout=180,
    )
    return _reviewed(
        "Tasks",
        title,
        task_set,
        check_tasks,
        lambda issues: review_tasks(context, task_set, issues),
        lambda result: result.revised,
    )


def generate_rebuild_plan(
    course_title: str,
    initial_prompt: str,
    outline: str,
    instructions: str | None = None,
    materials: str | None = None,
    existing_ids: set[str] | None = None,
) -> tuple[RebuildPlan, list[dict[str, Any]]]:
    context = _with_extras(
        f"Course: {course_title}\n"
        f"Course goal (the learner's original request): {initial_prompt}\n\n"
        f"CURRENT OUTLINE:\n{outline}",
        instructions,
        materials,
    )
    plan, sources = _structured_query_with_sources(
        [
            {"role": "system", "content": REBUILD_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        RebuildPlan,
        name="rebuild_plan",
        timeout=300,
        web_search=True,
        model=PLANNING_MODEL,
        reasoning_effort=PLANNING_REASONING_EFFORT,
    )
    plan = _reviewed(
        "Rebuild",
        course_title,
        plan,
        lambda draft: check_rebuild_plan(draft, existing_ids or set()),
        lambda issues: review_rebuild_plan(context, plan, issues),
        lambda result: result.revised,
    )
    return plan, sources


def build_grading_messages(
    question: str, grading_notes: str, answer: str
) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": GRADING_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"TASK:\n{question}\n\n"
                f"GRADING NOTES:\n{grading_notes}\n\n"
                f"LEARNER'S ANSWER:\n{answer}"
            ),
        },
    ]


def grade_answer(question: str, grading_notes: str, answer: str) -> TaskGrade:
    return _structured_query(
        build_grading_messages(question, grading_notes, answer),
        TaskGrade,
        name="task_grade",
        timeout=120,
    )


if __name__ == "__main__":
    sample_text = """
    Sztuczna inteligencja (AI) oraz duże modele językowe (tzw. LLM) zrewolucjonizowały sposób, 
    w jaki wchodzimy w interakcję z maszynami. Jeszcze dekadę temu wygenerowanie płynnego, 
    sensownego tekstu przez komputer wydawało się mrzonką. Dzisiaj algorytmy są w stanie pisać eseje, 
    analizować dane i programować. Modele te uczą się na potężnych zbiorach danych, które obejmują 
    m.in. artykuły naukowe, książki oraz zasoby internetowe.
        
    Jednakże, mimo swojej imponującej wiedzy, modele językowe mają pewne fundamentalne ograniczenia. 
    Przede wszystkim nie posiadają one domyślnego dostępu do wiedzy w czasie rzeczywistym. 
    Mają również tendencję do tzw. halucynacji, czyli zmyślania faktów w bardzo przekonujący sposób. 
    Rozwiązaniem tego problemu jest architektura RAG (Retrieval-Augmented Generation). 
    Pozwala ona na dynamiczne przeszukiwanie zewnętrznych baz danych, np. dokumentów firmowych, 
    zanim model wygeneruje ostateczną odpowiedź dla użytkownika.
        
    W procesie tym kluczową rolę odgrywają wektorowe bazy danych, takie jak ChromaDB czy Qdrant. 
    Zanim jednak jakikolwiek tekst trafi do bazy, musi zostać starannie podzielony na mniejsze fragmenty. 
    Każdy taki fragment jest następnie zamieniany na ciąg liczb, czyli wektor osadzeń (embedding). 
    Dzięki temu, gdy użytkownik zadaje pytanie o godz. 14:30 dotyczące specyfikacji tajnego projektu, 
    system może błyskawicznie odnaleźć odpowiedni paragraf. To właśnie precyzyjne cięcie tekstu 
    gwarantuje, że model otrzyma właściwy kontekst i odpowie bezbłędnie.
    """

    result = get_embeddings([sample_text])
    print(len(result))
