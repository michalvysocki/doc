import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


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
