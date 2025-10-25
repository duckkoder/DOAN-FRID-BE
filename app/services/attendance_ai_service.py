"""Attendance service với AI-Service integration mới."""
import logging
from typing import List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.models.class_model import Class
from app.models.teacher import Teacher
from app.models.class_member import ClassMember
from app.models.attendance_session import AttendanceSession
from app.models.attendance_record import AttendanceRecord
from app.models.student import Student
from app.core.enums import SessionStatus, AttendanceStatus, UserRole
from app.core.config import settings
from app.core.security import create_websocket_token
from app.services.ai_service_client import ai_service_client
from app.schemas.attendance import (
    StartSessionRequest,
    StartSessionWithAIResponse,
    AICallbackPayload,
    AICallbackResponse,
    AIValidatedStudent
)

logger = logging.getLogger(__name__)


class AttendanceAIService:
    """Service xử lý logic điểm danh với AI-Service."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def start_session_with_ai(
        self, 
        current_user: User, 
        request: StartSessionRequest
    ) -> StartSessionWithAIResponse:
        """
        Bắt đầu phiên điểm danh với AI-Service.
        
        Flow:
        1. Kiểm tra quyền và validate
        2. Tạo session trong DB với status="pending"
        3. Generate JWT token cho WebSocket
        4. Call AI-Service để tạo session
        5. Update ai_session_id và status="active"
        6. Return session info + WebSocket URL + token
        
        Args:
            current_user: User hiện tại (phải là teacher)
            request: StartSessionRequest
            
        Returns:
            StartSessionWithAIResponse với thông tin session và WebSocket
            
        Raises:
            HTTPException: Nếu validation fail hoặc AI-Service error
        """
        # 1. Kiểm tra role
        if current_user.role != UserRole.TEACHER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ giáo viên mới có thể bắt đầu phiên điểm danh"
            )
        
        # 2. Lấy thông tin giáo viên
        teacher = self.db.query(Teacher).filter(
            Teacher.user_id == current_user.id
        ).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy thông tin giáo viên"
            )
        
        # 3. Kiểm tra lớp tồn tại và thuộc sở hữu
        class_obj = self.db.query(Class).filter(
            Class.id == request.class_id
        ).first()
        if not class_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy lớp học"
            )
        
        if class_obj.teacher_id != teacher.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền với lớp học này"
            )
        
        # 4. Kiểm tra không có phiên nào đang active
        ongoing_session = self.db.query(AttendanceSession).filter(
            AttendanceSession.class_id == request.class_id,
            AttendanceSession.status.in_(["pending", "active"])
        ).first()
        
        if ongoing_session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lớp đang có phiên điểm danh đang diễn ra (ID: {ongoing_session.id})"
            )
        
        # 5. Lấy danh sách student_codes trong lớp
        class_members = self.db.query(ClassMember).filter(
            ClassMember.class_id == request.class_id
        ).all()
        
        student_codes = []
        for member in class_members:
            student = self.db.query(Student).filter(
                Student.id == member.student_id
            ).first()
            if student and student.student_code:
                student_codes.append(student.student_code)
        
        if not student_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lớp học không có sinh viên nào"
            )
        
        # 6. Tạo session trong DB với status="pending"
        new_session = AttendanceSession(
            class_id=request.class_id,
            session_name=request.session_name or f"Điểm danh {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            start_time=datetime.utcnow(),
            status="pending",  # Pending cho đến khi AI-Service confirm
            late_threshold_minutes=request.late_threshold_minutes,
            location=request.location,
            allow_late_checkin=True,
            day_of_week=request.day_of_week,
            period_range=request.period_range,
            session_index=request.session_index,
            ai_session_id=None  # Chưa có
        )
        
        self.db.add(new_session)
        self.db.commit()
        self.db.refresh(new_session)
        
        logger.info(
            f"Created pending session",
            extra={
                "session_id": new_session.id,
                "class_id": request.class_id,
                "teacher_id": teacher.id
            }
        )
        
        # 7. Generate JWT token cho WebSocket
        token_expires = timedelta(minutes=settings.AI_WEBSOCKET_TOKEN_EXPIRE_MINUTES)
        ws_token = create_websocket_token(
            user_id=current_user.id,
            session_id=new_session.id,
            role=current_user.role,  # role is already a string
            expires_delta=token_expires
        )
        
        # 8. Call AI-Service để tạo session
        try:
            ai_response = await ai_service_client.create_session(
                backend_session_id=new_session.id,
                class_id=request.class_id,
                student_codes=student_codes,
                ws_token=ws_token,
                allowed_users=[str(current_user.id)]
            )
            
            ai_session_id = ai_response.get("session_id")
            if not ai_session_id:
                raise ValueError("AI-Service không trả về session_id")
            
        except Exception as e:
            # Rollback session nếu AI-Service fail
            self.db.delete(new_session)
            self.db.commit()
            
            logger.error(
                f"Failed to create AI session, rolled back",
                extra={
                    "session_id": new_session.id,
                    "error": str(e)
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Không thể khởi tạo AI-Service: {str(e)}"
            )
        
        # 9. Update ai_session_id và status="active"
        new_session.ai_session_id = ai_session_id
        new_session.status = "active"
        self.db.commit()
        self.db.refresh(new_session)
        
        logger.info(
            f"Session activated with AI",
            extra={
                "session_id": new_session.id,
                "ai_session_id": ai_session_id
            }
        )
        
        # 10. Build WebSocket URL
        ai_ws_base = settings.AI_SERVICE_URL.replace("http://", "ws://").replace("https://", "wss://")
        ai_ws_url = f"{ai_ws_base}/api/v1/sessions/{ai_session_id}/stream"
        
        expires_at = datetime.utcnow() + token_expires
        
        return StartSessionWithAIResponse(
            session_id=new_session.id,
            ai_session_id=ai_session_id,
            ai_ws_url=ai_ws_url,
            ai_ws_token=ws_token,
            expires_at=expires_at,
            status=new_session.status
        )
    
    async def handle_ai_callback(
        self,
        payload: AICallbackPayload,
        signature: str
    ) -> AICallbackResponse:
        """
        Xử lý callback từ AI-Service khi có sinh viên được validate.
        
        Flow:
        1. Verify HMAC signature
        2. Tìm session bằng ai_session_id
        3. Lưu attendance records (với idempotency check)
        4. Return response
        
        Args:
            payload: AICallbackPayload
            signature: HMAC signature từ header
            
        Returns:
            AICallbackResponse
            
        Raises:
            HTTPException: Nếu signature invalid hoặc session not found
        """
        import hmac
        import hashlib
        import json
        
        # 1. Verify HMAC signature
        expected_signature = hmac.new(
            settings.AI_SERVICE_SECRET.encode(),
            json.dumps(payload.dict(), default=str).encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning("Invalid HMAC signature in AI callback")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )
        
        # 2. Tìm session
        session = self.db.query(AttendanceSession).filter(
            AttendanceSession.ai_session_id == payload.session_id,
            AttendanceSession.status == "active"
        ).first()
        
        if not session:
            logger.error(
                f"Session not found for AI callback",
                extra={"ai_session_id": payload.session_id}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # 3. Process validated students
        processed_count = 0
        
        for validated_student in payload.validated_students:
            # Tìm student trong class
            student = self.db.query(Student).filter(
                Student.student_code == validated_student.student_code
            ).first()
            
            if not student:
                logger.warning(
                    f"Student not found",
                    extra={"student_code": validated_student.student_code}
                )
                continue
            
            # Idempotency check - không tạo duplicate
            existing_record = self.db.query(AttendanceRecord).filter(
                AttendanceRecord.session_id == session.id,
                AttendanceRecord.student_id == student.id
            ).first()
            
            if existing_record:
                logger.info(
                    f"Attendance record already exists, skipping",
                    extra={
                        "session_id": session.id,
                        "student_id": student.id
                    }
                )
                continue
            
            # Tính status dựa vào thời gian
            time_diff = datetime.utcnow() - session.start_time
            is_late = time_diff.total_seconds() / 60 > session.late_threshold_minutes
            
            attendance_status = AttendanceStatus.LATE if is_late else AttendanceStatus.PRESENT
            
            # Tạo attendance record
            new_record = AttendanceRecord(
                session_id=session.id,
                student_id=student.id,
                status=attendance_status,
                check_in_time=validated_student.validation_passed_at,
                confidence_score=validated_student.avg_confidence,
                recognition_method="AI"
            )
            
            self.db.add(new_record)
            processed_count += 1
            
            logger.info(
                f"Attendance record created",
                extra={
                    "session_id": session.id,
                    "student_code": validated_student.student_code,
                    "status": attendance_status.value,
                    "confidence": validated_student.avg_confidence
                }
            )
        
        self.db.commit()
        
        return AICallbackResponse(
            status="ok",
            processed_students=processed_count,
            message=f"Processed {processed_count} students successfully"
        )
