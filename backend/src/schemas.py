import uuid
from datetime import datetime
from typing import Annotated, Any

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
