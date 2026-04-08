"""Service for class posts, comments, reactions, and mention tracking."""
from __future__ import annotations

import re
import uuid
from collections import Counter
from typing import Any, Iterable

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.class_member import ClassMember
from app.models.class_model import Class
from app.models.class_post import ClassPost
from app.models.comment_document_mention import CommentDocumentMention
from app.models.comment_member_mention import CommentMemberMention
from app.models.document import Document
from app.models.post_attachment import PostAttachment
from app.models.post_comment import PostComment
from app.models.post_document_mention import PostDocumentMention
from app.models.post_member_mention import PostMemberMention
from app.models.post_reaction import PostReaction
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user import User
from app.core.config import settings


DOC_BRACE_PATTERN = re.compile(r"@doc\{([^}]+)\}", re.IGNORECASE)
DOC_COLON_PATTERN = re.compile(r"@doc:([A-Za-z0-9\-]{4,})", re.IGNORECASE)
MEMBER_BRACE_PATTERN = re.compile(r"@sv\{([^}]+)\}", re.IGNORECASE)
MEMBER_COLON_PATTERN = re.compile(r"@sv:([A-Za-z0-9_.\-]{3,50})", re.IGNORECASE)


class ClassPostService:
    """Business logic for class posts and interactions."""

    @staticmethod
    def _build_student_profile(student: Student | None) -> dict[str, Any] | None:
        if not student:
            return None
        user = student.user
        return {
            "role": "student",
            "id": student.id,
            "fullName": user.full_name if user else None,
            "email": user.email if user else None,
            "avatarUrl": user.avatar_url if user else None,
            "studentCode": student.student_code,
            "department": student.department.name if student.department else None,
            "academicYear": student.academic_year,
        }

    @staticmethod
    def _build_teacher_profile(teacher: Teacher | None) -> dict[str, Any] | None:
        if not teacher:
            return None
        user = teacher.user
        return {
            "role": "teacher",
            "id": teacher.id,
            "fullName": user.full_name if user else None,
            "email": user.email if user else None,
            "avatarUrl": user.avatar_url if user else None,
            "department": teacher.department.name if teacher.department else None,
            "specialization": teacher.specialization.name if teacher.specialization else None,
        }

    @staticmethod
    def _resolve_document_file_url(document_id: uuid.UUID | None, file_url: str | None) -> str | None:
        """Return a stable backend endpoint for document content."""
        if document_id:
            return f"{settings.BACKEND_BASE_URL}{settings.API_V1_STR}/files/documents/{document_id}/content"
        return file_url

    @staticmethod
    def _resolve_actor_for_post_interaction(db: Session, user: User, class_id: int) -> tuple[str, int]:
        """Resolve actor role/id for class post interaction permissions."""
        if user.role == "teacher":
            teacher = ClassPostService._get_teacher_by_user(db, user)
            ClassPostService._ensure_teacher_owns_class(db, teacher.id, class_id)
            return "teacher", teacher.id

        if user.role == "student":
            student = ClassPostService._get_student_by_user(db, user)
            ClassPostService._ensure_student_in_class(db, student.id, class_id)
            return "student", student.id

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teachers or students can interact")

    @staticmethod
    def _get_teacher_by_user(db: Session, user: User) -> Teacher:
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teachers can perform this action")
        return teacher

    @staticmethod
    def _get_student_by_user(db: Session, user: User) -> Student:
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can perform this action")
        return student

    @staticmethod
    def _ensure_teacher_owns_class(db: Session, teacher_id: int, class_id: int) -> Class:
        class_obj = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher_id).first()
        if not class_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found or no permission")
        return class_obj

    @staticmethod
    def _ensure_student_in_class(db: Session, student_id: int, class_id: int) -> None:
        member = db.query(ClassMember).filter(ClassMember.class_id == class_id, ClassMember.student_id == student_id).first()
        if not member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this class")

    @staticmethod
    def _ensure_user_can_view_class(db: Session, user: User, class_id: int) -> None:
        if user.role == "teacher":
            teacher = ClassPostService._get_teacher_by_user(db, user)
            ClassPostService._ensure_teacher_owns_class(db, teacher.id, class_id)
            return
        if user.role == "student":
            student = ClassPostService._get_student_by_user(db, user)
            ClassPostService._ensure_student_in_class(db, student.id, class_id)
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teachers or students can access class posts")

    @staticmethod
    def _load_documents_by_ids(db: Session, document_ids: Iterable[uuid.UUID]) -> list[Document]:
        ids = list(set(document_ids))
        if not ids:
            return []
        documents = db.query(Document).filter(Document.id.in_(ids)).all()
        if len(documents) != len(ids):
            found_ids = {doc.id for doc in documents}
            missing_ids = [str(doc_id) for doc_id in ids if doc_id not in found_ids]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Documents not found: {', '.join(missing_ids)}",
            )
        return documents

    @staticmethod
    def _extract_document_tokens(content: str) -> set[str]:
        tokens = set()
        for item in DOC_BRACE_PATTERN.findall(content or ""):
            token = item.strip()
            if token:
                tokens.add(token)
        for item in DOC_COLON_PATTERN.findall(content or ""):
            token = item.strip()
            if token:
                tokens.add(token)
        return tokens

    @staticmethod
    def _extract_member_tokens(content: str) -> set[str]:
        tokens = set()
        for item in MEMBER_BRACE_PATTERN.findall(content or ""):
            token = item.strip()
            if token:
                tokens.add(token)
        for item in MEMBER_COLON_PATTERN.findall(content or ""):
            token = item.strip()
            if token:
                tokens.add(token)
        return tokens

    @staticmethod
    def _find_document_for_token(db: Session, token: str) -> Document | None:
        value = token.strip()
        if not value:
            return None
        try:
            token_uuid = uuid.UUID(value)
            return db.query(Document).filter(Document.id == token_uuid).first()
        except ValueError:
            pass
        return db.query(Document).filter(func.lower(Document.title) == value.lower()).first()

    @staticmethod
    def _find_member_for_token(db: Session, class_id: int, token: str) -> tuple[Student, str] | None:
        value = token.strip()
        if not value:
            return None
        row = (
            db.query(Student, User.full_name)
            .join(ClassMember, ClassMember.student_id == Student.id)
            .join(User, User.id == Student.user_id)
            .filter(ClassMember.class_id == class_id)
            .filter(
                (func.lower(Student.student_code) == value.lower())
                | (func.lower(User.full_name) == value.lower())
            )
            .first()
        )
        if not row:
            return None
        return row[0], row[1]

    @staticmethod
    def _replace_post_mentions(db: Session, post: ClassPost) -> None:
        db.query(PostDocumentMention).filter(PostDocumentMention.post_id == post.id).delete(synchronize_session=False)
        db.query(PostMemberMention).filter(PostMemberMention.post_id == post.id).delete(synchronize_session=False)

        document_tokens = ClassPostService._extract_document_tokens(post.content)
        member_tokens = ClassPostService._extract_member_tokens(post.content)

        seen_documents: set[uuid.UUID] = set()
        for token in document_tokens:
            doc = ClassPostService._find_document_for_token(db, token)
            if not doc or doc.id in seen_documents:
                continue
            seen_documents.add(doc.id)
            db.add(
                PostDocumentMention(
                    post_id=post.id,
                    document_id=doc.id,
                    document_title=doc.title,
                )
            )

        seen_students: set[int] = set()
        for token in member_tokens:
            member = ClassPostService._find_member_for_token(db, post.class_id, token)
            if not member:
                continue
            student, full_name = member
            if student.id in seen_students:
                continue
            seen_students.add(student.id)
            db.add(
                PostMemberMention(
                    post_id=post.id,
                    student_id=student.id,
                    mentioned_name=full_name,
                )
            )

    @staticmethod
    def _replace_comment_mentions(db: Session, comment: PostComment, class_id: int) -> None:
        db.query(CommentDocumentMention).filter(CommentDocumentMention.comment_id == comment.id).delete(synchronize_session=False)
        db.query(CommentMemberMention).filter(CommentMemberMention.comment_id == comment.id).delete(synchronize_session=False)

        document_tokens = ClassPostService._extract_document_tokens(comment.content)
        member_tokens = ClassPostService._extract_member_tokens(comment.content)

        seen_documents: set[uuid.UUID] = set()
        for token in document_tokens:
            doc = ClassPostService._find_document_for_token(db, token)
            if not doc or doc.id in seen_documents:
                continue
            seen_documents.add(doc.id)
            db.add(
                CommentDocumentMention(
                    comment_id=comment.id,
                    document_id=doc.id,
                    document_title=doc.title,
                )
            )

        seen_students: set[int] = set()
        for token in member_tokens:
            member = ClassPostService._find_member_for_token(db, class_id, token)
            if not member:
                continue
            student, full_name = member
            if student.id in seen_students:
                continue
            seen_students.add(student.id)
            db.add(
                CommentMemberMention(
                    comment_id=comment.id,
                    student_id=student.id,
                    mentioned_name=full_name,
                )
            )

    @staticmethod
    def _serialize_comment(db: Session, comment: PostComment) -> dict[str, Any]:
        author_name: str | None = None
        author_role: str | None = None
        author_id: int | None = None
        author_profile: dict[str, Any] | None = None

        if comment.student_id is not None:
            student = db.query(Student).filter(Student.id == comment.student_id).first()
            user = db.query(User).filter(User.id == student.user_id).first() if student else None
            author_name = user.full_name if user else None
            author_role = "student"
            author_id = comment.student_id
            if student and not student.user:
                student.user = user
            author_profile = ClassPostService._build_student_profile(student)
        elif comment.teacher_id is not None:
            teacher = db.query(Teacher).filter(Teacher.id == comment.teacher_id).first()
            user = db.query(User).filter(User.id == teacher.user_id).first() if teacher else None
            author_name = user.full_name if user else None
            author_role = "teacher"
            author_id = comment.teacher_id
            if teacher and not teacher.user:
                teacher.user = user
            author_profile = ClassPostService._build_teacher_profile(teacher)

        replies = (
            db.query(PostComment)
            .filter(PostComment.parent_comment_id == comment.id)
            .order_by(PostComment.created_at.asc())
            .all()
        )

        return {
            "id": comment.id,
            "postId": comment.post_id,
            "studentId": comment.student_id,
            "teacherId": comment.teacher_id,
            "authorId": author_id,
            "authorRole": author_role,
            "studentName": author_name,
            "authorProfile": author_profile,
            "content": comment.content,
            "parentCommentId": comment.parent_comment_id,
            "createdAt": comment.created_at.isoformat(),
            "documentMentions": [
                {
                    "documentId": str(item.document_id),
                    "documentTitle": item.document_title,
                }
                for item in comment.document_mentions
            ],
            "memberMentions": [
                {
                    "studentId": item.student_id,
                    "mentionedName": item.mentioned_name,
                }
                for item in comment.member_mentions
            ],
            "replies": [ClassPostService._serialize_comment(db, reply) for reply in replies],
        }

    @staticmethod
    def _serialize_post(db: Session, post: ClassPost, current_user: User | None = None, include_comments: bool = True) -> dict[str, Any]:
        teacher = db.query(Teacher).filter(Teacher.id == post.teacher_id).first()
        teacher_user = db.query(User).filter(User.id == teacher.user_id).first() if teacher else None
        if teacher and not teacher.user:
            teacher.user = teacher_user

        post_reactions = db.query(PostReaction).filter(PostReaction.post_id == post.id).all()
        reaction_summary = dict(Counter(item.emoji for item in post_reactions))

        current_reaction = None
        if current_user:
            if current_user.role == "student":
                current_student = db.query(Student).filter(Student.user_id == current_user.id).first()
                if current_student:
                    current_reaction_obj = (
                        db.query(PostReaction)
                        .filter(PostReaction.post_id == post.id, PostReaction.student_id == current_student.id)
                        .first()
                    )
                    current_reaction = current_reaction_obj.emoji if current_reaction_obj else None
            elif current_user.role == "teacher":
                current_teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
                if current_teacher:
                    current_reaction_obj = (
                        db.query(PostReaction)
                        .filter(PostReaction.post_id == post.id, PostReaction.teacher_id == current_teacher.id)
                        .first()
                    )
                    current_reaction = current_reaction_obj.emoji if current_reaction_obj else None

        comments_payload: list[dict[str, Any]] = []
        if include_comments:
            top_comments = (
                db.query(PostComment)
                .filter(PostComment.post_id == post.id, PostComment.parent_comment_id.is_(None))
                .order_by(PostComment.created_at.asc())
                .all()
            )
            comments_payload = [ClassPostService._serialize_comment(db, comment) for comment in top_comments]

        return {
            "id": post.id,
            "classId": post.class_id,
            "teacherId": post.teacher_id,
            "teacherName": teacher_user.full_name if teacher_user else None,
            "teacherProfile": ClassPostService._build_teacher_profile(teacher),
            "content": post.content,
            "createdAt": post.created_at.isoformat(),
            "attachments": [
                {
                    "documentId": str(item.document_id),
                    "title": item.document.title if item.document else None,
                    "fileUrl": ClassPostService._resolve_document_file_url(item.document_id, item.document.file_url) if item.document else None,
                }
                for item in post.attachments
            ],
            "documentMentions": [
                {
                    "documentId": str(item.document_id),
                    "documentTitle": item.document_title,
                }
                for item in post.document_mentions
            ],
            "memberMentions": [
                {
                    "studentId": item.student_id,
                    "mentionedName": item.mentioned_name,
                }
                for item in post.member_mentions
            ],
            "reactions": {
                "total": len(post_reactions),
                "byEmoji": reaction_summary,
                "myReaction": current_reaction,
            },
            "comments": comments_payload,
        }

    @staticmethod
    async def create_post(
        db: Session,
        current_user: User,
        class_id: int,
        content: str,
        attachment_document_ids: list[uuid.UUID],
    ) -> dict[str, Any]:
        teacher = ClassPostService._get_teacher_by_user(db, current_user)
        ClassPostService._ensure_teacher_owns_class(db, teacher.id, class_id)

        post = ClassPost(class_id=class_id, teacher_id=teacher.id, content=content)
        db.add(post)
        db.flush()

        documents = ClassPostService._load_documents_by_ids(db, attachment_document_ids)
        for doc in documents:
            db.add(PostAttachment(post_id=post.id, document_id=doc.id))

        ClassPostService._replace_post_mentions(db, post)

        db.commit()
        db.refresh(post)
        return {
            "success": True,
            "data": {"post": ClassPostService._serialize_post(db, post, current_user=current_user)},
            "message": "Post created successfully",
        }

    @staticmethod
    async def update_post(
        db: Session,
        current_user: User,
        post_id: int,
        content: str | None,
        attachment_document_ids: list[uuid.UUID] | None,
    ) -> dict[str, Any]:
        teacher = ClassPostService._get_teacher_by_user(db, current_user)
        post = db.query(ClassPost).filter(ClassPost.id == post_id).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

        ClassPostService._ensure_teacher_owns_class(db, teacher.id, post.class_id)

        if content is not None:
            post.content = content
            ClassPostService._replace_post_mentions(db, post)

        if attachment_document_ids is not None:
            db.query(PostAttachment).filter(PostAttachment.post_id == post.id).delete(synchronize_session=False)
            documents = ClassPostService._load_documents_by_ids(db, attachment_document_ids)
            for doc in documents:
                db.add(PostAttachment(post_id=post.id, document_id=doc.id))

        db.commit()
        db.refresh(post)
        return {
            "success": True,
            "data": {"post": ClassPostService._serialize_post(db, post, current_user=current_user)},
            "message": "Post updated successfully",
        }

    @staticmethod
    async def delete_post(db: Session, current_user: User, post_id: int) -> dict[str, Any]:
        teacher = ClassPostService._get_teacher_by_user(db, current_user)
        post = db.query(ClassPost).filter(ClassPost.id == post_id).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

        ClassPostService._ensure_teacher_owns_class(db, teacher.id, post.class_id)
        db.delete(post)
        db.commit()
        return {"success": True, "message": "Post deleted successfully"}

    @staticmethod
    async def list_class_posts(
        db: Session,
        current_user: User,
        class_id: int,
        include_comments: bool,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        ClassPostService._ensure_user_can_view_class(db, current_user, class_id)

        query = db.query(ClassPost).filter(ClassPost.class_id == class_id)
        total = query.count()
        posts = query.order_by(ClassPost.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "success": True,
            "data": {
                "items": [
                    ClassPostService._serialize_post(db, post, current_user=current_user, include_comments=include_comments)
                    for post in posts
                ],
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        }

    @staticmethod
    async def get_post_by_id(
        db: Session,
        current_user: User,
        post_id: int,
        include_comments: bool = True,
    ) -> dict[str, Any]:
        post = db.query(ClassPost).filter(ClassPost.id == post_id).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

        ClassPostService._ensure_user_can_view_class(db, current_user, post.class_id)

        return {
            "success": True,
            "data": {
                "post": ClassPostService._serialize_post(
                    db,
                    post,
                    current_user=current_user,
                    include_comments=include_comments,
                )
            },
        }

    @staticmethod
    async def create_comment(
        db: Session,
        current_user: User,
        post_id: int,
        content: str,
        parent_comment_id: int | None,
    ) -> dict[str, Any]:
        post = db.query(ClassPost).filter(ClassPost.id == post_id).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

        actor_role, actor_id = ClassPostService._resolve_actor_for_post_interaction(db, current_user, post.class_id)

        if parent_comment_id is not None:
            parent = db.query(PostComment).filter(PostComment.id == parent_comment_id).first()
            if not parent or parent.post_id != post.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid parent comment")

        comment = PostComment(
            post_id=post.id,
            student_id=actor_id if actor_role == "student" else None,
            teacher_id=actor_id if actor_role == "teacher" else None,
            content=content,
            parent_comment_id=parent_comment_id,
        )
        db.add(comment)
        db.flush()

        ClassPostService._replace_comment_mentions(db, comment, class_id=post.class_id)

        db.commit()
        db.refresh(comment)

        return {
            "success": True,
            "data": {"comment": ClassPostService._serialize_comment(db, comment)},
            "message": "Comment created successfully",
        }

    @staticmethod
    async def react_to_post(db: Session, current_user: User, post_id: int, emoji: str) -> dict[str, Any]:
        post = db.query(ClassPost).filter(ClassPost.id == post_id).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

        actor_role, actor_id = ClassPostService._resolve_actor_for_post_interaction(db, current_user, post.class_id)

        if actor_role == "teacher":
            reaction = db.query(PostReaction).filter(PostReaction.post_id == post.id, PostReaction.teacher_id == actor_id).first()
        else:
            reaction = db.query(PostReaction).filter(PostReaction.post_id == post.id, PostReaction.student_id == actor_id).first()

        if reaction:
            reaction.emoji = emoji
        else:
            reaction = PostReaction(
                post_id=post.id,
                student_id=actor_id if actor_role == "student" else None,
                teacher_id=actor_id if actor_role == "teacher" else None,
                emoji=emoji,
            )
            db.add(reaction)

        db.commit()

        post_reactions = db.query(PostReaction).filter(PostReaction.post_id == post.id).all()
        return {
            "success": True,
            "data": {
                "postId": post.id,
                "myReaction": emoji,
                "reactionSummary": dict(Counter(item.emoji for item in post_reactions)),
                "total": len(post_reactions),
            },
            "message": "Reaction updated successfully",
        }

    @staticmethod
    async def remove_reaction(db: Session, current_user: User, post_id: int) -> dict[str, Any]:
        post = db.query(ClassPost).filter(ClassPost.id == post_id).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

        actor_role, actor_id = ClassPostService._resolve_actor_for_post_interaction(db, current_user, post.class_id)

        if actor_role == "teacher":
            reaction = db.query(PostReaction).filter(PostReaction.post_id == post.id, PostReaction.teacher_id == actor_id).first()
        else:
            reaction = db.query(PostReaction).filter(PostReaction.post_id == post.id, PostReaction.student_id == actor_id).first()

        if reaction:
            db.delete(reaction)
            db.commit()
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reaction not found")

        post_reactions = db.query(PostReaction).filter(PostReaction.post_id == post.id).all()
        return {
            "success": True,
            "data": {
                "postId": post.id,
                "reactionSummary": dict(Counter(item.emoji for item in post_reactions)),
                "total": len(post_reactions),
            },
            "message": "Reaction removed successfully",
        }
