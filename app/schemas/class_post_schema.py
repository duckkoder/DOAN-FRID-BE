"""Schemas for class posts, comments, reactions and mentions."""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CreateClassPostRequest(BaseModel):
    """Request payload for creating a class post."""

    content: str = Field(..., min_length=1, description="Post content")
    attachment_document_ids: list[UUID] = Field(default_factory=list, description="Document ids attached to the post")


class UpdateClassPostRequest(BaseModel):
    """Request payload for updating a class post."""

    content: Optional[str] = Field(None, min_length=1, description="Updated post content")
    attachment_document_ids: Optional[list[UUID]] = Field(
        default=None,
        description="Replace attachment document ids when provided",
    )

    @model_validator(mode="after")
    def validate_at_least_one_field(self):
        if self.content is None and self.attachment_document_ids is None:
            raise ValueError("At least one of content or attachment_document_ids must be provided")
        return self


class CreatePostCommentRequest(BaseModel):
    """Request payload for creating a post comment or reply."""

    content: str = Field(..., min_length=1, description="Comment content")
    parent_comment_id: Optional[int] = Field(None, ge=1, description="Parent comment id for replies")


class ReactPostRequest(BaseModel):
    """Request payload for reacting to a post."""

    emoji: str = Field(..., min_length=1, max_length=32, description="Emoji reaction value")


class ClassPostListQuery(BaseModel):
    """Query object for class post listing."""

    include_comments: bool = True
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
