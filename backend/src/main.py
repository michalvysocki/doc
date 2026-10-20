import io
import os
import tempfile
import uuid

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from llama_index.core import SimpleDirectoryReader
from markitdown import MarkItDown

from .courses import (
    create_explanation,
    delete_course,
    get_course,
    get_topic,
    list_courses,
    save_course,
)
from .openrouter import OpenRouterError, generate_topic_map, send_query
from .schemas import (
    CourseCreate,
    CourseOut,
    CourseSummary,
    RequestContent,
    TopicDetail,
)
from .vectorstore import (
    add_document,
    delete_document,
    get_filenames,
    retrieve_chunks,
)

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


@app.post("/query")
def query(request_content: RequestContent):
    messages_list = [msg.model_dump() for msg in request_content.messages]

    if not messages_list:
        raise HTTPException(status_code=400, detail="Brak wiadomości w zapytaniu")

    file_uuids = request_content.file_uuids

    if file_uuids:
        last_message = messages_list[-1]
        last_user_text = ""

        if isinstance(last_message["content"], str):
            last_user_text = last_message["content"]

        elif isinstance(last_message["content"], list):
            for block in last_message["content"]:
                if block.get("type") == "text":
                    last_user_text = block.get("text", "")
                    break

        try:
            found_chunks = retrieve_chunks(query=last_user_text, file_uuids=file_uuids)
        except OpenRouterError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
        filenames = get_filenames(file_uuids)

        attached_list = "\n".join(f"- {name}" for name in filenames)

        context_texts = []
        for chunk in found_chunks:
            filename = chunk["metadata"].get("filename", "Unknown document")
            context_texts.append(
                f"--- Fragment of the document: {filename} ---\n{chunk['text']}"
            )
        full_context = "\n\n".join(context_texts)

        system_prompt = (
            "You are an AI assistant and teacher. The user attached the following "
            f"documents to this conversation:\n{attached_list}\n\n"
            "Answer the user's questions based on the document fragments below. "
            "If the answer is not in the documents, say so directly and answer "
            "using your general knowledge.\n\n"
            f"DOCUMENT FRAGMENTS:\n{full_context}"
        )

        messages_list.insert(0, {"role": "system", "content": system_prompt})

    try:
        result = send_query(messages_list)
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return result


@app.post("/parse_file")
def parse_file(file: UploadFile):
    if file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Image uploading is not supported")

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
        file_uuid = add_document(text_content, file.filename)
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
def post_topic_explanation(topic_id: uuid.UUID):
    try:
        topic = create_explanation(topic_id)
    except OpenRouterError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    return topic
