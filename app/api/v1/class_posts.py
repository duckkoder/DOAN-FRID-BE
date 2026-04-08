"""Class post endpoints for posts, comments, reactions and mentions."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.class_post_schema import (
    CreateClassPostRequest,
    UpdateClassPostRequest,
    CreatePostCommentRequest,
    ReactPostRequest,
)
from app.services.class_post_service import ClassPostService


router = APIRouter(prefix="/class-posts", tags=["Class Posts"])


@router.post("/classes/{class_id}/posts", status_code=status.HTTP_201_CREATED)
async def create_class_post(
    class_id: int,
    payload: CreateClassPostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ClassPostService.create_post(
        db=db,
        current_user=current_user,
        class_id=class_id,
        content=payload.content,
        attachment_document_ids=payload.attachment_document_ids,
    )


@router.get("/classes/{class_id}/posts")
async def list_class_posts(
    class_id: int,
    include_comments: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ClassPostService.list_class_posts(
        db=db,
        current_user=current_user,
        class_id=class_id,
        include_comments=include_comments,
        limit=limit,
        offset=offset,
    )


@router.get("/posts/{post_id}")
async def get_post_by_id(
    post_id: int,
    include_comments: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ClassPostService.get_post_by_id(
        db=db,
        current_user=current_user,
        post_id=post_id,
        include_comments=include_comments,
    )


@router.patch("/posts/{post_id}")
async def update_post(
    post_id: int,
    payload: UpdateClassPostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ClassPostService.update_post(
        db=db,
        current_user=current_user,
        post_id=post_id,
        content=payload.content,
        attachment_document_ids=payload.attachment_document_ids,
    )


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ClassPostService.delete_post(db=db, current_user=current_user, post_id=post_id)


@router.post("/posts/{post_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_comment(
    post_id: int,
    payload: CreatePostCommentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ClassPostService.create_comment(
        db=db,
        current_user=current_user,
        post_id=post_id,
        content=payload.content,
        parent_comment_id=payload.parent_comment_id,
    )


@router.post("/posts/{post_id}/reactions")
async def react_to_post(
    post_id: int,
    payload: ReactPostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ClassPostService.react_to_post(
        db=db,
        current_user=current_user,
        post_id=post_id,
        emoji=payload.emoji,
    )


@router.delete("/posts/{post_id}/reactions")
async def remove_reaction(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ClassPostService.remove_reaction(db=db, current_user=current_user, post_id=post_id)
