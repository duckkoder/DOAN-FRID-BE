"""Attendance service vá»›i AI-Service integration."""
import logging
import httpx
import base64
from typing import List, Optional
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

# âœ… Define Vietnam timezone for consistency
VIETNAM_TZ = ZoneInfo('Asia/Ho_Chi_Minh')

from app.models.user import User
from app.models.class_model import Class
from app.models.class_schedule import ClassSchedule
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

PERIOD_TIME_SLOTS = {
    1: ("07:00", "07:50"),
    2: ("08:00", "08:50"),
    3: ("09:00", "09:50"),
    4: ("10:00", "10:50"),
    5: ("11:00", "11:50"),
    6: ("13:00", "13:50"),
    7: ("14:00", "14:50"),
    8: ("15:00", "15:50"),
    9: ("16:00", "16:50"),
    10: ("17:00", "17:50"),
}


class AttendanceService:
    """Service xá»­ lÃ½ logic Ä‘iá»ƒm danh vá»›i AI-Service integration."""
    
    def __init__(self, db: Session, tenant_code: str | None = None):
        self.db = db
        self.tenant_code = tenant_code or "tenant"

    def _extract_period_numbers(self, period_range: Optional[str]) -> List[int]:
        if not period_range:
            return []

        import re

        numbers = [int(value) for value in re.findall(r"\d+", period_range)]
        if len(numbers) >= 2:
            return list(range(numbers[0], numbers[-1] + 1))
        return numbers

    def _parse_period_time(self, value: str) -> time:
        hour, minute = [int(part) for part in value.split(":", 1)]
        return time(hour=hour, minute=minute)

    def _periods_overlap(self, left: Optional[str], right: Optional[str]) -> bool:
        if not left or not right:
            return True

        def parse_periods(value: str) -> set[int]:
            parts = [int(part) for part in value.split("-") if part.strip().isdigit()]
            if len(parts) >= 2:
                return set(range(parts[0], parts[-1] + 1))
            return set(parts)

        left_periods = parse_periods(left)
        right_periods = parse_periods(right)
        if not left_periods or not right_periods:
            return True
        return bool(left_periods & right_periods)

    def _validate_session_create_window(self, request: StartSessionRequest) -> None:
        if request.day_of_week is None or not request.period_range:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cần chọn đúng buổi học để bắt đầu điểm danh",
            )

        now = datetime.now(VIETNAM_TZ)
        if request.day_of_week != now.weekday():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ có thể tạo phiên điểm danh trong ngày học của buổi này",
            )

        target_periods = self._extract_period_numbers(request.period_range)
        if not target_periods:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Khoảng tiết học không hợp lệ",
            )

        schedule_rows = self.db.query(ClassSchedule).filter(
            ClassSchedule.class_id == request.class_id
        ).all()
        has_matching_schedule = any(
            (row.schedule_data or {}).get("day") == request.day_of_week
            and ((row.schedule_data or {}).get("periods") or []) == target_periods
            for row in schedule_rows
        )
        if not has_matching_schedule:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Buổi học này không khớp với lịch của lớp",
            )

        first_period = min(target_periods)
        last_period = max(target_periods)
        if first_period not in PERIOD_TIME_SLOTS or last_period not in PERIOD_TIME_SLOTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tiết học không hợp lệ",
            )

        session_start = datetime.combine(
            now.date(),
            self._parse_period_time(PERIOD_TIME_SLOTS[first_period][0]),
            tzinfo=VIETNAM_TZ,
        )
        session_end = datetime.combine(
            now.date(),
            self._parse_period_time(PERIOD_TIME_SLOTS[last_period][1]),
            tzinfo=VIETNAM_TZ,
        )

        if settings.ATTENDANCE_ALLOW_CREATE_ANYTIME:
            return

        grace = timedelta(minutes=max(settings.ATTENDANCE_CREATE_WINDOW_GRACE_MINUTES, 0))

        if now < session_start - grace or now > session_end + grace:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Chỉ có thể tạo phiên điểm danh trong khung giờ "
                    f"{PERIOD_TIME_SLOTS[first_period][0]} - {PERIOD_TIME_SLOTS[last_period][1]}"
                ),
            )

    def _resolve_session_location(self, request: StartSessionRequest) -> Optional[str]:
        if request.location and request.location.strip().lower() not in {"classroom", "class room", "n/a"}:
            return request.location.strip()

        schedule_rows = self.db.query(ClassSchedule).filter(
            ClassSchedule.class_id == request.class_id
        ).order_by(ClassSchedule.id.asc()).all()
        if not schedule_rows:
            return None

        target_periods = self._extract_period_numbers(request.period_range)
        same_day_rows = []

        for row in schedule_rows:
            schedule_data = row.schedule_data or {}
            if schedule_data.get("day") == request.day_of_week:
                same_day_rows.append(row)
                row_periods = schedule_data.get("periods") or []
                if target_periods and row_periods == target_periods:
                    return row.location

        if request.session_index is not None:
            all_rows = sorted(
                schedule_rows,
                key=lambda item: ((item.schedule_data or {}).get("day", 0), item.id)
            )
            if 0 <= request.session_index < len(all_rows):
                return all_rows[request.session_index].location

        if same_day_rows:
            return same_day_rows[0].location

        return schedule_rows[0].location
    
    async def start_session_with_ai(
        self, 
        current_user: User, 
        request: StartSessionRequest,
        tenant_slug: str,
    ) -> StartSessionWithAIResponse:
        """
        Báº¯t Ä‘áº§u phiÃªn Ä‘iá»ƒm danh vá»›i AI-Service.
        
        Flow:
        1. Kiá»ƒm tra quyá»n vÃ  validate
        2. Táº¡o session trong DB vá»›i status="scheduled"
        3. Generate JWT token cho WebSocket
        4. Call AI-Service Ä‘á»ƒ táº¡o session
        5. Update ai_session_id vÃ  status="ongoing"
        6. Return session info + WebSocket URL + token
        
        Args:
            current_user: User hiá»‡n táº¡i (pháº£i lÃ  teacher)
            request: StartSessionRequest
            
        Returns:
            StartSessionWithAIResponse vá»›i thÃ´ng tin session vÃ  WebSocket
            
        Raises:
            HTTPException: Náº¿u validation fail hoáº·c AI-Service error
        """
        # 1. Kiá»ƒm tra role
        if current_user.role != UserRole.TEACHER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chá»‰ giÃ¡o viÃªn má»›i cÃ³ thá»ƒ báº¯t Ä‘áº§u phiÃªn Ä‘iá»ƒm danh"
            )
        
        # 2. Láº¥y thÃ´ng tin giÃ¡o viÃªn
        teacher = self.db.query(Teacher).filter(
            Teacher.user_id == current_user.id
        ).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KhÃ´ng tÃ¬m tháº¥y thÃ´ng tin giÃ¡o viÃªn"
            )
        
        # 3. Kiá»ƒm tra lá»›p tá»“n táº¡i vÃ  thuá»™c sá»Ÿ há»¯u
        class_obj = self.db.query(Class).filter(
            Class.id == request.class_id
        ).first()
        if not class_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KhÃ´ng tÃ¬m tháº¥y lá»›p há»c"
            )
        
        if class_obj.teacher_id != teacher.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Báº¡n khÃ´ng cÃ³ quyá»n vá»›i lá»›p há»c nÃ y"
            )

        self._validate_session_create_window(request)
        
        # 4. Kiá»ƒm tra khÃ´ng cÃ³ phiÃªn nÃ o Ä‘ang ongoing
        ongoing_session = self.db.query(AttendanceSession).filter(
            AttendanceSession.class_id == request.class_id,
            AttendanceSession.status.in_([SessionStatus.SCHEDULED.value, SessionStatus.ONGOING.value])
        ).first()
        
        if ongoing_session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lá»›p Ä‘ang cÃ³ phiÃªn Ä‘iá»ƒm danh Ä‘ang diá»…n ra (ID: {ongoing_session.id})"
            )
        
        # 5. Láº¥y danh sÃ¡ch student_codes trong lá»›p
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
                detail="Lá»›p há»c khÃ´ng cÃ³ sinh viÃªn nÃ o"
            )
        
        from app.services.face_embedding_service import FaceEmbeddingService
        face_embeddings = FaceEmbeddingService.get_approved_embeddings_by_student_codes(
            self.db,
            student_codes,
        )
        if not face_embeddings:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lớp học chưa có embedding khuôn mặt đã duyệt",
            )
        # 6. Táº¡o session trong DB vá»›i status="scheduled"
        # âœ… Use Vietnam timezone for all datetime fields
        vietnam_now = datetime.now(VIETNAM_TZ)
        default_session_name = f"Äiá»ƒm danh {vietnam_now.strftime('%d/%m/%Y %H:%M')}"
        
        session_location = self._resolve_session_location(request)

        new_session = AttendanceSession(
            class_id=request.class_id,
            session_name=request.session_name or default_session_name,
            start_time=vietnam_now,
            status=SessionStatus.SCHEDULED.value,  # Scheduled cho Ä‘áº¿n khi AI-Service confirm
            late_threshold_minutes=request.late_threshold_minutes,
            location=session_location,
            allow_late_checkin=True,
            day_of_week=request.day_of_week,
            period_range=request.period_range,
            session_index=request.session_index,
            ai_session_id=None  # ChÆ°a cÃ³
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
            tenant_slug=tenant_slug,
            expires_delta=token_expires
        )
        
        # 8. Call AI-Service Ä‘á»ƒ táº¡o session
        try:
            ai_response = await ai_service_client.create_session(
                backend_session_id=new_session.id,
                class_id=request.class_id,
                student_codes=student_codes,
                face_embeddings=face_embeddings,
                ws_token=ws_token,
                tenant_slug=tenant_slug,
                allowed_users=[str(current_user.id)]
            )
            
            ai_session_id = ai_response.get("session_id")
            if not ai_session_id:
                raise ValueError("AI-Service khÃ´ng tráº£ vá» session_id")
            
        except Exception as e:
            # Rollback session náº¿u AI-Service fail
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
                detail=f"KhÃ´ng thá»ƒ khá»Ÿi táº¡o AI-Service: {str(e)}"
            )
        
        # 9. Update ai_session_id vÃ  status="ongoing"
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
        
        # 10. Build WebSocket URL for Frontend
        if settings.AI_SERVICE_PUBLIC_URL:
            ai_ws_base = settings.AI_SERVICE_PUBLIC_URL.rstrip('/')
        else:
            # Fallback to internal URL (usually for local dev)
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
        session_id: int,
        tenant_slug: str,
    ) -> ResumeSessionResponse:
        """
        Resume má»™t phiÃªn Ä‘iá»ƒm danh Ä‘ang ongoing sau khi refresh page.
        
        Táº¡o token WebSocket má»›i Ä‘á»ƒ káº¿t ná»‘i láº¡i vá»›i AI-Service.
        Náº¿u AI-Service session Ä‘Ã£ bá»‹ máº¥t (restart/timeout), bÃ¡o lá»—i yÃªu cáº§u káº¿t thÃºc phiÃªn.
        
        Args:
            current_user: User hiá»‡n táº¡i (pháº£i lÃ  teacher cá»§a lá»›p)
            session_id: ID cá»§a session cáº§n resume
            
        Returns:
            ResumeSessionResponse vá»›i thÃ´ng tin WebSocket má»›i
            
        Raises:
            HTTPException: Náº¿u session khÃ´ng tá»“n táº¡i, khÃ´ng ongoing, AI session Ä‘Ã£ máº¥t, hoáº·c khÃ´ng cÃ³ quyá»n
        """
        # 1. Kiá»ƒm tra role
        if current_user.role != UserRole.TEACHER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chá»‰ giÃ¡o viÃªn má»›i cÃ³ thá»ƒ resume phiÃªn Ä‘iá»ƒm danh"
            )
        
        # 2. Láº¥y thÃ´ng tin giÃ¡o viÃªn
        teacher = self.db.query(Teacher).filter(
            Teacher.user_id == current_user.id
        ).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KhÃ´ng tÃ¬m tháº¥y thÃ´ng tin giÃ¡o viÃªn"
            )
        
        # 3. Láº¥y session
        session = self.db.query(AttendanceSession).filter(
            AttendanceSession.id == session_id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KhÃ´ng tÃ¬m tháº¥y phiÃªn Ä‘iá»ƒm danh"
            )
        
        # 4. Kiá»ƒm tra session Ä‘ang ongoing
        if session.status != SessionStatus.ONGOING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PhiÃªn Ä‘iá»ƒm danh khÃ´ng á»Ÿ tráº¡ng thÃ¡i Ä‘ang diá»…n ra (status: {session.status})"
            )
        
        # 5. Kiá»ƒm tra quyá»n - lá»›p pháº£i thuá»™c vá» giÃ¡o viÃªn nÃ y
        class_obj = self.db.query(Class).filter(
            Class.id == session.class_id
        ).first()
        
        if not class_obj or class_obj.teacher_id != teacher.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Báº¡n khÃ´ng cÃ³ quyá»n vá»›i phiÃªn Ä‘iá»ƒm danh nÃ y"
            )
        
        # 6. Kiá»ƒm tra AI-Service session cÃ²n tá»“n táº¡i khÃ´ng
        ai_session_id = session.ai_session_id
        
        if not ai_session_id:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="PhiÃªn Ä‘iá»ƒm danh khÃ´ng cÃ³ káº¿t ná»‘i AI. Vui lÃ²ng káº¿t thÃºc phiÃªn nÃ y vÃ  táº¡o phiÃªn Ä‘iá»ƒm danh má»›i."
            )
        
        # Kiá»ƒm tra AI session cÃ²n active khÃ´ng
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
                    detail="Káº¿t ná»‘i AI Ä‘Ã£ háº¿t háº¡n hoáº·c khÃ´ng cÃ²n hoáº¡t Ä‘á»™ng. Vui lÃ²ng káº¿t thÃºc phiÃªn nÃ y vÃ  táº¡o phiÃªn Ä‘iá»ƒm danh má»›i."
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
                detail="Káº¿t ná»‘i AI Ä‘Ã£ máº¥t (cÃ³ thá»ƒ do há»‡ thá»‘ng khá»Ÿi Ä‘á»™ng láº¡i). Vui lÃ²ng káº¿t thÃºc phiÃªn nÃ y vÃ  táº¡o phiÃªn Ä‘iá»ƒm danh má»›i."
            )
        
        logger.info(
            f"AI session still active, proceeding with resume",
            extra={
                "session_id": session.id,
                "ai_session_id": ai_session_id
            }
        )
        
        # 7. Generate JWT token má»›i cho WebSocket
        token_expires = timedelta(minutes=settings.AI_WEBSOCKET_TOKEN_EXPIRE_MINUTES)
        ws_token = create_websocket_token(
            user_id=current_user.id,
            session_id=session.id,
            role=current_user.role,
            tenant_slug=tenant_slug,
            expires_delta=token_expires
        )
        
        # 8. Build WebSocket URL for Frontend
        if settings.AI_SERVICE_PUBLIC_URL:
            ai_ws_base = settings.AI_SERVICE_PUBLIC_URL.rstrip('/')
        else:
            # Fallback to internal URL (usually for local dev)
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
        Xá»­ lÃ½ callback tá»« AI-Service khi cÃ³ sinh viÃªn Ä‘Æ°á»£c validate.
        
        Flow:
        1. Verify HMAC signature
        2. TÃ¬m session báº±ng ai_session_id
        3. LÆ°u attendance records (vá»›i idempotency check)
        4. Return response
        
        Args:
            payload: AICallbackPayload
            signature: HMAC signature tá»« header
            
        Returns:
            AICallbackResponse
            
        Raises:
            HTTPException: Náº¿u signature invalid hoáº·c session not found
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
        
        # 2. TÃ¬m session
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
        
        # 3. Process validated students vá»›i confidence threshold logic
        processed_count = 0
        pending_count = 0
        auto_approved_count = 0
        
        for validated_student in payload.validated_students:
            # TÃ¬m student trong class
            student = self.db.query(Student).filter(
                Student.student_code == validated_student.student_code
            ).first()
            
            if not student:
                logger.warning(
                    f"Student not found",
                    extra={"student_code": validated_student.student_code}
                )
                continue
            
            # Idempotency check - khÃ´ng táº¡o duplicate
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
            
            # âœ… HYBRID APPROACH: Kiá»ƒm tra confidence Ä‘á»ƒ quyáº¿t Ä‘á»‹nh status
            confidence = validated_student.avg_confidence
            
            if confidence >= settings.AI_CONFIDENCE_THRESHOLD:
                # Confidence cao â†’ Tá»± Ä‘á»™ng xÃ¡c nháº­n lÃ  PRESENT
                attendance_status = AttendanceStatus.PRESENT
                notes = f"AI-validated (track_id={validated_student.track_id}, frames={validated_student.frame_count}, confidence={confidence:.3f}, auto-approved)"
                auto_approved_count += 1
                logger.info(
                    f"âœ… Auto-approved attendance (high confidence)",
                    extra={
                        "student_code": validated_student.student_code,
                        "confidence": confidence,
                        "threshold": settings.AI_CONFIDENCE_THRESHOLD
                    }
                )
            else:
                # Confidence tháº¥p â†’ Chá» giÃ¡o viÃªn xÃ¡c nháº­n (PENDING)
                attendance_status = AttendanceStatus.PENDING
                notes = f"Pending teacher confirmation (track_id={validated_student.track_id}, frames={validated_student.frame_count}, confidence={confidence:.3f})"
                pending_count += 1
                logger.warning(
                    f"â³ Pending teacher confirmation (low confidence)",
                    extra={
                        "student_code": validated_student.student_code,
                        "confidence": confidence,
                        "threshold": settings.AI_CONFIDENCE_THRESHOLD
                    }
                )
            
            # Táº¡o attendance record (image_path = NULL, sáº½ update sau khi end_session)
            new_record = AttendanceRecord(
                session_id=session.id,
                student_id=student.id,
                status=attendance_status,
                recorded_at=validated_student.validation_passed_at,
                confidence_score=validated_student.avg_confidence,
                image_path=None,  # âš ï¸ CHÆ¯A CÃ“ áº¢NH, sáº½ update sau
                notes=notes
            )
            
            self.db.add(new_record)
            self.db.flush()  # âœ… Flush Ä‘á»ƒ cÃ³ ID ngay (cáº§n cho WebSocket notification)
            
            processed_count += 1
            
            # âœ… Náº¿u PENDING, gá»­i realtime notification qua WebSocket
            if attendance_status == AttendanceStatus.PENDING:
                try:
                    # Import á»Ÿ Ä‘Ã¢y Ä‘á»ƒ trÃ¡nh circular import
                    from app.api.v1.attendance import manager
                    from app.schemas.attendance import WSPendingConfirmation
                    
                    # Broadcast pending confirmation tá»›i giÃ¡o viÃªn trong phiÃªn
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
                                message=f"Sinh viÃªn {student.user.full_name} cáº§n xÃ¡c nháº­n (confidence: {confidence:.1%})"
                            ).model_dump()
                        )
                    )
                    logger.info(f"ðŸ“¢ Sent pending confirmation notification for student {student.student_code}")
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
        Káº¿t thÃºc phiÃªn Ä‘iá»ƒm danh.
        
        Logic:
        1. Kiá»ƒm tra quyá»n
        2. Cáº­p nháº­t status = "finished"
        3. Tá»± Ä‘á»™ng Ä‘Ã¡nh dáº¥u absent náº¿u cáº§n
        4. Tráº£ vá» thá»‘ng kÃª
        
        Args:
            skip_image_upload: Náº¿u True, bá» qua viá»‡c upload áº£nh (Ä‘á»ƒ cháº¡y á»Ÿ background task)
        """
        from app.schemas.attendance import EndSessionResponse
        
        # Kiá»ƒm tra role
        if current_user.role != UserRole.TEACHER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chá»‰ giÃ¡o viÃªn má»›i cÃ³ thá»ƒ káº¿t thÃºc phiÃªn"
            )
        
        # Láº¥y phiÃªn
        session = self.db.query(AttendanceSession).filter(
            AttendanceSession.id == session_id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KhÃ´ng tÃ¬m tháº¥y phiÃªn Ä‘iá»ƒm danh"
            )
        
        # Kiá»ƒm tra quyá»n sá»Ÿ há»¯u
        teacher = self.db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        class_obj = self.db.query(Class).filter(Class.id == session.class_id).first()
        
        if not class_obj or class_obj.teacher_id != teacher.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Báº¡n khÃ´ng cÃ³ quyá»n vá»›i phiÃªn nÃ y"
            )
        
        # Kiá»ƒm tra phiÃªn Ä‘ang ongoing
        if session.status != SessionStatus.ONGOING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PhiÃªn khÃ´ng á»Ÿ tráº¡ng thÃ¡i Ä‘ang diá»…n ra (status: {session.status})"
            )
        
        # Tá»± Ä‘á»™ng Ä‘Ã¡nh dáº¥u absent náº¿u Ä‘Æ°á»£c yÃªu cáº§u
        if request.mark_absent:
            # Láº¥y táº¥t cáº£ sinh viÃªn trong lá»›p
            class_members = self.db.query(ClassMember).filter(
                ClassMember.class_id == session.class_id
            ).all()
            all_student_ids = [member.student_id for member in class_members]
            
            # Láº¥y cÃ¡c sinh viÃªn Ä‘Ã£ Ä‘iá»ƒm danh
            existing_records = self.db.query(AttendanceRecord).filter(
                AttendanceRecord.session_id == session_id
            ).all()
            recorded_student_ids = {record.student_id for record in existing_records}
            
            # TÃ¬m sinh viÃªn chÆ°a Ä‘iá»ƒm danh
            absent_student_ids = [sid for sid in all_student_ids if sid not in recorded_student_ids]
            
            # Táº¡o báº£n ghi absent
            for student_id in absent_student_ids:
                new_record = AttendanceRecord(
                    session_id=session_id,
                    student_id=student_id,
                    status=AttendanceStatus.ABSENT,
                    recorded_at=datetime.now(VIETNAM_TZ)
                )
                self.db.add(new_record)
        
        # Commit Ä‘á»ƒ cÃ³ cÃ¡c báº£n ghi absent
        self.db.commit()
        
        # Xá»­ lÃ½ Ä‘Æ¡n xin nghá»‰ Ä‘Ã£ Ä‘Æ°á»£c cháº¥p nháº­n
        # Láº¥y táº¥t cáº£ records cÃ³ status ABSENT
        absent_records = self.db.query(AttendanceRecord).filter(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.status == AttendanceStatus.ABSENT
        ).all()
        
        if absent_records:
            # Láº¥y thÃ´ng tin vá» ngÃ y vÃ  thá»i gian cá»§a session
            # âœ… FIX: Convert session start_time to Vietnam timezone before extracting date
            session_start_vietnam = session.start_time
            if session_start_vietnam.tzinfo is None:
                # Náº¿u naive datetime, assume UTC vÃ  convert sang Vietnam
                session_start_vietnam = session_start_vietnam.replace(tzinfo=timezone.utc).astimezone(VIETNAM_TZ)
            else:
                # Náº¿u aware datetime, convert sang Vietnam timezone
                session_start_vietnam = session_start_vietnam.astimezone(VIETNAM_TZ)
            
            session_date = session_start_vietnam.date()
            
            # âœ… FIX: Táº¡o range vá»›i timezone-aware datetime Ä‘á»ƒ so sÃ¡nh chÃ­nh xÃ¡c
            # leave_date trong DB cÃ³ thá»ƒ lÆ°u dáº¡ng UTC, cáº§n convert sang Vietnam
            day_start_vietnam = datetime.combine(session_date, datetime.min.time()).replace(tzinfo=VIETNAM_TZ)
            day_end_vietnam = datetime.combine(session_date, datetime.max.time()).replace(tzinfo=VIETNAM_TZ)
            
            # Convert sang UTC Ä‘á»ƒ so sÃ¡nh vá»›i DB (PostgreSQL thÆ°á»ng lÆ°u UTC)
            day_start_utc = day_start_vietnam.astimezone(timezone.utc)
            day_end_utc = day_end_vietnam.astimezone(timezone.utc)
            
            logger.info(
                f"Checking leave requests for session {session_id}: "
                f"session_start_time={session.start_time}, "
                f"session_date_vietnam={session_date}, "
                f"day_start_utc={day_start_utc}, day_end_utc={day_end_utc}"
            )
            
            # TÃ¬m cÃ¡c Ä‘Æ¡n xin nghá»‰ Ä‘Ã£ Ä‘Æ°á»£c cháº¥p nháº­n cho lá»›p nÃ y trong ngÃ y nÃ y
            # So sÃ¡nh vá»›i cáº£ 2 trÆ°á»ng há»£p: leave_date lÆ°u dáº¡ng UTC hoáº·c naive
            from sqlalchemy import or_, func
            approved_leave_requests = self.db.query(LeaveRequest).filter(
                LeaveRequest.class_id == session.class_id,
                LeaveRequest.status == RequestStatus.APPROVED.value,
                LeaveRequest.day_of_week == session.day_of_week,
                or_(
                    # Case 1: leave_date lÃ  UTC aware datetime
                    (LeaveRequest.leave_date >= day_start_utc) & (LeaveRequest.leave_date < day_end_utc),
                    # Case 2: leave_date lÃ  naive datetime (so sÃ¡nh trá»±c tiáº¿p vá»›i Vietnam date)
                    func.date(LeaveRequest.leave_date) == session_date
                )
            ).all()
            
            logger.info(
                f"Found {len(approved_leave_requests)} approved leave requests for class {session.class_id} on {session_date}"
            )
            for lr in approved_leave_requests:
                logger.info(f"  - LeaveRequest ID={lr.id}, student_id={lr.student_id}, leave_date={lr.leave_date}")
            
            approved_by_student: dict[int, list[LeaveRequest]] = {}
            for lr in approved_leave_requests:
                approved_by_student.setdefault(lr.student_id, []).append(lr)
            
            # Cáº­p nháº­t status cho cÃ¡c sinh viÃªn cÃ³ Ä‘Æ¡n Ä‘Æ°á»£c duyá»‡t
            excused_count = 0
            for record in absent_records:
                leave_request = next(
                    (
                        lr for lr in approved_by_student.get(record.student_id, [])
                        if self._periods_overlap(session.period_range, lr.time_slot)
                    ),
                    None,
                )
                if leave_request:
                    record.status = AttendanceStatus.EXCUSED
                    record.notes = f"ÄÃ£ cÃ³ Ä‘Æ¡n xin nghá»‰ Ä‘Æ°á»£c cháº¥p nháº­n (ID: {leave_request.id})"
                    excused_count += 1
                    logger.info(
                        f"Updated student {record.student_id} from ABSENT to EXCUSED "
                        f"based on approved leave request {leave_request.id}"
                    )
        
        # âœ… Gá»ŒI AI SERVICE Láº¤Y áº¢NH VÃ€ UPLOAD LÃŠN S3 (CHá»ˆ Náº¾U KHÃ”NG SKIP)
        # Náº¿u skip_image_upload=True, viá»‡c upload sáº½ Ä‘Æ°á»£c thá»±c hiá»‡n á»Ÿ background task
        if not skip_image_upload and session.ai_session_id:
            try:
                await self._fetch_and_upload_face_images(session)
            except Exception as e:
                logger.error(f"Failed to fetch and upload face images: {e}")
                # Continue without images (khÃ´ng block end_session)
            
            # âœ… Gá»ŒI AI SERVICE Láº¤Y áº¢NH GIáº¢ Máº O VÃ€ UPLOAD LÃŠN S3
            try:
                await self._fetch_and_upload_spoof_images(session)
            except Exception as e:
                logger.error(f"Failed to fetch and upload spoof images: {e}")
                # Continue without spoof images (khÃ´ng block end_session)

            try:
                await ai_service_client.delete_session(session.ai_session_id)
            except Exception as e:
                logger.error(f"Failed to delete AI session: {e}")
                # Continue without blocking end_session
        
        # Cáº­p nháº­t tráº¡ng thÃ¡i phiÃªn
        session.status = SessionStatus.FINISHED.value
        session.end_time = datetime.now(VIETNAM_TZ)
        self.db.commit()
        self.db.refresh(session)
        
        # TÃ­nh thá»‘ng kÃª
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
        pending_count = sum(1 for r in records if r.status == AttendanceStatus.PENDING)  # âœ… NEW
        
        # Chá»‰ tÃ­nh present, khÃ´ng tÃ­nh late vÃ¬ khÃ´ng cÃ³ tráº¡ng thÃ¡i late
        attendance_rate = present_count / total_students * 100 if total_students > 0 else 0
        
        from app.schemas.attendance import SessionResponse
        
        return EndSessionResponse(
            session=SessionResponse.model_validate(session),
            total_students=total_students,
            present_count=present_count,
            absent_count=absent_count,
            excused_count=excused_count,
            pending_count=pending_count,  # âœ… NEW
            attendance_rate=round(attendance_rate, 2)
        )
    
    async def get_session_attendance(
        self,
        current_user: User,
        session_id: int
    ):
        """Láº¥y danh sÃ¡ch Ä‘iá»ƒm danh cá»§a phiÃªn."""
        from app.schemas.attendance import SessionAttendanceListResponse, AttendanceRecordDetail, SessionResponse
        
        # Kiá»ƒm tra quyá»n
        session = self.db.query(AttendanceSession).filter(
            AttendanceSession.id == session_id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KhÃ´ng tÃ¬m tháº¥y phiÃªn Ä‘iá»ƒm danh"
            )
        
        # Kiá»ƒm tra quyá»n truy cáº­p (teacher cá»§a lá»›p hoáº·c student trong lá»›p)
        if current_user.role == UserRole.TEACHER:
            teacher = self.db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
            class_obj = self.db.query(Class).filter(Class.id == session.class_id).first()
            if not class_obj or class_obj.teacher_id != teacher.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Báº¡n khÃ´ng cÃ³ quyá»n truy cáº­p phiÃªn nÃ y"
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
                    detail="Báº¡n khÃ´ng thuá»™c lá»›p nÃ y"
                )
        
        # Láº¥y records
        records = self.db.query(AttendanceRecord).filter(
            AttendanceRecord.session_id == session_id
        ).all()
        
        # Chuyá»ƒn Ä‘á»•i sang schema
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
        
        # TÃ­nh thá»‘ng kÃª
        class_members = self.db.query(ClassMember).filter(
            ClassMember.class_id == session.class_id
        ).all()
        total_students = len(class_members)
        
        present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        excused_count = sum(1 for r in records if r.status == AttendanceStatus.EXCUSED)
        pending_count = sum(1 for r in records if r.status == AttendanceStatus.PENDING)  # âœ… NEW
        
        statistics = {
            "total_students": total_students,
            "present_count": present_count,
            "absent_count": absent_count,
            "excused_count": excused_count,
            "pending_count": pending_count,  # âœ… NEW
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
        Láº¥y danh sÃ¡ch cÃ¡c phiÃªn Ä‘iá»ƒm danh cá»§a lá»›p.
        
        Returns:
            {
                "sessions": [...],
                "total": int
            }
        """
        from app.schemas.attendance import SessionResponse
        
        # Kiá»ƒm tra quyá»n truy cáº­p
        if current_user.role == UserRole.TEACHER:
            teacher = self.db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
            if not teacher:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KhÃ´ng tÃ¬m tháº¥y thÃ´ng tin giÃ¡o viÃªn"
                )
            
            class_obj = self.db.query(Class).filter(Class.id == class_id).first()
            if not class_obj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KhÃ´ng tÃ¬m tháº¥y lá»›p há»c"
                )
            
            if class_obj.teacher_id != teacher.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Báº¡n khÃ´ng cÃ³ quyá»n xem lá»›p nÃ y"
                )
        
        elif current_user.role == UserRole.STUDENT:
            student = self.db.query(Student).filter(Student.user_id == current_user.id).first()
            if not student:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KhÃ´ng tÃ¬m tháº¥y thÃ´ng tin sinh viÃªn"
                )
            
            member = self.db.query(ClassMember).filter(
                ClassMember.class_id == class_id,
                ClassMember.student_id == student.id
            ).first()
            if not member:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Báº¡n khÃ´ng thuá»™c lá»›p nÃ y"
                )
        
        # Build query
        query = self.db.query(AttendanceSession).filter(
            AttendanceSession.class_id == class_id
        )
        
        if status_filter:
            query = query.filter(AttendanceSession.status == status_filter)
        
        # Äáº¿m tá»•ng sá»‘
        total = query.count()
        
        # Láº¥y danh sÃ¡ch phiÃªn
        sessions = query.order_by(AttendanceSession.start_time.desc()).offset(skip).limit(limit).all()
        
        # Chuyá»ƒn Ä‘á»•i sang schema vÃ  thÃªm statistics cho má»—i phiÃªn
        session_responses = []
        for session in sessions:
            # Láº¥y statistics cá»§a phiÃªn
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
            pending_count = sum(1 for r in records if r.status == AttendanceStatus.PENDING)  # âœ… NEW
            
            session_data = SessionResponse.model_validate(session).model_dump()
            session_data["statistics"] = {
                "total_students": total_students,
                "present_count": present_count,
                "absent_count": absent_count,
                "excused_count": excused_count,
                "pending_count": pending_count,  # âœ… NEW
                "attendance_rate": round(present_count / total_students * 100, 2) if total_students > 0 else 0
            }
            session_responses.append(session_data)
        
        return {
            "sessions": session_responses,
            "total": total
        }
    
    async def _fetch_and_upload_face_images(self, session: AttendanceSession):
        """
        Gá»i AI Service láº¥y face crops vÃ  upload lÃªn S3, sau Ä‘Ã³ update image_path cho records.
        
        Args:
            session: AttendanceSession object
        """
        from app.services.file_service import FileService
        
        # Láº¥y teacher_id Ä‘á»ƒ lÃ m uploader_id
        class_obj = self.db.query(Class).filter(Class.id == session.class_id).first()
        teacher = self.db.query(Teacher).filter(Teacher.id == class_obj.teacher_id).first() if class_obj else None
        uploader_id = teacher.user_id if teacher else 1  # Fallback to system user
        
        # Khá»Ÿi táº¡o FileService
        file_service = FileService(self.db)
        
        try:
            # 1. Gá»i AI Service GET /sessions/{ai_session_id}/face-crops
            ai_service_url = f"{settings.AI_SERVICE_URL}/api/v1/sessions/{session.ai_session_id}/face-crops"
            
            # TÄƒng timeout dá»±a trÃªn sá»‘ lÆ°á»£ng sinh viÃªn dá»± kiáº¿n (2s per student)
            # Tá»‘i thiá»ƒu 60s, tá»‘i Ä‘a 300s (5 phÃºt)
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
                
                # 2. Upload tá»«ng áº£nh lÃªn S3 qua FileService vÃ  update DB
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
                        
                        # âœ… Idempotency check: Skip náº¿u Ä‘Ã£ cÃ³ áº£nh
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
                            folder=f"{self.tenant_code}/attendance-evidence",
                            uploader_id=uploader_id,
                            category="attendance_evidence"
                        )
                        
                        # Update attendance record vá»›i file_id (Ä‘á»ƒ cÃ³ thá»ƒ get presigned URL sau)
                        # LÆ°u cáº£ S3 URL cho backward compatibility
                        image_url = file_service.get_file_url(file_record.id)
                        record.image_path = image_url
                        
                        # âœ… Commit ngay sau má»—i record Ä‘á»ƒ trÃ¡nh máº¥t dá»¯ liá»‡u
                        self.db.commit()
                        
                        uploaded_count += 1
                        
                        logger.info(f"âœ… Uploaded face evidence for {student_code}: file_id={file_record.id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to process face crop for {student_code}: {e}")
                        # Rollback transaction hiá»‡n táº¡i náº¿u cÃ³ lá»—i
                        self.db.rollback()
                        continue
                
                logger.info(f"âœ… Uploaded {uploaded_count}/{len(face_crops)} face images to S3 (skipped: {skipped_count})")
                
        except Exception as e:
            logger.error(f"Error in _fetch_and_upload_face_images: {e}")
            raise

    async def _fetch_and_upload_spoof_images(self, session: AttendanceSession):
        """
        Gá»i AI Service láº¥y spoof face crops vÃ  upload lÃªn S3, sau Ä‘Ã³ táº¡o SpoofDetection records.
        
        Args:
            session: AttendanceSession object
        """
        from app.services.file_service import FileService
        from app.models.spoof_detection import SpoofDetection
        
        # Láº¥y teacher_id Ä‘á»ƒ lÃ m uploader_id
        class_obj = self.db.query(Class).filter(Class.id == session.class_id).first()
        teacher = self.db.query(Teacher).filter(Teacher.id == class_obj.teacher_id).first() if class_obj else None
        uploader_id = teacher.user_id if teacher else 1  # Fallback to system user
        
        # Khá»Ÿi táº¡o FileService
        file_service = FileService(self.db)
        
        try:
            # 1. Gá»i AI Service GET /sessions/{ai_session_id}/spoof-faces
            ai_service_url = f"{settings.AI_SERVICE_URL}/api/v1/sessions/{session.ai_session_id}/spoof-faces"
            
            # Timeout 60s cho viá»‡c láº¥y spoof images
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(ai_service_url)
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch spoof faces from AI Service: {response.status_code}")
                    return
                
                data = response.json()
                spoof_faces = data.get("spoof_faces", [])
                
                if not spoof_faces:
                    logger.info(f"No spoof faces detected for session {session.id}")
                    return
                
                logger.info(f"Fetched {len(spoof_faces)} spoof faces from AI Service")
                
                # 2. Upload tá»«ng áº£nh lÃªn S3 qua FileService vÃ  táº¡o SpoofDetection records
                uploaded_count = 0
                
                for idx, spoof_data in enumerate(spoof_faces):
                    face_crop_base64 = spoof_data.get("face_crop_base64")
                    spoofing_type = spoof_data.get("spoofing_type", "spoof")
                    spoofing_confidence = spoof_data.get("spoofing_confidence", 0.0)
                    detected_at_str = spoof_data.get("detected_at")
                    frame_count = spoof_data.get("frame_count")
                    
                    if not face_crop_base64:
                        continue
                    
                    try:
                        # Parse detected_at
                        detected_at = None
                        if detected_at_str:
                            try:
                                detected_at = datetime.fromisoformat(detected_at_str.replace('Z', '+00:00'))
                            except:
                                detected_at = datetime.now(VIETNAM_TZ)
                        else:
                            detected_at = datetime.now(VIETNAM_TZ)
                        
                        # Upload to S3 via FileService
                        timestamp_ms = int(datetime.now().timestamp() * 1000)
                        filename = f"{session.id}/spoof_{idx}_{timestamp_ms}.jpg"
                        
                        file_record = await file_service.upload_base64_and_save(
                            base64_data=face_crop_base64,
                            filename=filename,
                            folder=f"{self.tenant_code}/spoof-detections",
                            uploader_id=uploader_id,
                            category="spoof_detection"
                        )
                        
                        # Get presigned URL
                        image_url = file_service.get_file_url(file_record.id)
                        
                        # Táº¡o SpoofDetection record
                        spoof_record = SpoofDetection(
                            session_id=session.id,
                            spoofing_type=spoofing_type,
                            spoofing_confidence=spoofing_confidence,
                            image_path=image_url,
                            detected_at=detected_at,
                            frame_count=frame_count
                        )
                        
                        self.db.add(spoof_record)
                        self.db.commit()
                        
                        uploaded_count += 1
                        
                        logger.info(f"âœ… Uploaded spoof evidence #{idx}: type={spoofing_type}, confidence={spoofing_confidence:.2f}")
                        
                    except Exception as e:
                        logger.error(f"Failed to process spoof face #{idx}: {e}")
                        self.db.rollback()
                        continue
                
                logger.info(f"âœ… Uploaded {uploaded_count}/{len(spoof_faces)} spoof images to S3")
                
        except Exception as e:
            logger.error(f"Error in _fetch_and_upload_spoof_images: {e}")
            raise

    def get_student_face_image_by_record(self, record_id: int, current_user: User) -> str:
        """
        Láº¥y áº£nh trá»±c diá»‡n cá»§a sinh viÃªn tá»« báº£n ghi Ä‘iá»ƒm danh (presigned S3 URL).
        """
        if current_user.role not in ["teacher", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Quyá»n truy cáº­p bá»‹ tá»« chá»‘i. Chá»‰ GiÃ¡o viÃªn hoáº·c Admin."
            )

        from app.models.attendance_record import AttendanceRecord
        from app.models.face_registration_request import FaceRegistrationRequest
        from app.services.s3_service import s3_service

        # Láº¥y báº£n ghi Ä‘iá»ƒm danh
        record = self.db.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KhÃ´ng tÃ¬m tháº¥y báº£n ghi Ä‘iá»ƒm danh."
            )

        # TÃ¬m Ä‘Æ¡n Ä‘Äƒng kÃ½ khuÃ´n máº·t approved cá»§a sinh viÃªn Ä‘Ã³
        reg = (
            self.db.query(FaceRegistrationRequest)
            .filter(
                FaceRegistrationRequest.student_id == record.student_id,
                FaceRegistrationRequest.status == "approved"
            )
            .order_by(FaceRegistrationRequest.created_at.desc())
            .first()
        )

        if not reg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sinh viên này chưa có đăng ký khuôn mặt được duyệt."
            )

        # Láº¥y file áº£nh trá»±c diá»‡n
        file_key = None
        if reg.evidence_file:
            file_key = reg.evidence_file.file_key
        elif reg.verification_data and "steps" in reg.verification_data:
            # Fallback tÃ¬m trong verification_data JSON
            for step in reg.verification_data["steps"]:
                if step.get("step_name") == "face_front" or step.get("step") == "face_front":
                    file_key = step.get("s3_key")
                    break

        if not file_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KhÃ´ng tÃ¬m tháº¥y áº£nh trá»±c diá»‡n cá»§a sinh viÃªn."
            )

        try:
            presigned_url = s3_service.get_presigned_url(file_key, expires_in=3600)
            return presigned_url
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lá»—i táº¡o link áº£nh S3: {str(e)}"
            )
