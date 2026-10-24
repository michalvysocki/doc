import json
import logging
import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from .chat import (
    ChatEvent,
    NothingToRetryError,
    add_course_note,
    add_topic_note,
    list_course_messages,
    list_topic_messages,
    retry_course_message,
    retry_topic_message,
    send_course_message,
    send_topic_message,
)
from .course_rebuilds import (
    apply_course_rebuild,
    discard_course_rebuild,
    get_course_rebuild,
)
from .courses import (
    course_exists,
    create_course_with_files,
    create_explanation,
    delete_course,
    get_course,
    get_topic,
    list_courses,
    save_course,
    topic_exists,
)
from .file_parsing import (
    FileParsingError,
    FileTooLargeError,
    prepare_upload,
    read_upload,
)
from .openrouter import OpenRouterError, generate_topic_map
from .regenerations import (
    cancel_regeneration,
    confirm_regeneration,
    list_regenerations,
)
from .schemas import (
    AttemptCreate,
    AttemptOut,
    ChatMessageOut,
    CourseCreate,
    CourseFileOut,
    CourseOut,
    CourseRebuildOut,
    CourseSummary,
    MessageCreate,
    PendingRegenerationOut,
    ReviewTaskOut,
    TaskOut,
    TopicDeletionOut,
    TopicDetail,
)
from .tasks import (
    LessonMissingError,
    create_tasks,
    get_due_reviews,
    get_tasks,
    grade_attempt,
    submit_attempt,
)
from .topic_deletions import (
    cancel_topic_deletion,
    confirm_topic_deletion,
    list_topic_deletions,
)
from .vectorstore import (
    DocumentTooLargeError,
    add_document,
    delete_document,
    get_image,
    list_course_files,
)

logger = logging.getLogger(__name__)

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/parse_file")
def parse_file(file: UploadFile, course_id: Annotated[uuid.UUID, Form()]):
    if not course_exists(course_id):
        raise HTTPException(status_code=404, detail="Course not found")

    try:
        parsed = prepare_upload(file.filename, file.content_type, read_upload(file))
    except FileTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    except FileParsingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    try:
        file_uuid = add_document(
            parsed.text,
            file.filename,
            course_id,
            media_type=parsed.media_type,
            content=parsed.content,
            summary=parsed.summary,
        )
    except DocumentTooLargeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return {"filename": file.filename, "file_uuid": file_uuid}


@app.get("/files/{file_uuid}/content")
def read_file_content(file_uuid: uuid.UUID):
    image = get_image(file_uuid)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    content, media_type = image
    return Response(content=content, media_type=media_type)


@app.delete("/delete_file/{file_uuid}", status_code=204)
def delete_file(file_uuid: uuid.UUID):
    if not delete_document(file_uuid):
        raise HTTPException(
            status_code=404, detail=f"File with UUID {file_uuid} was not found"
        )


@app.get("/courses", response_model=list[CourseSummary])
def read_courses():
    return list_courses()


MAX_FILES_PER_COURSE = 10


@app.post("/courses", status_code=201, response_model=CourseOut)
def create_course(
    initial_prompt: Annotated[str, Form()],
    files: Annotated[list[UploadFile] | None, File()] = None,
):
    try:
        request = CourseCreate(initial_prompt=initial_prompt)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors()) from e
    files = files or []
    if len(files) > MAX_FILES_PER_COURSE:
        raise HTTPException(
            status_code=400, detail=f"At most {MAX_FILES_PER_COURSE} files per course"
        )

    texts = []
    for file in files:
        try:
            parsed = prepare_upload(file.filename, file.content_type, read_upload(file))
        except FileParsingError as e:
            raise HTTPException(status_code=400, detail=f"{file.filename}: {e}") from e
        except OpenRouterError as e:
            raise HTTPException(status_code=502, detail=f"{file.filename}: {e}") from e
        texts.append((file.filename, parsed))

    try:
        if texts:
            course_id = create_course_with_files(request.initial_prompt, texts)
        else:
            topic_map, sources = generate_topic_map(request.initial_prompt)
            course_id = save_course(request.initial_prompt, topic_map, sources)
    except DocumentTooLargeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return get_course(course_id)


@app.get("/courses/{course_id}/reviews", response_model=list[ReviewTaskOut])
def read_reviews(course_id: uuid.UUID):
    if not course_exists(course_id):
        raise HTTPException(status_code=404, detail="Course not found")

    return get_due_reviews(course_id)


@app.get("/courses/{course_id}/files", response_model=list[CourseFileOut])
def read_course_files(course_id: uuid.UUID):
    if not course_exists(course_id):
        raise HTTPException(status_code=404, detail="Course not found")

    return list_course_files(course_id)


@app.get("/courses/{course_id}", response_model=CourseOut)
def read_course(course_id: uuid.UUID):
    course = get_course(course_id)

    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    return course


@app.delete("/courses/{course_id}", status_code=204)
def remove_course(course_id: uuid.UUID):
    if not delete_course(course_id):
        raise HTTPException(status_code=404, detail="Course not found")


@app.get("/topics/{topic_id}", response_model=TopicDetail)
def read_topic(topic_id: uuid.UUID):
    topic = get_topic(topic_id)

    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    return topic


@app.post("/topics/{topic_id}/explanation", response_model=TopicDetail)
def post_topic_explanation(topic_id: uuid.UUID):
    try:
        topic = create_explanation(topic_id)
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    return topic


@app.get("/topics/{topic_id}/messages", response_model=list[ChatMessageOut])
def read_topic_messages(topic_id: uuid.UUID):
    if not topic_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")

    return list_topic_messages(topic_id)


def _event_line(event: ChatEvent) -> str:
    # jsonable_encoder turns the Pydantic models (ChatReply, ChatMessageOut),
    # dates and UUIDs inside an event into plain JSON values.
    return json.dumps(jsonable_encoder(event)) + "\n"


def _stream_chat(
    events: Iterator[ChatEvent], status_code: int = 200
) -> StreamingResponse:
    """
    Sends chat events as JSON lines (NDJSON). The status is already sent when
    the stream starts, so a failure on the way becomes a last "error" event.
    """

    def lines() -> Iterator[str]:
        try:
            for event in events:
                yield _event_line(event)
        except OpenRouterError as e:
            yield _event_line({"type": "error", "detail": str(e)})
        except Exception:
            logger.exception("Chat stream failed")
            yield _event_line(
                {"type": "error", "detail": "Something went wrong while answering"}
            )

    return StreamingResponse(
        lines(),
        status_code=status_code,
        media_type="application/x-ndjson",
        # Stops proxies and browsers from buffering the stream.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/topics/{topic_id}/messages", status_code=201)
def post_topic_message(topic_id: uuid.UUID, request: MessageCreate):
    events = send_topic_message(topic_id, request.content, request.file_uuids)
    if events is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    return _stream_chat(events, status_code=201)


@app.post("/topics/{topic_id}/messages/retry")
def post_topic_retry(topic_id: uuid.UUID):
    try:
        events = retry_topic_message(topic_id)
    except NothingToRetryError as e:
        raise HTTPException(
            status_code=409, detail="There is no unanswered message"
        ) from e

    if events is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    return _stream_chat(events)


@app.get("/topics/{topic_id}/tasks", response_model=list[TaskOut])
def read_tasks(topic_id: uuid.UUID):
    if not topic_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")

    return get_tasks(topic_id)


@app.post("/topics/{topic_id}/tasks", response_model=list[TaskOut])
def post_tasks(topic_id: uuid.UUID):
    try:
        tasks = create_tasks(topic_id)
    except LessonMissingError as e:
        raise HTTPException(
            status_code=409, detail="The lesson has not been generated yet"
        ) from e
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if tasks is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    return tasks


@app.post("/tasks/{task_id}/attempts", status_code=201, response_model=AttemptOut)
def post_attempt(task_id: uuid.UUID, request: AttemptCreate):
    try:
        attempt = submit_attempt(task_id, request.answer)
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if attempt is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return attempt


@app.post("/attempts/{attempt_id}/grade", response_model=AttemptOut)
def post_grade(attempt_id: int):
    try:
        attempt = grade_attempt(attempt_id)
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")

    return attempt


@app.get("/courses/{course_id}/messages", response_model=list[ChatMessageOut])
def read_course_messages(course_id: uuid.UUID):
    if not course_exists(course_id):
        raise HTTPException(status_code=404, detail="Course not found")

    return list_course_messages(course_id)


@app.post("/courses/{course_id}/messages", status_code=201)
def post_course_message(course_id: uuid.UUID, request: MessageCreate):
    events = send_course_message(course_id, request.content, request.file_uuids)
    if events is None:
        raise HTTPException(status_code=404, detail="Course not found")

    return _stream_chat(events, status_code=201)


@app.post("/courses/{course_id}/messages/retry")
def post_course_retry(course_id: uuid.UUID):
    try:
        events = retry_course_message(course_id)
    except NothingToRetryError as e:
        raise HTTPException(
            status_code=409, detail="There is no unanswered message"
        ) from e

    if events is None:
        raise HTTPException(status_code=404, detail="Course not found")

    return _stream_chat(events)


@app.get("/courses/{course_id}/topic-deletions", response_model=list[TopicDeletionOut])
def read_topic_deletions(course_id: uuid.UUID):
    if not course_exists(course_id):
        raise HTTPException(status_code=404, detail="Course not found")

    return list_topic_deletions(course_id)


@app.post("/topic-deletions/{deletion_id}/confirm", response_model=ChatMessageOut)
def post_confirm_topic_deletion(deletion_id: uuid.UUID):
    result = confirm_topic_deletion(deletion_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Deletion proposal not found")

    course_id, title = result
    return add_course_note(course_id, f"[Deleted topic: {title}]")


@app.post("/topic-deletions/{deletion_id}/cancel", response_model=ChatMessageOut)
def post_cancel_topic_deletion(deletion_id: uuid.UUID):
    result = cancel_topic_deletion(deletion_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Deletion proposal not found")

    course_id, title = result
    return add_course_note(course_id, f"[Cancelled deletion of topic: {title}]")


@app.get("/courses/{course_id}/rebuild", response_model=CourseRebuildOut | None)
def read_course_rebuild(course_id: uuid.UUID):
    if not course_exists(course_id):
        raise HTTPException(status_code=404, detail="Course not found")

    return get_course_rebuild(course_id)


@app.post("/course-rebuilds/{rebuild_id}/apply", response_model=ChatMessageOut)
def post_apply_course_rebuild(rebuild_id: uuid.UUID):
    result = apply_course_rebuild(rebuild_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Course rebuild not found")

    return add_course_note(
        result.course_id,
        f"[Rebuilt course: kept {result.kept}, added {result.added}, "
        f"deleted {result.deleted} topics]",
    )


@app.post("/course-rebuilds/{rebuild_id}/discard", response_model=ChatMessageOut)
def post_discard_course_rebuild(rebuild_id: uuid.UUID):
    course_id = discard_course_rebuild(rebuild_id)
    if course_id is None:
        raise HTTPException(status_code=404, detail="Course rebuild not found")

    return add_course_note(course_id, "[Discarded course rebuild]")


@app.get(
    "/topics/{topic_id}/regenerations", response_model=list[PendingRegenerationOut]
)
def read_regenerations(topic_id: uuid.UUID):
    if not topic_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")

    return list_regenerations(topic_id)


@app.post("/regenerations/{regeneration_id}/confirm", response_model=ChatMessageOut)
def post_confirm_regeneration(regeneration_id: uuid.UUID):
    try:
        proposal = confirm_regeneration(regeneration_id)
    except LessonMissingError as e:
        raise HTTPException(
            status_code=409, detail="The lesson has not been generated yet"
        ) from e
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if proposal is None:
        raise HTTPException(status_code=404, detail="Regeneration not found")

    note = add_topic_note(proposal.topic_id, f"[Regenerated {proposal.kind}]")
    if note is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return note


@app.post("/regenerations/{regeneration_id}/cancel", response_model=ChatMessageOut)
def post_cancel_regeneration(regeneration_id: uuid.UUID):
    proposal = cancel_regeneration(regeneration_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Regeneration not found")

    note = add_topic_note(
        proposal.topic_id, f"[Cancelled {proposal.kind} regeneration]"
    )
    if note is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return note
