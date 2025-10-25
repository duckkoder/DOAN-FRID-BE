"""Attendance service với AI-Service integration."""
import logging
from typing import List, Optional
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


class AttendanceService:
    """Service xử lý logic điểm danh với AI-Service integration."""
    
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
        # Must match AI-Service's signature generation (separators=(',', ':'))
        payload_dict = payload.model_dump()  # Convert Pydantic to dict
        
        # Convert datetime to isoformat to match AI-Service
        if isinstance(payload_dict.get('timestamp'), datetime):
            payload_dict['timestamp'] = payload_dict['timestamp'].isoformat()
        
        for student in payload_dict.get('validated_students', []):
            if isinstance(student.get('validation_passed_at'), datetime):
                student['validation_passed_at'] = student['validation_passed_at'].isoformat()
        
        payload_str = json.dumps(payload_dict, separators=(',', ':'))  # Match AI-Service format
        
        expected_signature = hmac.new(
            settings.AI_SERVICE_SECRET.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning("Invalid HMAC signature in AI callback",
                          extra={
                              "received_signature": signature,
                              "expected_signature": expected_signature,
                              "payload_preview": payload_str[:200]
                          })
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
                recorded_at=validated_student.validation_passed_at,
                confidence_score=validated_student.avg_confidence,
                notes=f"AI-validated (track_id={validated_student.track_id}, frames={validated_student.frame_count})"
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
    
    async def end_session(
        self,
        current_user: User,
        session_id: int,
        request
    ):
        """
        Kết thúc phiên điểm danh.
        
        Logic:
        1. Kiểm tra quyền
        2. Cập nhật status = "finished"
        3. Tự động đánh dấu absent nếu cần
        4. Trả về thống kê
        """
        from app.schemas.attendance import EndSessionResponse
        
        # Kiểm tra role
        if current_user.role != UserRole.TEACHER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ giáo viên mới có thể kết thúc phiên"
            )
        
        # Lấy phiên
        session = self.db.query(AttendanceSession).filter(
            AttendanceSession.id == session_id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy phiên điểm danh"
            )
        
        # Kiểm tra quyền sở hữu
        teacher = self.db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        class_obj = self.db.query(Class).filter(Class.id == session.class_id).first()
        
        if not class_obj or class_obj.teacher_id != teacher.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền với phiên này"
            )
        
        # Kiểm tra phiên đang active
        if session.status not in ["ongoing", "active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Phiên không ở trạng thái đang diễn ra (status: {session.status})"
            )
        
        # Tự động đánh dấu absent nếu được yêu cầu
        if request.mark_absent:
            # Lấy tất cả sinh viên trong lớp
            class_members = self.db.query(ClassMember).filter(
                ClassMember.class_id == session.class_id
            ).all()
            all_student_ids = [member.student_id for member in class_members]
            
            # Lấy các sinh viên đã điểm danh
            existing_records = self.db.query(AttendanceRecord).filter(
                AttendanceRecord.session_id == session_id
            ).all()
            recorded_student_ids = {record.student_id for record in existing_records}
            
            # Tìm sinh viên chưa điểm danh
            absent_student_ids = [sid for sid in all_student_ids if sid not in recorded_student_ids]
            
            # Tạo bản ghi absent
            for student_id in absent_student_ids:
                new_record = AttendanceRecord(
                    session_id=session_id,
                    student_id=student_id,
                    status=AttendanceStatus.ABSENT,
                    recorded_at=datetime.utcnow()
                )
                self.db.add(new_record)
        
        # Cập nhật trạng thái phiên
        session.status = "finished"
        session.end_time = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)
        
        # Tính thống kê
        class_members = self.db.query(ClassMember).filter(
            ClassMember.class_id == session.class_id
        ).all()
        total_students = len(class_members)
        
        records = self.db.query(AttendanceRecord).filter(
            AttendanceRecord.session_id == session_id
        ).all()
        
        present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        late_count = sum(1 for r in records if r.status == AttendanceStatus.LATE)
        absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        
        attendance_rate = (present_count + late_count) / total_students * 100 if total_students > 0 else 0
        
        from app.schemas.attendance import SessionResponse
        
        return EndSessionResponse(
            session=SessionResponse.model_validate(session),
            total_students=total_students,
            present_count=present_count,
            late_count=late_count,
            absent_count=absent_count,
            attendance_rate=round(attendance_rate, 2)
        )
    
    async def get_session_attendance(
        self,
        current_user: User,
        session_id: int
    ):
        """Lấy danh sách điểm danh của phiên."""
        from app.schemas.attendance import SessionAttendanceListResponse, AttendanceRecordDetail, SessionResponse
        
        # Kiểm tra quyền
        session = self.db.query(AttendanceSession).filter(
            AttendanceSession.id == session_id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy phiên điểm danh"
            )
        
        # Kiểm tra quyền truy cập (teacher của lớp hoặc student trong lớp)
        if current_user.role == UserRole.TEACHER:
            teacher = self.db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
            class_obj = self.db.query(Class).filter(Class.id == session.class_id).first()
            if not class_obj or class_obj.teacher_id != teacher.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền truy cập phiên này"
                )
        elif current_user.role == UserRole.STUDENT:
            student = self.db.query(Student).filter(Student.user_id == current_user.id).first()
            member = self.db.query(ClassMember).filter(
                ClassMember.class_id == session.class_id,
                ClassMember.student_id == student.id
            ).first()
            if not member:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không thuộc lớp này"
                )
        
        # Lấy records
        records = self.db.query(AttendanceRecord).filter(
            AttendanceRecord.session_id == session_id
        ).all()
        
        # Chuyển đổi sang schema
        record_details = [
            AttendanceRecordDetail(
                id=record.id,
                session_id=record.session_id,
                student_id=record.student_id,
                student_code=record.student.student_code,
                student_name=record.student.user.full_name,
                status=record.status,
                confidence_score=record.confidence_score,
                recorded_at=record.recorded_at,
                notes=record.notes
            )
            for record in records
        ]
        
        # Tính thống kê
        class_members = self.db.query(ClassMember).filter(
            ClassMember.class_id == session.class_id
        ).all()
        total_students = len(class_members)
        
        present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        late_count = sum(1 for r in records if r.status == AttendanceStatus.LATE)
        absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        
        statistics = {
            "total_students": total_students,
            "present_count": present_count,
            "late_count": late_count,
            "absent_count": absent_count,
            "attendance_rate": round((present_count + late_count) / total_students * 100, 2) if total_students > 0 else 0
        }
        
        return SessionAttendanceListResponse(
            session=SessionResponse.model_validate(session),
            records=record_details,
            statistics=statistics
        )
    
    async def get_class_sessions(
        self,
        current_user: User,
        class_id: int,
        status_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ):
        """
        Lấy danh sách các phiên điểm danh của lớp.
        
        Returns:
            {
                "sessions": [...],
                "total": int
            }
        """
        from app.schemas.attendance import SessionResponse
        
        # Kiểm tra quyền truy cập
        if current_user.role == UserRole.TEACHER:
            teacher = self.db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
            if not teacher:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Không tìm thấy thông tin giáo viên"
                )
            
            class_obj = self.db.query(Class).filter(Class.id == class_id).first()
            if not class_obj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Không tìm thấy lớp học"
                )
            
            if class_obj.teacher_id != teacher.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không có quyền xem lớp này"
                )
        
        elif current_user.role == UserRole.STUDENT:
            student = self.db.query(Student).filter(Student.user_id == current_user.id).first()
            if not student:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Không tìm thấy thông tin sinh viên"
                )
            
            member = self.db.query(ClassMember).filter(
                ClassMember.class_id == class_id,
                ClassMember.student_id == student.id
            ).first()
            if not member:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bạn không thuộc lớp này"
                )
        
        # Build query
        query = self.db.query(AttendanceSession).filter(
            AttendanceSession.class_id == class_id
        )
        
        if status_filter:
            query = query.filter(AttendanceSession.status == status_filter)
        
        # Đếm tổng số
        total = query.count()
        
        # Lấy danh sách phiên
        sessions = query.order_by(AttendanceSession.start_time.desc()).offset(skip).limit(limit).all()
        
        # Chuyển đổi sang schema và thêm statistics cho mỗi phiên
        session_responses = []
        for session in sessions:
            # Lấy statistics của phiên
            records = self.db.query(AttendanceRecord).filter(
                AttendanceRecord.session_id == session.id
            ).all()
            
            class_members = self.db.query(ClassMember).filter(
                ClassMember.class_id == session.class_id
            ).all()
            total_students = len(class_members)
            
            present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
            late_count = sum(1 for r in records if r.status == AttendanceStatus.LATE)
            absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
            
            session_data = SessionResponse.model_validate(session).model_dump()
            session_data["statistics"] = {
                "total_students": total_students,
                "present_count": present_count,
                "late_count": late_count,
                "absent_count": absent_count,
                "attendance_rate": round((present_count + late_count) / total_students * 100, 2) if total_students > 0 else 0
            }
            session_responses.append(session_data)
        
        return {
            "sessions": session_responses,
            "total": total
        }
