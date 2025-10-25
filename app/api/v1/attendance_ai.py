"""Attendance endpoints mới với AI-Service integration."""
from fastapi import APIRouter, Depends, Request, Header, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.attendance import (
    StartSessionRequest,
    StartSessionWithAIResponse,
    AICallbackPayload,
    AICallbackResponse,
    SessionResponse
)
from app.services.attendance_ai_service import AttendanceAIService

router = APIRouter(prefix="/attendance", tags=["Attendance AI"])


@router.post("/sessions/start-ai", response_model=StartSessionWithAIResponse, status_code=status.HTTP_201_CREATED)
async def start_attendance_session_with_ai(
    request: StartSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Bắt đầu phiên điểm danh mới với AI-Service.
    
    **Flow:**
    1. Backend tạo session với status="pending"
    2. Backend gọi AI-Service để tạo session
    3. Backend nhận ai_session_id, update status="active"
    4. Client nhận WebSocket URL + JWT token
    5. Client connect trực tiếp tới AI-Service WebSocket
    
    **Returns:**
    - `session_id`: Backend session ID
    - `ai_session_id`: AI Service session ID  
    - `ai_ws_url`: WebSocket URL để connect
    - `ai_ws_token`: JWT token cho authentication
    - `expires_at`: Thời gian hết hạn
    
    **Permissions:**
    - Chỉ teacher của lớp mới được phép
    """
    service = AttendanceAIService(db)
    return await service.start_session_with_ai(current_user, request)


@router.post("/webhook/ai-recognition", response_model=AICallbackResponse)
async def ai_recognition_webhook(
    payload: AICallbackPayload,
    request: Request,
    x_ai_signature: Optional[str] = Header(None, alias="X-AI-Signature"),
    db: Session = Depends(get_db)
):
    """
    Webhook endpoint để nhận callback từ AI-Service.
    
    **AI-Service gửi callback khi:**
    - Sinh viên pass validation (multi-frame recognition)
    - Đủ điều kiện: confidence cao, số frame đủ
    
    **Security:**
    - Verify HMAC-SHA256 signature với shared secret
    - Signature trong header `X-AI-Signature`
    
    **Idempotency:**
    - Không tạo duplicate attendance records
    - Check existing record trước khi insert
    
    **Payload:**
    ```json
    {
        "session_id": "ai-session-uuid",
        "validated_students": [
            {
                "student_code": "102220347",
                "student_name": "Nguyen Van A",
                "track_id": 1,
                "avg_confidence": 0.85,
                "frame_count": 10,
                "recognition_count": 8,
                "validation_passed_at": "2025-10-24T10:00:00Z"
            }
        ],
        "timestamp": "2025-10-24T10:00:00Z"
    }
    ```
    """
    if not x_ai_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-AI-Signature header"
        )
    
    service = AttendanceAIService(db)
    return await service.handle_ai_callback(payload, x_ai_signature)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session_for_polling(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lấy thông tin session cho client polling.
    
    **Use case:**
    - Client poll endpoint này để cập nhật UI
    - Thay thế WebSocket từ backend
    - Chỉ giữ WebSocket với AI-Service
    
    **Returns:**
    - Session info
    - Attendance records (via relationship)
    - Statistics
    
    **Permissions:**
    - Teacher: Được xem session của lớp mình dạy
    - Student: Được xem session của lớp mình học
    """
    from app.models.attendance_session import AttendanceSession
    from app.models.class_model import Class
    from app.models.teacher import Teacher
    from app.models.class_member import ClassMember
    from app.core.enums import UserRole
    
    session = db.query(AttendanceSession).filter(
        AttendanceSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Verify permission
    class_obj = db.query(Class).filter(Class.id == session.class_id).first()
    
    if current_user.role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if not teacher or class_obj.teacher_id != teacher.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    elif current_user.role == UserRole.STUDENT:
        from app.models.student import Student
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        
        is_member = db.query(ClassMember).filter(
            ClassMember.class_id == session.class_id,
            ClassMember.student_id == student.id
        ).first()
        
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid role"
        )
    
    return SessionResponse.model_validate(session)
