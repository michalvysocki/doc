import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class Message(BaseModel):
    role: str
    content: str | list[dict[str, Any]]


class RequestContent(BaseModel):
    messages: list[Message]
    file_uuids: list[uuid.UUID] = []


class TopicNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Short topic name")
    description: str = Field(
        description="One or two sentences about what the topic covers"
    )
    children: list["TopicNode"] = Field(
        description="Subtopics; empty list for leaf topics"
    )


class TopicMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_title: str = Field(description="Title of the whole course")
    topics: list[TopicNode] = Field(description="Top-level topics")


class CourseCreate(BaseModel):
    initial_prompt: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]


class TopicOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    has_explanation: bool
    children: list["TopicOut"]


class CourseOut(BaseModel):
    id: uuid.UUID
    title: str
    initial_prompt: str
    created_at: datetime
    topics: list[TopicOut]


class CourseSummary(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime


class TopicLink(BaseModel):
    id: uuid.UUID
    title: str


class TopicDetail(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    course_title: str
    path: list[TopicLink]
    title: str
    description: str
    explanation: str | None
    subtopics: list[TopicLink]


class AttachmentOut(BaseModel):
    file_uuid: uuid.UUID
    filename: str


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    attachments: list[AttachmentOut]


class ImageIn(BaseModel):
    filename: str
    data: str


class TopicMessageCreate(BaseModel):
    content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)
    ]
    file_uuids: list[uuid.UUID] = []
    images: list[ImageIn] = []


class TopicChatReply(BaseModel):
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut


class GeneratedTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        description="An open question or practical exercise for the learner"
    )
    grading_notes: str = Field(
        description="Key points a correct answer must contain; never shown to the learner"
    )


class GeneratedTaskSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[GeneratedTask] = Field(description="Tasks from easier to harder")


class AttemptOut(BaseModel):
    id: int
    answer: str
    verdict: str | None
    feedback: str | None
    created_at: datetime


class TaskOut(BaseModel):
    id: uuid.UUID
    position: int
    question: str
    attempts: list[AttemptOut]


class TaskGrade(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["correct", "partially_correct", "incorrect"] = Field(
        description="Overall assessment of the answer"
    )
    feedback: str = Field(
        description="What is right, what is missing or wrong, and a hint how to improve"
    )


class AttemptCreate(BaseModel):
    answer: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)
    ]
