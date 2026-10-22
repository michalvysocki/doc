import uuid
from datetime import datetime
from typing import Annotated, Literal

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


class RebuildTopicNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    existing_topic_id: str | None = Field(
        description=(
            "Id of the existing topic (from the outline) that this topic keeps, "
            "or null for a new topic"
        )
    )
    title: str = Field(description="Short topic name")
    description: str = Field(
        description="One or two sentences about what the topic covers"
    )
    children: list["RebuildTopicNode"] = Field(
        description="Subtopics; empty list for leaf topics"
    )


class RebuildPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: list[RebuildTopicNode] = Field(description="Top-level topics in order")


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
    tasks_total: int
    tasks_solved: int
    children: list["TopicOut"]


class CourseProgress(BaseModel):
    topics_total: int
    topics_completed: int


class CourseOut(BaseModel):
    id: uuid.UUID
    title: str
    initial_prompt: str
    created_at: datetime
    topics: list[TopicOut]
    progress: CourseProgress


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


class MessageCreate(BaseModel):
    content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)
    ]
    file_uuids: list[uuid.UUID] = []
    images: list[ImageIn] = []


class ChatReply(BaseModel):
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut
    course_changed: bool = False


class AddTopicsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_topic_id: str | None = Field(
        description="Id of the topic to add subtopics to; null for top-level topics"
    )
    after_topic_id: str | None = Field(
        description="Id of the sibling after which to insert; null to add at the end"
    )
    topics: list[TopicNode] = Field(description="Topics to add, may have subtopics")


class RenameTopicArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_id: str = Field(description="Id of the topic to rename, from the outline")
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ] = Field(description="New short topic name")
    description: str | None = Field(
        description="New description, or null to keep the current one"
    )


class MoveTopicArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_id: str = Field(description="Id of the topic to move, from the outline")
    parent_topic_id: str | None = Field(
        description="Id of the new parent topic; null to make it a top-level topic"
    )
    after_topic_id: str | None = Field(
        description=(
            'Id of the new sibling after which to place it; "first" to put it '
            "first; null to put it at the end"
        )
    )


class GenerationOptions(BaseModel):
    instructions: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    use_files: bool = False


class RebuildPreviewNode(BaseModel):
    topic_id: uuid.UUID | None  # None = new topic
    title: str
    description: str
    old_title: str | None  # set when a kept topic gets a new title
    has_explanation: bool
    tasks_total: int
    tasks_solved: int
    children: list["RebuildPreviewNode"]


class RebuildDeletedTopic(BaseModel):
    topic_id: uuid.UUID
    title: str
    has_explanation: bool
    tasks: int
    attempts: int


class CourseRebuildOut(BaseModel):
    id: uuid.UUID
    topics: list[RebuildPreviewNode]
    deleted: list[RebuildDeletedTopic]
    kept_count: int
    new_count: int


class ProposeCourseRebuildArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instructions: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = Field(description="What the learner wants changed, in their own words")
    use_files: bool = Field(
        description="True if the new map should be based on the uploaded course files"
    )


class TopicDeletionOut(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    topic_title: str
    subtopics: int
    lessons: int
    tasks: int
    attempts: int


class ProposeTopicDeletionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_id: str = Field(description="Id of the topic to delete, from the outline")


class AddSubtopicsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    after_topic_id: str | None = Field(
        description=(
            "Id of the existing subtopic after which to insert; null to add at the end"
        )
    )
    topics: list[TopicNode] = Field(
        description=(
            "Subtopics to add to the current lesson, may have their own subtopics"
        )
    )


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


MAX_TASKS_PER_TOOL_CALL = 5


class AddTasksArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tasks: list[GeneratedTask] = Field(
        min_length=1,
        max_length=MAX_TASKS_PER_TOOL_CALL,
        description="Tasks to add at the end of this lesson's task list",
    )


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
