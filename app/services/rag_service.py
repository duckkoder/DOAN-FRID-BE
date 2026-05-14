import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException

from app.models.class_model import Class
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.user import User
from app.schemas.rag_schema import ChatSaveRequest, ChatMessageResponse


class RAGService:
    @staticmethod
    def save_chat_message(db: Session, current_user: User, body: ChatSaveRequest) -> str:
        class_obj = db.query(Class).filter(Class.id == body.class_id).first()
        if not class_obj or not class_obj.course_id:
            raise HTTPException(status_code=404, detail="Class or Course not found")

        session = db.query(ChatSession).filter(
            ChatSession.user_id == current_user.id,
            ChatSession.course_id == class_obj.course_id
        ).first()

        if not session:
            session = ChatSession(
                id=uuid.uuid4(),
                user_id=current_user.id,
                course_id=class_obj.course_id
            )
            db.add(session)
            db.flush()

        user_msg = ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            role="user",
            content=body.question
        )
        
        ai_msg = ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            role="ai",
            content=body.answer,
            citations=body.citations
        )
        
        db.add(user_msg)
        db.add(ai_msg)
        db.commit()
        
        return str(session.id)

    @staticmethod
    def get_chat_history(db: Session, current_user: User, class_id: int, limit: int = 20) -> List[ChatMessageResponse]:
        class_obj = db.query(Class).filter(Class.id == class_id).first()
        if not class_obj or not class_obj.course_id:
            return []

        session = db.query(ChatSession).filter(
            ChatSession.user_id == current_user.id,
            ChatSession.course_id == class_obj.course_id
        ).first()

        if not session:
            return []

        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(desc(ChatMessage.created_at)).limit(limit).all()

        return [
            ChatMessageResponse(
                role=m.role,
                content=m.content,
                created_at=m.created_at,
                citations=m.citations
            )
            for m in reversed(messages)
        ]

    @staticmethod
    def clear_chat_history(db: Session, current_user: User, class_id: int) -> bool:
        class_obj = db.query(Class).filter(Class.id == class_id).first()
        if not class_obj or not class_obj.course_id:
            return True

        session = db.query(ChatSession).filter(
            ChatSession.user_id == current_user.id,
            ChatSession.course_id == class_obj.course_id
        ).first()

        if session:
            db.delete(session)
            db.commit()

        return True
