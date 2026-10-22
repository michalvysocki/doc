import io
import os
import tempfile
import uuid
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from llama_index.core import SimpleDirectoryReader
from markitdown import MarkItDown

from .chat import (
    add_course_note,
    add_topic_note,
    list_course_messages,
    list_topic_messages,
    send_course_message,
    send_topic_message,
)
from .course_rebuilds import (
    RebuildError,
    apply_course_rebuild,
    discard_course_rebuild,
    get_course_rebuild,
    propose_course_rebuild,
)
from .courses import (
    course_exists,
    create_explanation,
    delete_course,
    get_course,
    get_topic,
    list_courses,
    save_course,
    topic_exists,
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
    ChatReply,
    CourseCreate,
    CourseOut,
    CourseRebuildOut,
    CourseSummary,
    GenerationOptions,
    MessageCreate,
    PendingRegenerationOut,
    TaskOut,
    TopicDeletionOut,
    TopicDetail,
)
from .tasks import (
    LessonMissingError,
    create_tasks,
    get_tasks,
    grade_attempt,
    submit_attempt,
)
from .topic_deletions import (
    cancel_topic_deletion,
    confirm_topic_deletion,
    list_topic_deletions,
)
from .vectorstore import add_document, delete_document

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

md = MarkItDown()


@app.post("/parse_file")
def parse_file(file: UploadFile, course_id: Annotated[uuid.UUID, Form()]):
    if file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Image uploading is not supported")

    if not course_exists(course_id):
        raise HTTPException(status_code=404, detail="Course not found")

    file_bytes = file.file.read()
    binary_stream = io.BytesIO(file_bytes)

    _, extension = os.path.splitext(file.filename)
    extension = extension.lower()

    text_content = ""

    try:
        if file.content_type == "application/pdf" or extension == ".pdf":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(file_bytes)
                tmp_path = tmp_file.name

            try:
                documents = SimpleDirectoryReader(input_files=[tmp_path]).load_data()

                text_content = "\n".join([doc.text for doc in documents])

            finally:
                os.remove(tmp_path)

        elif file.content_type.startswith(
            "application/vnd.openxmlformats-officedocument"
        ) or extension in [".docx", ".xlsx", ".pptx"]:
            result = md.convert_stream(binary_stream, file_extension=extension)
            text_content = result.text_content

        elif file.content_type.startswith("text/") or extension in [
            ".md",
            ".txt",
            ".html",
            ".csv",
            ".json",
        ]:
            text_content = file_bytes.decode()

        else:
            raise ValueError(f"Unsupported file extension: {extension}")

    except ValueError:
        raise HTTPException(status_code=400, detail="Wrong file type")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e!s}")

    if not text_content or text_content.strip() == "":
        raise HTTPException(
            status_code=400, detail="Empty file or no readable text found"
        )

    try:
        file_uuid = add_document(text_content, file.filename, course_id)
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return {"filename": file.filename, "file_uuid": file_uuid}


@app.delete("/delete_file/{file_uuid}", status_code=204)
def delete_file(file_uuid: uuid.UUID):
    if not delete_document(file_uuid):
        raise HTTPException(
            status_code=404, detail=f"File with UUID {file_uuid} was not found"
        )


@app.get("/courses", response_model=list[CourseSummary])
def read_courses():
    return list_courses()


@app.post("/courses", status_code=201, response_model=CourseOut)
def create_course(request: CourseCreate):
    try:
        topic_map = generate_topic_map(request.initial_prompt)
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    course_id = save_course(request.initial_prompt, topic_map)

    return get_course(course_id)


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
def post_topic_explanation(
    topic_id: uuid.UUID,
    regenerate: bool = False,
    request: GenerationOptions | None = None,
):
    options = request or GenerationOptions()
    try:
        topic = create_explanation(
            topic_id, regenerate, options.instructions or None, options.use_files
        )
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


@app.post("/topics/{topic_id}/messages", status_code=201, response_model=ChatReply)
def post_topic_message(topic_id: uuid.UUID, request: MessageCreate):
    try:
        reply = send_topic_message(
            topic_id, request.content, request.file_uuids, request.images
        )
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if reply is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    return reply


@app.get("/topics/{topic_id}/tasks", response_model=list[TaskOut])
def read_tasks(topic_id: uuid.UUID):
    if not topic_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")

    return get_tasks(topic_id)


@app.post("/topics/{topic_id}/tasks", response_model=list[TaskOut])
def post_tasks(
    topic_id: uuid.UUID,
    regenerate: bool = False,
    request: GenerationOptions | None = None,
):
    options = request or GenerationOptions()
    try:
        tasks = create_tasks(
            topic_id, regenerate, options.instructions or None, options.use_files
        )
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


@app.post("/courses/{course_id}/messages", status_code=201, response_model=ChatReply)
def post_course_message(course_id: uuid.UUID, request: MessageCreate):
    try:
        reply = send_course_message(
            course_id, request.content, request.file_uuids, request.images
        )
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if reply is None:
        raise HTTPException(status_code=404, detail="Course not found")

    return reply


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


@app.post("/courses/{course_id}/rebuild", response_model=CourseRebuildOut)
def post_course_rebuild(course_id: uuid.UUID, request: GenerationOptions | None = None):
    options = request or GenerationOptions()
    try:
        rebuild_id = propose_course_rebuild(
            course_id, options.instructions or None, options.use_files
        )
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except RebuildError as e:
        raise HTTPException(
            status_code=502, detail=f"The generated plan cannot be used: {e}"
        ) from e

    if rebuild_id is None:
        raise HTTPException(status_code=404, detail="Course not found")

    return get_course_rebuild(course_id)


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
