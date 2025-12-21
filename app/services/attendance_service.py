"""Attendance service với AI-Service integration."""
import logging
import httpx
import base64
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

# ✅ Define Vietnam timezone for consistency
VIETNAM_TZ = ZoneInfo('Asia/Ho_Chi_Minh')

from app.models.user import User
from app.models.class_model import Class
from app.models.teacher import Teacher
from app.models.class_member import ClassMember
from app.models.attendance_session import AttendanceSession
from app.models.attendance_record import AttendanceRecord
from app.models.student import Student
from app.models.leave_request import LeaveRequest
from app.core.enums import SessionStatus, AttendanceStatus, UserRole, RequestStatus
from app.core.config import settings
from app.core.security import create_websocket_token
from app.services.ai_service_client import ai_service_client
from app.schemas.attendance import (
    StartSessionRequest,
    StartSessionWithAIResponse,
    ResumeSessionResponse,
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
        2. Tạo session trong DB với status="scheduled"
        3. Generate JWT token cho WebSocket
        4. Call AI-Service để tạo session
        5. Update ai_session_id và status="ongoing"
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
        
        # 4. Kiểm tra không có phiên nào đang ongoing
        ongoing_session = self.db.query(AttendanceSession).filter(
            AttendanceSession.class_id == request.class_id,
            AttendanceSession.status.in_([SessionStatus.SCHEDULED.value, SessionStatus.ONGOING.value])
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
        
        # 6. Tạo session trong DB với status="scheduled"
        # ✅ Use Vietnam timezone for all datetime fields
        vietnam_now = datetime.now(VIETNAM_TZ)
        default_session_name = f"Điểm danh {vietnam_now.strftime('%d/%m/%Y %H:%M')}"
        
        new_session = AttendanceSession(
            class_id=request.class_id,
            session_name=request.session_name or default_session_name,
            start_time=vietnam_now,
            status=SessionStatus.SCHEDULED.value,  # Scheduled cho đến khi AI-Service confirm
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
        
        # 9. Update ai_session_id và status="ongoing"
        new_session.ai_session_id = ai_session_id
        new_session.status = SessionStatus.ONGOING.value
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
        
        expires_at = datetime.now(VIETNAM_TZ) + token_expires
        
        return StartSessionWithAIResponse(
            session_id=new_session.id,
            ai_session_id=ai_session_id,
            ai_ws_url=ai_ws_url,
            ai_ws_token=ws_token,
            expires_at=expires_at,
            status=new_session.status
        )
    
    async def resume_session(
        self,
        current_user: User,
        session_id: int
    ) -> ResumeSessionResponse:
        """
        Resume một phiên điểm danh đang ongoing sau khi refresh page.
        
        Tạo token WebSocket mới để kết nối lại với AI-Service.
        Nếu AI-Service session đã bị mất (restart/timeout), báo lỗi yêu cầu kết thúc phiên.
        
        Args:
            current_user: User hiện tại (phải là teacher của lớp)
            session_id: ID của session cần resume
            
        Returns:
            ResumeSessionResponse với thông tin WebSocket mới
            
        Raises:
            HTTPException: Nếu session không tồn tại, không ongoing, AI session đã mất, hoặc không có quyền
        """
        # 1. Kiểm tra role
        if current_user.role != UserRole.TEACHER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ giáo viên mới có thể resume phiên điểm danh"
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
        
        # 3. Lấy session
        session = self.db.query(AttendanceSession).filter(
            AttendanceSession.id == session_id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy phiên điểm danh"
            )
        
        # 4. Kiểm tra session đang ongoing
        if session.status != SessionStatus.ONGOING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Phiên điểm danh không ở trạng thái đang diễn ra (status: {session.status})"
            )
        
        # 5. Kiểm tra quyền - lớp phải thuộc về giáo viên này
        class_obj = self.db.query(Class).filter(
            Class.id == session.class_id
        ).first()
        
        if not class_obj or class_obj.teacher_id != teacher.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền với phiên điểm danh này"
            )
        
        # 6. Kiểm tra AI-Service session còn tồn tại không
        ai_session_id = session.ai_session_id
        
        if not ai_session_id:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Phiên điểm danh không có kết nối AI. Vui lòng kết thúc phiên này và tạo phiên điểm danh mới."
            )
        
        # Kiểm tra AI session còn active không
        try:
            ai_status = await ai_service_client.get_session_status(ai_session_id)
            if ai_status.get("status") != "active":
                logger.warning(
                    f"AI session not active",
                    extra={
                        "session_id": session.id,
                        "ai_session_id": ai_session_id,
                        "ai_status": ai_status.get("status")
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Kết nối AI đã hết hạn hoặc không còn hoạt động. Vui lòng kết thúc phiên này và tạo phiên điểm danh mới."
                )
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.warning(
                f"AI session not found or expired",
                extra={
                    "session_id": session.id,
                    "ai_session_id": ai_session_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Kết nối AI đã mất (có thể do hệ thống khởi động lại). Vui lòng kết thúc phiên này và tạo phiên điểm danh mới."
            )
        
        logger.info(
            f"AI session still active, proceeding with resume",
            extra={
                "session_id": session.id,
                "ai_session_id": ai_session_id
            }
        )
        
        # 7. Generate JWT token mới cho WebSocket
        token_expires = timedelta(minutes=settings.AI_WEBSOCKET_TOKEN_EXPIRE_MINUTES)
        ws_token = create_websocket_token(
            user_id=current_user.id,
            session_id=session.id,
            role=current_user.role,
            expires_delta=token_expires
        )
        
        # 8. Build WebSocket URL
        ai_ws_base = settings.AI_SERVICE_URL.replace("http://", "ws://").replace("https://", "wss://")
        ai_ws_url = f"{ai_ws_base}/api/v1/sessions/{ai_session_id}/stream"
        
        expires_at = datetime.now(VIETNAM_TZ) + token_expires
        
        logger.info(
            f"Session resumed",
            extra={
                "session_id": session.id,
                "ai_session_id": ai_session_id,
                "teacher_id": teacher.id
            }
        )
        
        return ResumeSessionResponse(
            session_id=session.id,
            ai_session_id=ai_session_id,
            ai_ws_url=ai_ws_url,
            ai_ws_token=ws_token,
            expires_at=expires_at,
            status=session.status,
            session_name=session.session_name,
            start_time=session.start_time,
            class_id=session.class_id
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
            AttendanceSession.status == SessionStatus.ONGOING.value
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
        
        # 3. Process validated students với confidence threshold logic
        processed_count = 0
        pending_count = 0
        auto_approved_count = 0
        
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
            
            # ✅ HYBRID APPROACH: Kiểm tra confidence để quyết định status
            confidence = validated_student.avg_confidence
            
            if confidence >= settings.AI_CONFIDENCE_THRESHOLD:
                # Confidence cao → Tự động xác nhận là PRESENT
                attendance_status = AttendanceStatus.PRESENT
                notes = f"AI-validated (track_id={validated_student.track_id}, frames={validated_student.frame_count}, confidence={confidence:.3f}, auto-approved)"
                auto_approved_count += 1
                logger.info(
                    f"✅ Auto-approved attendance (high confidence)",
                    extra={
                        "student_code": validated_student.student_code,
                        "confidence": confidence,
                        "threshold": settings.AI_CONFIDENCE_THRESHOLD
                    }
                )
            else:
                # Confidence thấp → Chờ giáo viên xác nhận (PENDING)
                attendance_status = AttendanceStatus.PENDING
                notes = f"Pending teacher confirmation (track_id={validated_student.track_id}, frames={validated_student.frame_count}, confidence={confidence:.3f})"
                pending_count += 1
                logger.warning(
                    f"⏳ Pending teacher confirmation (low confidence)",
                    extra={
                        "student_code": validated_student.student_code,
                        "confidence": confidence,
                        "threshold": settings.AI_CONFIDENCE_THRESHOLD
                    }
                )
            
            # Tạo attendance record (image_path = NULL, sẽ update sau khi end_session)
            new_record = AttendanceRecord(
                session_id=session.id,
                student_id=student.id,
                status=attendance_status,
                recorded_at=validated_student.validation_passed_at,
                confidence_score=validated_student.avg_confidence,
                image_path=None,  # ⚠️ CHƯA CÓ ẢNH, sẽ update sau
                notes=notes
            )
            
            self.db.add(new_record)
            self.db.flush()  # ✅ Flush để có ID ngay (cần cho WebSocket notification)
            
            processed_count += 1
            
            # ✅ Nếu PENDING, gửi realtime notification qua WebSocket
            if attendance_status == AttendanceStatus.PENDING:
                try:
                    # Import ở đây để tránh circular import
                    from app.api.v1.attendance import manager
                    from app.schemas.attendance import WSPendingConfirmation
                    
                    # Broadcast pending confirmation tới giáo viên trong phiên
                    import asyncio
                    asyncio.create_task(
                        manager.broadcast_to_session(
                            session.id,
                            WSPendingConfirmation(
                                type="pending_confirmation",
                                session_id=session.id,
                                record_id=new_record.id,
                                student_id=student.id,
                                student_code=student.student_code,
                                full_name=student.user.full_name,
                                confidence_score=validated_student.avg_confidence,
                                recorded_at=validated_student.validation_passed_at,
                                message=f"Sinh viên {student.user.full_name} cần xác nhận (confidence: {confidence:.1%})"
                            ).model_dump()
                        )
                    )
                    logger.info(f"📢 Sent pending confirmation notification for student {student.student_code}")
                except Exception as ws_error:
                    logger.error(f"Failed to send WebSocket notification: {ws_error}")
            
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
            message=f"Processed {processed_count} students ({auto_approved_count} auto-approved, {pending_count} pending confirmation)"
        )
    
    async def end_session(
        self,
        current_user: User,
        session_id: int,
        request,
        skip_image_upload: bool = False
    ):
        """
        Kết thúc phiên điểm danh.
        
        Logic:
        1. Kiểm tra quyền
        2. Cập nhật status = "finished"
        3. Tự động đánh dấu absent nếu cần
        4. Trả về thống kê
        
        Args:
            skip_image_upload: Nếu True, bỏ qua việc upload ảnh (để chạy ở background task)
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
        
        # Kiểm tra phiên đang ongoing
        if session.status != SessionStatus.ONGOING.value:
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
                    recorded_at=datetime.now(VIETNAM_TZ)
                )
                self.db.add(new_record)
        
        # Commit để có các bản ghi absent
        self.db.commit()
        
        # Xử lý đơn xin nghỉ đã được chấp nhận
        # Lấy tất cả records có status ABSENT
        absent_records = self.db.query(AttendanceRecord).filter(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.status == AttendanceStatus.ABSENT
        ).all()
        
        if absent_records:
            # Lấy thông tin về ngày và thời gian của session
            # ✅ FIX: Convert session start_time to Vietnam timezone before extracting date
            session_start_vietnam = session.start_time
            if session_start_vietnam.tzinfo is None:
                # Nếu naive datetime, assume UTC và convert sang Vietnam
                session_start_vietnam = session_start_vietnam.replace(tzinfo=timezone.utc).astimezone(VIETNAM_TZ)
            else:
                # Nếu aware datetime, convert sang Vietnam timezone
                session_start_vietnam = session_start_vietnam.astimezone(VIETNAM_TZ)
            
            session_date = session_start_vietnam.date()
            
            # ✅ FIX: Tạo range với timezone-aware datetime để so sánh chính xác
            # leave_date trong DB có thể lưu dạng UTC, cần convert sang Vietnam
            day_start_vietnam = datetime.combine(session_date, datetime.min.time()).replace(tzinfo=VIETNAM_TZ)
            day_end_vietnam = datetime.combine(session_date, datetime.max.time()).replace(tzinfo=VIETNAM_TZ)
            
            # Convert sang UTC để so sánh với DB (PostgreSQL thường lưu UTC)
            day_start_utc = day_start_vietnam.astimezone(timezone.utc)
            day_end_utc = day_end_vietnam.astimezone(timezone.utc)
            
            logger.info(
                f"Checking leave requests for session {session_id}: "
                f"session_start_time={session.start_time}, "
                f"session_date_vietnam={session_date}, "
                f"day_start_utc={day_start_utc}, day_end_utc={day_end_utc}"
            )
            
            # Tìm các đơn xin nghỉ đã được chấp nhận cho lớp này trong ngày này
            # So sánh với cả 2 trường hợp: leave_date lưu dạng UTC hoặc naive
            from sqlalchemy import or_, func
            approved_leave_requests = self.db.query(LeaveRequest).filter(
                LeaveRequest.class_id == session.class_id,
                LeaveRequest.status == RequestStatus.APPROVED.value,
                or_(
                    # Case 1: leave_date là UTC aware datetime
                    (LeaveRequest.leave_date >= day_start_utc) & (LeaveRequest.leave_date < day_end_utc),
                    # Case 2: leave_date là naive datetime (so sánh trực tiếp với Vietnam date)
                    func.date(LeaveRequest.leave_date) == session_date
                )
            ).all()
            
            logger.info(
                f"Found {len(approved_leave_requests)} approved leave requests for class {session.class_id} on {session_date}"
            )
            for lr in approved_leave_requests:
                logger.info(f"  - LeaveRequest ID={lr.id}, student_id={lr.student_id}, leave_date={lr.leave_date}")
            
            # Tạo map student_id -> leave_request để tra cứu nhanh
            approved_student_ids = {lr.student_id: lr for lr in approved_leave_requests}
            
            # Cập nhật status cho các sinh viên có đơn được duyệt
            excused_count = 0
            for record in absent_records:
                if record.student_id in approved_student_ids:
                    leave_request = approved_student_ids[record.student_id]
                    
                    # Kiểm tra thêm về time_slot nếu cần (tùy chọn)
                    # Có thể match với period_range hoặc session_index
                    # Ở đây tôi cập nhật tất cả absent có đơn trong ngày
                    
                    record.status = AttendanceStatus.EXCUSED
                    record.notes = f"Đã có đơn xin nghỉ được chấp nhận (ID: {leave_request.id})"
                    excused_count += 1
                    logger.info(
                        f"Updated student {record.student_id} from ABSENT to EXCUSED "
                        f"based on approved leave request {leave_request.id}"
                    )
        
        # ✅ GỌI AI SERVICE LẤY ẢNH VÀ UPLOAD LÊN S3 (CHỈ NẾU KHÔNG SKIP)
        # Nếu skip_image_upload=True, việc upload sẽ được thực hiện ở background task
        if not skip_image_upload and session.ai_session_id:
            try:
                await self._fetch_and_upload_face_images(session)
            except Exception as e:
                logger.error(f"Failed to fetch and upload face images: {e}")
                # Continue without images (không block end_session)
        
        # Cập nhật trạng thái phiên
        session.status = SessionStatus.FINISHED.value
        session.end_time = datetime.now(VIETNAM_TZ)
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
        absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        excused_count = sum(1 for r in records if r.status == AttendanceStatus.EXCUSED)
        pending_count = sum(1 for r in records if r.status == AttendanceStatus.PENDING)  # ✅ NEW
        
        # Chỉ tính present, không tính late vì không có trạng thái late
        attendance_rate = present_count / total_students * 100 if total_students > 0 else 0
        
        from app.schemas.attendance import SessionResponse
        
        return EndSessionResponse(
            session=SessionResponse.model_validate(session),
            total_students=total_students,
            present_count=present_count,
            absent_count=absent_count,
            excused_count=excused_count,
            pending_count=pending_count,  # ✅ NEW
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
                notes=record.notes,
                image_path=record.image_path
            )
            for record in records
        ]
        
        # Tính thống kê
        class_members = self.db.query(ClassMember).filter(
            ClassMember.class_id == session.class_id
        ).all()
        total_students = len(class_members)
        
        present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        excused_count = sum(1 for r in records if r.status == AttendanceStatus.EXCUSED)
        pending_count = sum(1 for r in records if r.status == AttendanceStatus.PENDING)  # ✅ NEW
        
        statistics = {
            "total_students": total_students,
            "present_count": present_count,
            "absent_count": absent_count,
            "excused_count": excused_count,
            "pending_count": pending_count,  # ✅ NEW
            "attendance_rate": round(present_count / total_students * 100, 2) if total_students > 0 else 0
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
            absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
            excused_count = sum(1 for r in records if r.status == AttendanceStatus.EXCUSED)
            pending_count = sum(1 for r in records if r.status == AttendanceStatus.PENDING)  # ✅ NEW
            
            session_data = SessionResponse.model_validate(session).model_dump()
            session_data["statistics"] = {
                "total_students": total_students,
                "present_count": present_count,
                "absent_count": absent_count,
                "excused_count": excused_count,
                "pending_count": pending_count,  # ✅ NEW
                "attendance_rate": round(present_count / total_students * 100, 2) if total_students > 0 else 0
            }
            session_responses.append(session_data)
        
        return {
            "sessions": session_responses,
            "total": total
        }
    
    async def _fetch_and_upload_face_images(self, session: AttendanceSession):
        """
        Gọi AI Service lấy face crops và upload lên S3, sau đó update image_path cho records.
        
        Args:
            session: AttendanceSession object
        """
        from app.services.file_service import FileService
        
        # Lấy teacher_id để làm uploader_id
        class_obj = self.db.query(Class).filter(Class.id == session.class_id).first()
        teacher = self.db.query(Teacher).filter(Teacher.id == class_obj.teacher_id).first() if class_obj else None
        uploader_id = teacher.user_id if teacher else 1  # Fallback to system user
        
        # Khởi tạo FileService
        file_service = FileService(self.db)
        
        try:
            # 1. Gọi AI Service GET /sessions/{ai_session_id}/face-crops
            ai_service_url = f"{settings.AI_SERVICE_URL}/api/v1/sessions/{session.ai_session_id}/face-crops"
            
            # Tăng timeout dựa trên số lượng sinh viên dự kiến (2s per student)
            # Tối thiểu 60s, tối đa 300s (5 phút)
            class_members_count = self.db.query(ClassMember).filter(
                ClassMember.class_id == session.class_id
            ).count()
            estimated_timeout = max(60, min(class_members_count * 2 + 30, 300))
            
            async with httpx.AsyncClient(timeout=estimated_timeout) as client:
                response = await client.get(ai_service_url)
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch face crops from AI Service: {response.status_code}")
                    return
                
                data = response.json()
                face_crops = data.get("face_crops", [])
                
                if not face_crops:
                    logger.info(f"No face crops available for session {session.id}")
                    return
                
                logger.info(f"Fetched {len(face_crops)} face crops from AI Service")
                
                # 2. Upload từng ảnh lên S3 qua FileService và update DB
                uploaded_count = 0
                skipped_count = 0
                
                for crop_data in face_crops:
                    student_code = crop_data.get("student_code")
                    face_crop_base64 = crop_data.get("face_crop_base64")
                    
                    if not student_code or not face_crop_base64:
                        continue
                    
                    try:
                        # Find student
                        student = self.db.query(Student).filter(
                            Student.student_code == student_code
                        ).first()
                        
                        if not student:
                            logger.warning(f"Student not found: {student_code}")
                            continue
                        
                        # Find attendance record
                        record = self.db.query(AttendanceRecord).filter(
                            AttendanceRecord.session_id == session.id,
                            AttendanceRecord.student_id == student.id
                        ).first()
                        
                        if not record:
                            logger.warning(f"Attendance record not found for student {student_code}")
                            continue
                        
                        # ✅ Idempotency check: Skip nếu đã có ảnh
                        if record.image_path:
                            logger.info(f"Image already uploaded for {student_code}, skipping")
                            skipped_count += 1
                            continue
                        
                        # Upload to S3 via FileService
                        timestamp_ms = int(datetime.now().timestamp() * 1000)
                        filename = f"{session.id}/{student_code}_{timestamp_ms}.jpg"
                        
                        file_record = await file_service.upload_base64_and_save(
                            base64_data=face_crop_base64,
                            filename=filename,
                            folder="private/attendance-evidence",
                            uploader_id=uploader_id,
                            category="attendance_evidence"
                        )
                        
                        # Update attendance record với file_id (để có thể get presigned URL sau)
                        # Lưu cả S3 URL cho backward compatibility
                        image_url = file_service.get_file_url(file_record.id)
                        record.image_path = image_url
                        
                        # ✅ Commit ngay sau mỗi record để tránh mất dữ liệu
                        self.db.commit()
                        
                        uploaded_count += 1
                        
                        logger.info(f"✅ Uploaded face evidence for {student_code}: file_id={file_record.id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to process face crop for {student_code}: {e}")
                        # Rollback transaction hiện tại nếu có lỗi
                        self.db.rollback()
                        continue
                
                logger.info(f"✅ Uploaded {uploaded_count}/{len(face_crops)} face images to S3 (skipped: {skipped_count})")
                
        except Exception as e:
            logger.error(f"Error in _fetch_and_upload_face_images: {e}")
            raise

