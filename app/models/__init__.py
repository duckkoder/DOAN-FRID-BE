"""Models module for SQLAlchemy ORM entities."""
from app.models.base import Base, BaseModel

# Import all models for Alembic detection
from app.models.user import User
from app.models.admin import Admin
from app.models.department import Department
from app.models.specialization import Specialization
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.model_config import ModelConfig
from app.models.file import File
from app.models.class_post import ClassPost
from app.models.post_reaction import PostReaction
from app.models.post_comment import PostComment
from app.models.post_document_mention import PostDocumentMention
from app.models.post_member_mention import PostMemberMention
from app.models.comment_document_mention import CommentDocumentMention
from app.models.comment_member_mention import CommentMemberMention
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.post_attachment import PostAttachment
from app.models.face_embedding import FaceEmbedding
from app.models.face_registration_request import FaceRegistrationRequest
from app.models.face_model import FaceModel
from app.models.class_model import Class
from app.models.class_schedule import ClassSchedule
from app.models.class_member import ClassMember
from app.models.attendance_session import AttendanceSession
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_image import AttendanceImage
from app.models.spoof_detection import SpoofDetection
from app.models.leave_request import LeaveRequest
from app.models.refresh_token import RefreshToken
from app.models.system_log import SystemLog
from app.models.ai_training_job import AITrainingJob
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage

__all__ = [
    "Base",
    "BaseModel",
    "User",
    "Admin",
    "Department",
    "Specialization",
    "Teacher",
    "Student",
    "ModelConfig",
    "File",
    "ClassPost",
    "PostReaction",
    "PostComment",
    "PostDocumentMention",
    "PostMemberMention",
    "CommentDocumentMention",
    "CommentMemberMention",
    "Document",
    "DocumentChunk",
    "PostAttachment",
    "FaceEmbedding",
    "FaceRegistrationRequest",
    "FaceModel",
    "Class",
    "ClassSchedule",
    "ClassMember",
    "AttendanceSession",
    "AttendanceRecord",
    "AttendanceImage",
    "SpoofDetection",
    "LeaveRequest",
    "RefreshToken",
    "SystemLog",
    "AITrainingJob",
    "ChatSession",
    "ChatMessage",
]