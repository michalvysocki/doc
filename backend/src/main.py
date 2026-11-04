import json
import logging
import os
import queue
import threading
import uuid
from collections.abc import Callable, Iterator
from typing import Annotated, Any

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
)
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

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
    update_course_goal,
)
from .file_parsing import (
    FileParsingError,
    FileTooLargeError,
    prepare_upload,
    read_upload,
)
from .learner_settings import get_about, set_about
from .openrouter import OpenRouterError, StatusCallback, generate_topic_map
from .ownership import (
    attempt_owner,
    course_owner,
    course_rebuild_owner,
    document_owner,
    regeneration_owner,
    task_owner,
    topic_deletion_owner,
    topic_owner,
)
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
    CourseGoalUpdate,
    CourseOut,
    CourseRebuildOut,
    CourseSummary,
    Credentials,
    LearnerSettingsOut,
    LearnerSettingsUpdate,
    MessageCreate,
    PendingRegenerationOut,
    ReviewTaskOut,
    TaskOut,
    TopicDeletionOut,
    TopicDetail,
    UserOut,
)
from .tasks import (
    FollowUpError,
    LessonMissingError,
    create_follow_up,
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
from .users import (
    SESSION_DAYS,
    EmailTakenError,
    authenticate,
    create_user,
    end_session,
    normalize_email,
    session_user,
    start_session,
    user_email,
)
from .vectorstore import (
    DocumentTooLargeError,
    add_document,
    delete_document,
    get_image,
    list_course_files,
)

# Shows the app's own INFO logs (such as review results) next to uvicorn's.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SESSION_COOKIE = "doc_session"
# Over plain http in development the cookie cannot be Secure; set to "true" when deployed with https.
COOKIE_SECURE = os.getenv("COOKIE_SECURE") == "true"

app = FastAPI()

# Only the frontend may send requests with the login cookie.
origins = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
    )


def current_user(
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> uuid.UUID:
    user_id = session_user(token) if token else None
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user_id


CurrentUser = Annotated[uuid.UUID, Depends(current_user)]


def _require_owner(owner: uuid.UUID | None, user_id: uuid.UUID, what: str) -> None:
    # Someone else's resource looks the same as a missing one.
    if owner != user_id:
        raise HTTPException(status_code=404, detail=f"{what} not found")


def owned_course(course_id: uuid.UUID, user_id: CurrentUser) -> None:
    _require_owner(course_owner(course_id), user_id, "Course")


def owned_topic(topic_id: uuid.UUID, user_id: CurrentUser) -> None:
    _require_owner(topic_owner(topic_id), user_id, "Topic")


def owned_task(task_id: uuid.UUID, user_id: CurrentUser) -> None:
    _require_owner(task_owner(task_id), user_id, "Task")


def owned_attempt(attempt_id: int, user_id: CurrentUser) -> None:
    _require_owner(attempt_owner(attempt_id), user_id, "Attempt")


def owned_document(file_uuid: uuid.UUID, user_id: CurrentUser) -> None:
    _require_owner(document_owner(file_uuid), user_id, "File")


def owned_topic_deletion(deletion_id: uuid.UUID, user_id: CurrentUser) -> None:
    _require_owner(topic_deletion_owner(deletion_id), user_id, "Topic deletion")


def owned_course_rebuild(rebuild_id: uuid.UUID, user_id: CurrentUser) -> None:
    _require_owner(course_rebuild_owner(rebuild_id), user_id, "Course rebuild")


def owned_regeneration(regeneration_id: uuid.UUID, user_id: CurrentUser) -> None:
    _require_owner(regeneration_owner(regeneration_id), user_id, "Regeneration")


@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(credentials: Credentials, response: Response):
    try:
        user_id = create_user(credentials.email, credentials.password)
    except EmailTakenError as e:
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        ) from e
    _set_session_cookie(response, start_session(user_id))
    return UserOut(id=user_id, email=normalize_email(credentials.email))


@app.post("/auth/login", response_model=UserOut)
def login(credentials: Credentials, response: Response):
    user_id = authenticate(credentials.email, credentials.password)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Wrong email or password")
    _set_session_cookie(response, start_session(user_id))
    return UserOut(id=user_id, email=normalize_email(credentials.email))


@app.post("/auth/logout", status_code=204)
def logout(
    response: Response,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
):
    if token:
        end_session(token)
    response.delete_cookie(SESSION_COOKIE)


@app.get("/auth/me", response_model=UserOut)
def me(user_id: CurrentUser):
    return UserOut(id=user_id, email=user_email(user_id))


@app.post("/parse_file")
def parse_file(
    file: UploadFile, course_id: Annotated[uuid.UUID, Form()], user_id: CurrentUser
):
    # The course comes in the form, not the path, so it is checked here.
    _require_owner(course_owner(course_id), user_id, "Course")

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


@app.get("/files/{file_uuid}/content", dependencies=[Depends(owned_document)])
def read_file_content(file_uuid: uuid.UUID):
    image = get_image(file_uuid)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    content, media_type = image
    return Response(content=content, media_type=media_type)


@app.delete(
    "/delete_file/{file_uuid}", status_code=204, dependencies=[Depends(owned_document)]
)
def delete_file(file_uuid: uuid.UUID):
    if not delete_document(file_uuid):
        raise HTTPException(
            status_code=404, detail=f"File with UUID {file_uuid} was not found"
        )


@app.get("/courses", response_model=list[CourseSummary])
def read_courses(user_id: CurrentUser):
    return list_courses(user_id)


MAX_FILES_PER_COURSE = 10


@app.post("/courses", status_code=201)
def create_course(
    user_id: CurrentUser,
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

    # The files are read now: they are closed once the response starts streaming.
    uploads = []
    for file in files:
        try:
            uploads.append((file.filename, file.content_type, read_upload(file)))
        except FileParsingError as e:
            raise HTTPException(status_code=400, detail=f"{file.filename}: {e}") from e

    def work(on_status: StatusCallback) -> CourseOut:
        texts = []
        for number, (filename, content_type, data) in enumerate(uploads, start=1):
            on_status(f"Reading {filename} ({number}/{len(uploads)})…")
            try:
                parsed = prepare_upload(filename, content_type, data)
            except (FileParsingError, OpenRouterError) as e:
                raise type(e)(f"{filename}: {e}") from e
            texts.append((filename, parsed))

        if texts:
            course_id = create_course_with_files(
                user_id, request.initial_prompt, texts, on_status
            )
        else:
            topic_map, sources = generate_topic_map(
                request.initial_prompt, on_status=on_status, about=get_about()
            )
            course_id = save_course(user_id, request.initial_prompt, topic_map, sources)
        return get_course(course_id)

    return _stream_events(_run_with_status(work), status_code=201)


@app.get(
    "/courses/{course_id}/reviews",
    response_model=list[ReviewTaskOut],
    dependencies=[Depends(owned_course)],
)
def read_reviews(course_id: uuid.UUID):
    if not course_exists(course_id):
        raise HTTPException(status_code=404, detail="Course not found")

    return get_due_reviews(course_id)


@app.get(
    "/courses/{course_id}/files",
    response_model=list[CourseFileOut],
    dependencies=[Depends(owned_course)],
)
def read_course_files(course_id: uuid.UUID):
    if not course_exists(course_id):
        raise HTTPException(status_code=404, detail="Course not found")

    return list_course_files(course_id)


@app.get(
    "/learner-settings",
    response_model=LearnerSettingsOut,
    dependencies=[Depends(current_user)],
)
def read_learner_settings():
    return LearnerSettingsOut(about=get_about())


@app.put(
    "/learner-settings",
    response_model=LearnerSettingsOut,
    dependencies=[Depends(current_user)],
)
def put_learner_settings(request: LearnerSettingsUpdate):
    return LearnerSettingsOut(about=set_about(request.about))


@app.patch(
    "/courses/{course_id}",
    response_model=CourseOut,
    dependencies=[Depends(owned_course)],
)
def patch_course(course_id: uuid.UUID, request: CourseGoalUpdate):
    course = update_course_goal(course_id, request.initial_prompt)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@app.get(
    "/courses/{course_id}",
    response_model=CourseOut,
    dependencies=[Depends(owned_course)],
)
def read_course(course_id: uuid.UUID):
    course = get_course(course_id)

    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    return course


@app.delete(
    "/courses/{course_id}", status_code=204, dependencies=[Depends(owned_course)]
)
def remove_course(course_id: uuid.UUID):
    if not delete_course(course_id):
        raise HTTPException(status_code=404, detail="Course not found")


@app.get(
    "/topics/{topic_id}",
    response_model=TopicDetail,
    dependencies=[Depends(owned_topic)],
)
def read_topic(topic_id: uuid.UUID):
    topic = get_topic(topic_id)

    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    return topic


@app.post(
    "/topics/{topic_id}/explanation",
    response_model=TopicDetail,
    dependencies=[Depends(owned_topic)],
)
def post_topic_explanation(topic_id: uuid.UUID):
    try:
        topic = create_explanation(topic_id)
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    return topic


@app.get(
    "/topics/{topic_id}/messages",
    response_model=list[ChatMessageOut],
    dependencies=[Depends(owned_topic)],
)
def read_topic_messages(topic_id: uuid.UUID):
    if not topic_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")

    return list_topic_messages(topic_id)


def _event_line(event: ChatEvent) -> str:
    # jsonable_encoder turns the Pydantic models (ChatReply, ChatMessageOut),
    # dates and UUIDs inside an event into plain JSON values.
    return json.dumps(jsonable_encoder(event)) + "\n"


def _stream_events(
    events: Iterator[ChatEvent], status_code: int = 200
) -> StreamingResponse:
    """
    Sends events (of a chat answer or a course being created) as JSON lines
    (NDJSON). The status is already sent when the stream starts, so a failure on
    the way becomes a last "error" event.
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


def _run_with_status(work: Callable[[StatusCallback], Any]) -> Iterator[ChatEvent]:
    """
    Runs slow work in a thread and yields its status messages as events while
    it runs, then "done" with its result or "error".
    """

    events: queue.Queue[ChatEvent] = queue.Queue()

    def status(text: str) -> None:
        events.put({"type": "status", "text": text})

    def run() -> None:
        try:
            events.put({"type": "done", "course": work(status)})
        except (FileParsingError, DocumentTooLargeError, OpenRouterError) as e:
            events.put({"type": "error", "detail": str(e)})
        except Exception:
            logger.exception("Creating a course failed")
            events.put(
                {
                    "type": "error",
                    "detail": "Something went wrong while creating the course",
                }
            )

    threading.Thread(target=run, daemon=True).start()
    while True:
        event = events.get()
        yield event
        if event["type"] in ("done", "error"):
            return


@app.post(
    "/topics/{topic_id}/messages", status_code=201, dependencies=[Depends(owned_topic)]
)
def post_topic_message(topic_id: uuid.UUID, request: MessageCreate):
    events = send_topic_message(topic_id, request.content, request.file_uuids)
    if events is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    return _stream_events(events, status_code=201)


@app.post("/topics/{topic_id}/messages/retry", dependencies=[Depends(owned_topic)])
def post_topic_retry(topic_id: uuid.UUID):
    try:
        events = retry_topic_message(topic_id)
    except NothingToRetryError as e:
        raise HTTPException(
            status_code=409, detail="There is no unanswered message"
        ) from e

    if events is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    return _stream_events(events)


@app.get(
    "/topics/{topic_id}/tasks",
    response_model=list[TaskOut],
    dependencies=[Depends(owned_topic)],
)
def read_tasks(topic_id: uuid.UUID):
    if not topic_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")

    return get_tasks(topic_id)


@app.post(
    "/topics/{topic_id}/tasks",
    response_model=list[TaskOut],
    dependencies=[Depends(owned_topic)],
)
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


@app.post(
    "/tasks/{task_id}/attempts",
    status_code=201,
    response_model=AttemptOut,
    dependencies=[Depends(owned_task)],
)
def post_attempt(task_id: uuid.UUID, request: AttemptCreate):
    try:
        attempt = submit_attempt(task_id, request.answer)
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if attempt is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return attempt


@app.post(
    "/attempts/{attempt_id}/follow-up",
    status_code=201,
    response_model=TaskOut,
    dependencies=[Depends(owned_attempt)],
)
def post_follow_up(attempt_id: int):
    try:
        task = create_follow_up(attempt_id)
    except FollowUpError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except LessonMissingError as e:
        raise HTTPException(
            status_code=409, detail="The lesson has not been generated yet"
        ) from e
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if task is None:
        raise HTTPException(status_code=404, detail="Attempt not found")

    return task


@app.post(
    "/attempts/{attempt_id}/grade",
    response_model=AttemptOut,
    dependencies=[Depends(owned_attempt)],
)
def post_grade(attempt_id: int):
    try:
        attempt = grade_attempt(attempt_id)
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")

    return attempt


@app.get(
    "/courses/{course_id}/messages",
    response_model=list[ChatMessageOut],
    dependencies=[Depends(owned_course)],
)
def read_course_messages(course_id: uuid.UUID):
    if not course_exists(course_id):
        raise HTTPException(status_code=404, detail="Course not found")

    return list_course_messages(course_id)


@app.post(
    "/courses/{course_id}/messages",
    status_code=201,
    dependencies=[Depends(owned_course)],
)
def post_course_message(course_id: uuid.UUID, request: MessageCreate):
    events = send_course_message(course_id, request.content, request.file_uuids)
    if events is None:
        raise HTTPException(status_code=404, detail="Course not found")

    return _stream_events(events, status_code=201)


@app.post("/courses/{course_id}/messages/retry", dependencies=[Depends(owned_course)])
def post_course_retry(course_id: uuid.UUID):
    try:
        events = retry_course_message(course_id)
    except NothingToRetryError as e:
        raise HTTPException(
            status_code=409, detail="There is no unanswered message"
        ) from e

    if events is None:
        raise HTTPException(status_code=404, detail="Course not found")

    return _stream_events(events)


@app.get(
    "/courses/{course_id}/topic-deletions",
    response_model=list[TopicDeletionOut],
    dependencies=[Depends(owned_course)],
)
def read_topic_deletions(course_id: uuid.UUID):
    if not course_exists(course_id):
        raise HTTPException(status_code=404, detail="Course not found")

    return list_topic_deletions(course_id)


@app.post(
    "/topic-deletions/{deletion_id}/confirm",
    response_model=ChatMessageOut,
    dependencies=[Depends(owned_topic_deletion)],
)
def post_confirm_topic_deletion(deletion_id: uuid.UUID):
    result = confirm_topic_deletion(deletion_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Deletion proposal not found")

    course_id, title = result
    return add_course_note(course_id, f"[Deleted topic: {title}]")


@app.post(
    "/topic-deletions/{deletion_id}/cancel",
    response_model=ChatMessageOut,
    dependencies=[Depends(owned_topic_deletion)],
)
def post_cancel_topic_deletion(deletion_id: uuid.UUID):
    result = cancel_topic_deletion(deletion_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Deletion proposal not found")

    course_id, title = result
    return add_course_note(course_id, f"[Cancelled deletion of topic: {title}]")


@app.get(
    "/courses/{course_id}/rebuild",
    response_model=CourseRebuildOut | None,
    dependencies=[Depends(owned_course)],
)
def read_course_rebuild(course_id: uuid.UUID):
    if not course_exists(course_id):
        raise HTTPException(status_code=404, detail="Course not found")

    return get_course_rebuild(course_id)


@app.post(
    "/course-rebuilds/{rebuild_id}/apply",
    response_model=ChatMessageOut,
    dependencies=[Depends(owned_course_rebuild)],
)
def post_apply_course_rebuild(rebuild_id: uuid.UUID):
    try:
        result = apply_course_rebuild(rebuild_id)
    except SQLAlchemyError as e:
        logger.exception("Applying course rebuild %s failed", rebuild_id)
        raise HTTPException(
            status_code=500,
            detail="Could not apply the rebuild; the course was not changed",
        ) from e
    if result is None:
        raise HTTPException(status_code=404, detail="Course rebuild not found")

    return add_course_note(
        result.course_id,
        f"[Rebuilt course: kept {result.kept}, added {result.added}, "
        f"deleted {result.deleted} topics]",
    )


@app.post(
    "/course-rebuilds/{rebuild_id}/discard",
    response_model=ChatMessageOut,
    dependencies=[Depends(owned_course_rebuild)],
)
def post_discard_course_rebuild(rebuild_id: uuid.UUID):
    course_id = discard_course_rebuild(rebuild_id)
    if course_id is None:
        raise HTTPException(status_code=404, detail="Course rebuild not found")

    return add_course_note(course_id, "[Discarded course rebuild]")


@app.get(
    "/topics/{topic_id}/regenerations",
    response_model=list[PendingRegenerationOut],
    dependencies=[Depends(owned_topic)],
)
def read_regenerations(topic_id: uuid.UUID):
    if not topic_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")

    return list_regenerations(topic_id)


@app.post(
    "/regenerations/{regeneration_id}/confirm",
    response_model=ChatMessageOut,
    dependencies=[Depends(owned_regeneration)],
)
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


@app.post(
    "/regenerations/{regeneration_id}/cancel",
    response_model=ChatMessageOut,
    dependencies=[Depends(owned_regeneration)],
)
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
