import json
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from .schemas import GeneratedTaskSet, RebuildPlan, TaskGrade, TopicMap

current_dir = Path(__file__).resolve().parent
load_dotenv(current_dir.parent / ".env")

URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("MODEL")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
EMBEDDING_URL = "https://openrouter.ai/api/v1/embeddings"

TOPIC_MAP_SYSTEM_PROMPT = (
    "You are an expert teacher designing a course. Based on the user's request, "
    "create a map of topics the learner should study, ordered from the basics "
    "to advanced topics. Use at most 3 levels of nesting. Each topic should be "
    "specific enough to study in a single session. Do not number the topic "
    "titles. Write titles and descriptions in the same language as the user's "
    "request."
)

REBUILD_SYSTEM_PROMPT = (
    "You are an expert teacher redesigning an existing course. Create the complete "
    "new map of topics, ordered from the basics to advanced topics, at most 3 "
    "levels deep, each topic specific enough to study in a single session. For "
    "every topic that covers the same content as an existing topic, set "
    "existing_topic_id to that topic's id from the current outline, so its lesson, "
    "tasks and progress are kept; you may change its title, description and place. "
    "Prefer keeping topics with progress. Use each id at most once and null for "
    "new topics. Existing topics you leave out will be deleted. Do not number the "
    "titles. Write in the language of the course."
)

TOPIC_EXPLANATION_SYSTEM_PROMPT = (
    "You are an expert teacher writing a lesson about one topic of a course. "
    "Explain the topic clearly for a learner using Markdown with headings, "
    "lists and examples. For technical topics include short code examples in "
    "fenced code blocks. Aim for 500-1000 words. If the topic has subtopics, "
    "give only an overview of them, because each subtopic has its own lesson. "
    "Do not start with a heading that repeats the topic title. Write in the "
    "same language as the topic title. If course materials are given, base the "
    "lesson on them where they are relevant and stay consistent with them. If the "
    "learner gives instructions, follow them."
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
    "Answer in the language of the learner's last message and use Markdown."
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
    'see a "[Rebuilt course: ...]" note in the conversation. Answer in the language '
    "of the learner's last message and use Markdown."
)

TASKS_SYSTEM_PROMPT = (
    "You are an expert teacher creating practice tasks for one lesson of a course. "
    "Create open questions and practical exercises (no multiple choice) that check "
    "real understanding of the lesson, ordered from easier to harder. Choose as "
    "many tasks as the topic needs, usually between 3 and 8. For technical topics "
    "include practical exercises, such as writing or analysing code. For each task "
    "write grading notes listing the key points a correct answer must contain; the "
    "learner never sees them. Write the questions in Markdown. Write in the same "
    "language as the lesson. If course materials are given, use them as "
    "inspiration for the style, topics and difficulty of the tasks, but keep the "
    "tasks answerable from the lesson. If the learner gives instructions, follow "
    "them."
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
    "Markdown."
)


class OpenRouterError(Exception):
    """Raised when a request to OpenRouter fails or returns an unexpected response."""


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
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
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


def send_query(messages: list[dict[str, Any]]) -> str:
    data = _post_to_openrouter(
        URL,
        {
            "model": MODEL,
            "messages": messages,
            "plugins": [{"id": "file-parser", "pdf": {"engine": "cloudflare-ai"}}],
        },
        timeout=120,
    )

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise OpenRouterError("Unexpected response format from OpenRouter") from e


def send_query_with_tools(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Sends messages with tool definitions and returns the model's message, which
    contains either text content or tool_calls.
    """

    data = _post_to_openrouter(
        URL,
        {
            "model": MODEL,
            "messages": messages,
            "tools": tools,
            "plugins": [{"id": "file-parser", "pdf": {"engine": "cloudflare-ai"}}],
        },
        timeout=120,
    )

    try:
        return data["choices"][0]["message"]
    except (KeyError, IndexError) as e:
        raise OpenRouterError("Unexpected response format from OpenRouter") from e


def get_embeddings(texts: list[str]) -> list[list[float]]:
    data = _post_to_openrouter(
        EMBEDDING_URL, {"model": EMBEDDING_MODEL, "input": texts}, timeout=60
    )

    try:
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]
    except (KeyError, TypeError) as e:
        raise OpenRouterError(
            "Unexpected embedding response format from OpenRouter"
        ) from e


def _structured_query[T: BaseModel](
    messages: list[dict[str, Any]], schema: type[T], name: str, timeout: int
) -> T:
    """
    Asks the model for a JSON response matching the schema (strict structured
    output) and validates it.

    Raises:
        OpenRouterError: if the request fails or the response does not match
    """

    data = _post_to_openrouter(
        URL,
        {
            "model": MODEL,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": name,
                    "strict": True,
                    "schema": schema.model_json_schema(),
                },
            },
        },
        timeout=timeout,
    )

    try:
        return schema.model_validate_json(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, ValidationError) as e:
        raise OpenRouterError(f"Model returned an invalid {name}") from e


def generate_topic_map(initial_prompt: str) -> TopicMap:
    return _structured_query(
        [
            {"role": "system", "content": TOPIC_MAP_SYSTEM_PROMPT},
            {"role": "user", "content": initial_prompt},
        ],
        TopicMap,
        name="topic_map",
        timeout=180,
    )


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
) -> str:
    context_lines = [
        f"Course: {course_title}",
        f"Topic path: {' > '.join([*path, title])}",
        f"Topic: {title}",
        f"Topic description: {description}",
    ]
    if subtopics:
        context_lines.append(
            "Subtopics covered in separate lessons: " + ", ".join(subtopics)
        )

    data = _post_to_openrouter(
        URL,
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": TOPIC_EXPLANATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _with_extras(
                        "\n".join(context_lines), instructions, materials
                    ),
                },
            ],
        },
        timeout=180,
    )

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise OpenRouterError("Unexpected response format from OpenRouter") from e

    if not content:
        raise OpenRouterError("Model returned an empty explanation")

    return content


def generate_tasks(
    course_title: str,
    path: list[str],
    title: str,
    lesson: str,
    instructions: str | None = None,
    materials: str | None = None,
) -> GeneratedTaskSet:
    context = _with_extras(
        f"Course: {course_title}\n"
        f"Topic path: {' > '.join([*path, title])}\n\n"
        f"LESSON:\n{lesson}",
        instructions,
        materials,
    )
    return _structured_query(
        [
            {"role": "system", "content": TASKS_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        GeneratedTaskSet,
        name="task_set",
        timeout=180,
    )


def generate_rebuild_plan(
    course_title: str,
    initial_prompt: str,
    outline: str,
    instructions: str | None = None,
    materials: str | None = None,
) -> RebuildPlan:
    context = _with_extras(
        f"Course: {course_title}\n"
        f"Course goal (the learner's original request): {initial_prompt}\n\n"
        f"CURRENT OUTLINE:\n{outline}",
        instructions,
        materials,
    )
    return _structured_query(
        [
            {"role": "system", "content": REBUILD_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        RebuildPlan,
        name="rebuild_plan",
        timeout=240,
    )


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
