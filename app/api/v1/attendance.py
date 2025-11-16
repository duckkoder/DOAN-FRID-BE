"""Attendance endpoints with AI-Service integration."""
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status, HTTPException, Request, Header
from sqlalchemy.orm import Session
from typing import Dict, Set, Any, Optional
from datetime import datetime
import json

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.attendance_session import AttendanceSession
from app.models.attendance_record import AttendanceRecord
from app.models.student import Student
from app.schemas.attendance import (
    StartSessionRequest,
    SessionResponse,
    EndSessionRequest,
    EndSessionResponse,
    SessionAttendanceListResponse,
    WSAttendanceUpdate,
    WSSessionStatus,
    WSStudentAttendanceUpdate,
    StartSessionWithAIResponse,
    AICallbackPayload,
    AICallbackResponse,
    PendingStudentsResponse,
    PendingStudentDetail,
    ConfirmAttendanceRequest,
    ConfirmAttendanceResponse,
    RejectAttendanceRequest,
    ConfirmAllPendingResponse,
    AttendanceRecordDetail,
    WSPendingConfirmation
)
from app.services.attendance_service import AttendanceService


router = APIRouter(prefix="/attendance", tags=["Attendance"])


# WebSocket Connection Manager
class ConnectionManager:
    """Quản lý kết nối WebSocket cho real-time updates."""
    
    def __init__(self):
        # session_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, session_id: int):
        """Thêm connection vào session."""
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()
        self.active_connections[session_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, session_id: int):
        """Xóa connection khỏi session."""
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)
            # Xóa session nếu không còn connection nào
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
    
    async def broadcast_to_session(self, session_id: int, message: dict):
        """Broadcast message đến tất cả clients trong session."""
        if session_id not in self.active_connections:
            return
        
        # Tạo list để xử lý connections có thể bị đóng
        dead_connections = set()
        
        for connection in self.active_connections[session_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to connection: {e}")
                dead_connections.add(connection)
        
        # Xóa các connections bị lỗi
        for connection in dead_connections:
            self.disconnect(connection, session_id)


# Global connection manager
manager = ConnectionManager()

# Global set để giữ reference của background tasks (tránh bị garbage collected)
background_tasks_set = set()


# ============= Background Task Helper =============

async def upload_images_background_task(session_id: int, ai_session_id: str):
    """
    Background task để upload ảnh điểm danh từ AI Service lên S3.
    Chạy sau khi API đã trả về response để không block UI.
    """
    import logging
    import sys
    from app.core.database import SessionLocal
    from app.services.attendance_service import AttendanceService
    
    # Configure logger với handler để đảm bảo output được hiển thị
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    db = SessionLocal()
    try:
        service = AttendanceService(db)
        session = db.query(AttendanceSession).filter(
            AttendanceSession.id == session_id
        ).first()
        
        if session:
            logger.info(f"Background: Starting image upload for session {session_id}")
            await service._fetch_and_upload_face_images(session)
            logger.info(f"Background: Completed image upload for session {session_id}")
        else:
            logger.warning(f"Background: Session {session_id} not found")
            
    except Exception as e:
        error_msg = f"Background: Failed to upload images for session {session_id}: {e}"
        logger.error(error_msg)
        import traceback
        traceback.print_exc()
    finally:
        db.close()


# ============= REST API Endpoints =============

@router.post("/sessions/start", response_model=StartSessionWithAIResponse, status_code=status.HTTP_201_CREATED)
async def start_attendance_session(
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
    service = AttendanceService(db)
    return await service.start_session_with_ai(current_user, request)


@router.post("/sessions/{session_id}/end", response_model=EndSessionResponse)
async def end_attendance_session(
    session_id: int,
    request: EndSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Kết thúc phiên điểm danh.
    
    - Tự động đánh dấu vắng cho sinh viên chưa điểm danh (nếu mark_absent=True)
    - Upload ảnh được thực hiện ở background (không block UI)
    - Trả về thống kê điểm danh ngay lập tức
    """
    import asyncio
    
    service = AttendanceService(db)
    # Skip image upload trong end_session, sẽ chạy ở background
    result = await service.end_session(current_user, session_id, request, skip_image_upload=True)
    
    # Schedule upload ảnh ở background task (không block response)
    # Dùng asyncio.create_task() để chạy trong background
    if result.session.ai_session_id:
        print(f"Scheduling background image upload for session {session_id}, ai_session_id={result.session.ai_session_id}")
        task = asyncio.create_task(
            upload_images_background_task(
                session_id=session_id,
                ai_session_id=result.session.ai_session_id
            )
        )
        # Giữ reference để task không bị garbage collected
        background_tasks_set.add(task)
        # Remove task khỏi set khi hoàn thành
        task.add_done_callback(background_tasks_set.discard)
        print(f"Background task created and tracked: {task}")
    
    # Broadcast thông báo phiên kết thúc
    await manager.broadcast_to_session(
        session_id,
        WSSessionStatus(
            type="session_status",
            session_id=session_id,
            status="finished",
            message="Phiên điểm danh đã kết thúc"
        ).model_dump()
    )
    
    return result


@router.get("/sessions/{session_id}", response_model=SessionAttendanceListResponse)
async def get_session_attendance(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lấy danh sách điểm danh của phiên - Endpoint cho client polling.
    
    **Use case:**
    - Client poll endpoint này để cập nhật UI realtime
    - Thay thế WebSocket từ backend
    - Chỉ giữ WebSocket với AI-Service để gửi frames
    
    **Returns:**
    - Session info
    - Attendance records với student details
    - Statistics (present/late/absent counts)
    
    **Permissions:**
    - Giáo viên: Xem tất cả sinh viên trong lớp
    - Sinh viên: Chỉ xem nếu thuộc lớp đó
    
    **Polling Strategy:**
    ```javascript
    // Client nên implement smart polling:
    - Start: Poll mỗi 2s
    - Không có update: Tăng interval (exponential backoff) 
    - Max interval: 10s
    - Stop khi session status = "finished"
    ```
    """
    service = AttendanceService(db)
    return await service.get_session_attendance(current_user, session_id)


@router.get("/classes/{class_id}/sessions")
async def get_class_sessions(
    class_id: int,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lấy danh sách các phiên điểm danh của lớp.
    
    - Giáo viên: Xem tất cả phiên của lớp mình dạy
    - Sinh viên: Xem tất cả phiên của lớp mình học
    
    Query params:
    - status: Filter theo trạng thái (ongoing, finished, scheduled)
    - skip: Số phiên bỏ qua (pagination)
    - limit: Số phiên tối đa trả về
    """
    service = AttendanceService(db)
    return await service.get_class_sessions(current_user, class_id, status, skip, limit)


# ============= Webhook Endpoint (AI-Service Callback) =============

@router.post("/webhook/ai-recognition", response_model=AICallbackResponse)
async def ai_recognition_webhook(
    payload: AICallbackPayload,
    request: Request,
    x_ai_signature: Optional[str] = Header(None, alias="X-AI-Signature"),
    db: Session = Depends(get_db)
):
    """
    Webhook endpoint để nhận callback từ AI-Service khi có sinh viên được validate.
    
    **AI-Service gọi endpoint này khi:**
    - Sinh viên pass multi-frame validation
    - Đủ điều kiện: avg_confidence cao, frame_count đủ, recognition_count đủ
    
    **Security:**
    - Verify HMAC-SHA256 signature với shared secret
    - Signature trong header `X-AI-Signature`
    - Reject nếu signature không hợp lệ
    
    **Idempotency:**
    - Không tạo duplicate attendance records
    - Check existing record trước khi insert
    
    **Payload Example:**
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
    
    **Response:**
    ```json
    {
        "status": "ok",
        "processed_students": 1,
        "message": "Processed 1 students successfully"
    }
    ```
    """
    if not x_ai_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-AI-Signature header"
        )
    
    service = AttendanceService(db)
    return await service.handle_ai_callback(payload, x_ai_signature)


# ============= WebSocket Endpoint =============

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: int,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint cho real-time updates.
    
    Khi có sinh viên được điểm danh, server sẽ gửi message:
    {
        "type": "attendance_update",
        "session_id": 123,
        "student": {
            "student_id": 1,
            "student_code": "SV001",
            "full_name": "Nguyễn Văn A",
            "status": "present",
            "confidence_score": 0.95,
            "recorded_at": "2025-10-20T10:30:00"
        }
    }
    
    Khi phiên kết thúc:
    {
        "type": "session_status",
        "session_id": 123,
        "status": "finished",
        "message": "Phiên điểm danh đã kết thúc"
    }
    """
    # TODO: Có thể thêm authentication cho WebSocket nếu cần
    # Hiện tại accept tất cả connections
    
    await manager.connect(websocket, session_id)
    
    try:
        # Gửi message chào mừng
        await websocket.send_json({
            "type": "connection",
            "message": f"Connected to session {session_id}",
            "session_id": session_id
        })
        
        # Keep connection alive và nhận messages từ client (nếu cần)
        while True:
            data = await websocket.receive_text()
            # Client có thể gửi ping/pong để keep alive
            if data == "ping":
                await websocket.send_text("pong")
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket, session_id)


# ============= Student API - Real-time Attendance View =============

@router.get("/classes/{class_id}/current-session-attendance")
async def get_current_session_attendance_for_student(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sinh viên xem danh sách điểm danh realtime của cả lớp.
    
    Returns:
        - has_active_session: bool
        - session: Session info nếu có
        - students: Danh sách tất cả sinh viên với trạng thái điểm danh
        - my_student_id: ID sinh viên của user hiện tại
    """
    from app.models.class_member import ClassMember
    
    # 1. Verify student is in this class
    student = db.query(Student).filter(
        Student.user_id == current_user.id
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không phải là sinh viên"
        )
    
    # Check if student is enrolled in this class
    enrollment = db.query(ClassMember).filter(
        ClassMember.class_id == class_id,
        ClassMember.student_id == student.id
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không thuộc lớp học này"
        )
    
    # 2. Find active session
    session = db.query(AttendanceSession).filter(
        AttendanceSession.class_id == class_id,
        AttendanceSession.status == "ongoing"
    ).first()
    
    if not session:
        return {
            "has_active_session": False,
            "session": None,
            "students": [],
            "my_student_id": student.id
        }
    
    # 3. Get all students in this class with user info (eager loading to avoid N+1)
    from sqlalchemy.orm import joinedload
    
    class_members = db.query(ClassMember).filter(
        ClassMember.class_id == class_id
    ).all()
    
    # Get all students with their user info in one query
    student_ids = [member.student_id for member in class_members]
    students_in_class = db.query(Student).options(
        joinedload(Student.user)
    ).filter(
        Student.id.in_(student_ids)
    ).all()
    
    # Create student map for quick lookup
    student_map = {s.id: s for s in students_in_class}
    
    # 4. Get attendance records for this session
    attendance_records = db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session.id
    ).all()
    
    # Create a map of student_id -> attendance_record
    attendance_map = {record.student_id: record for record in attendance_records}
    
    # 5. Build student list with attendance status
    students_data = []
    for member in class_members:
        member_student = student_map.get(member.student_id)
        
        if not member_student or not member_student.user:
            continue
        
        attendance_record = attendance_map.get(member.student_id)
        
        # Get full name from user (User model only has full_name, not first_name/last_name)
        user = member_student.user
        full_name = user.full_name if user.full_name else user.email
        
        students_data.append({
            "student_id": member_student.id,
            "student_code": member_student.student_code,
            "full_name": full_name,
            "is_present": attendance_record is not None,
            "status": attendance_record.status if attendance_record else None,
            "recorded_at": attendance_record.recorded_at.isoformat() if attendance_record and attendance_record.recorded_at else None,
            "confidence_score": attendance_record.confidence_score if attendance_record else None
        })
    
    # Sort: attended first, then by name
    students_data.sort(key=lambda x: (not x["is_present"], x["full_name"]))
    
    return {
        "has_active_session": True,
        "session": {
            "id": session.id,
            "session_name": session.session_name,
            "start_time": session.start_time.isoformat() if session.start_time else None,
            "status": session.status
        },
        "students": students_data,
        "my_student_id": student.id,
        "stats": {
            "total_students": len(students_data),
            "present_count": sum(1 for s in students_data if s["is_present"]),
            "absent_count": sum(1 for s in students_data if not s["is_present"])
        }
    }


# ============= Teacher Confirmation APIs (Hybrid Approach) =============

@router.get("/sessions/{session_id}/pending-students", response_model=PendingStudentsResponse)
async def get_pending_students(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lấy danh sách sinh viên chờ xác nhận (status = PENDING).
    
    **Chỉ giáo viên của lớp mới có quyền truy cập.**
    
    Returns:
        - pending_count: Số lượng sinh viên chờ xác nhận
        - students: Danh sách sinh viên với thông tin chi tiết
    """
    from app.core.enums import UserRole, AttendanceStatus
    from app.models.teacher import Teacher
    from app.models.class_model import Class
    
    # Kiểm tra role
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ giáo viên mới có thể xem danh sách chờ xác nhận"
        )
    
    # Kiểm tra quyền sở hữu session
    session = db.query(AttendanceSession).filter(
        AttendanceSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phiên điểm danh"
        )
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    class_obj = db.query(Class).filter(Class.id == session.class_id).first()
    
    if not class_obj or class_obj.teacher_id != teacher.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền với phiên này"
        )
    
    # Lấy các record có status = PENDING
    pending_records = db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session_id,
        AttendanceRecord.status == AttendanceStatus.PENDING
    ).all()
    
    students = [
        PendingStudentDetail(
            record_id=record.id,
            student_id=record.student_id,
            student_code=record.student.student_code,
            full_name=record.student.user.full_name,
            confidence_score=record.confidence_score,
            recorded_at=record.recorded_at
        )
        for record in pending_records
    ]
    
    return PendingStudentsResponse(
        pending_count=len(students),
        students=students
    )


@router.post("/records/{record_id}/confirm", response_model=ConfirmAttendanceResponse)
async def confirm_attendance(
    record_id: int,
    request: ConfirmAttendanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Xác nhận điểm danh cho một sinh viên (chuyển từ PENDING → PRESENT).
    
    **Chỉ giáo viên của lớp mới có quyền.**
    
    Body:
        - status: "present" (mặc định)
        - notes: Ghi chú (tùy chọn)
    """
    from app.core.enums import UserRole, AttendanceStatus
    from app.models.teacher import Teacher
    from app.models.class_model import Class
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    VIETNAM_TZ = ZoneInfo('Asia/Ho_Chi_Minh')
    
    # Kiểm tra role
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ giáo viên mới có thể xác nhận điểm danh"
        )
    
    # Lấy record
    record = db.query(AttendanceRecord).filter(
        AttendanceRecord.id == record_id
    ).first()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bản ghi điểm danh"
        )
    
    # Kiểm tra quyền sở hữu
    session = db.query(AttendanceSession).filter(
        AttendanceSession.id == record.session_id
    ).first()
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    class_obj = db.query(Class).filter(Class.id == session.class_id).first()
    
    if not class_obj or class_obj.teacher_id != teacher.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền với phiên này"
        )
    
    # Kiểm tra status hiện tại
    if record.status != AttendanceStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bản ghi không ở trạng thái chờ xác nhận (status: {record.status})"
        )
    
    # Cập nhật status
    record.status = AttendanceStatus.PRESENT
    if request.notes:
        existing_notes = record.notes or ""
        record.notes = f"{existing_notes} | Teacher confirmed: {request.notes}"
    else:
        existing_notes = record.notes or ""
        record.notes = f"{existing_notes} | Teacher confirmed"
    
    record.updated_at = datetime.now(VIETNAM_TZ)
    
    db.commit()
    db.refresh(record)
    
    # Broadcast confirmation update qua WebSocket
    await manager.broadcast_to_session(
        session.id,
        {
            "type": "confirmation_update",
            "session_id": session.id,
            "student_id": record.student_id,
            "student_code": record.student.student_code,
            "full_name": record.student.user.full_name,
            "status": "present",
            "confirmed_by": teacher.user.full_name,
            "confirmed_at": datetime.now(VIETNAM_TZ).isoformat()
        }
    )
    
    return ConfirmAttendanceResponse(
        success=True,
        record=AttendanceRecordDetail(
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
    )


@router.post("/records/{record_id}/reject", response_model=ConfirmAttendanceResponse)
async def reject_attendance(
    record_id: int,
    request: RejectAttendanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Từ chối điểm danh (chuyển từ PENDING → ABSENT).
    
    **Chỉ giáo viên của lớp mới có quyền.**
    
    Body:
        - reason: Lý do từ chối (tùy chọn)
    """
    from app.core.enums import UserRole, AttendanceStatus
    from app.models.teacher import Teacher
    from app.models.class_model import Class
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    VIETNAM_TZ = ZoneInfo('Asia/Ho_Chi_Minh')
    
    # Kiểm tra role
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ giáo viên mới có thể từ chối điểm danh"
        )
    
    # Lấy record
    record = db.query(AttendanceRecord).filter(
        AttendanceRecord.id == record_id
    ).first()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bản ghi điểm danh"
        )
    
    # Kiểm tra quyền sở hữu
    session = db.query(AttendanceSession).filter(
        AttendanceSession.id == record.session_id
    ).first()
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    class_obj = db.query(Class).filter(Class.id == session.class_id).first()
    
    if not class_obj or class_obj.teacher_id != teacher.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền với phiên này"
        )
    
    # Kiểm tra status hiện tại
    if record.status != AttendanceStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bản ghi không ở trạng thái chờ xác nhận (status: {record.status})"
        )
    
    # Chuyển sang ABSENT
    record.status = AttendanceStatus.ABSENT
    if request.reason:
        existing_notes = record.notes or ""
        record.notes = f"{existing_notes} | Teacher rejected: {request.reason}"
    else:
        existing_notes = record.notes or ""
        record.notes = f"{existing_notes} | Teacher rejected (wrong recognition)"
    
    record.updated_at = datetime.now(VIETNAM_TZ)
    
    db.commit()
    db.refresh(record)
    
    # Broadcast rejection update qua WebSocket
    await manager.broadcast_to_session(
        session.id,
        {
            "type": "confirmation_update",
            "session_id": session.id,
            "student_id": record.student_id,
            "student_code": record.student.student_code,
            "full_name": record.student.user.full_name,
            "status": "absent",
            "confirmed_by": teacher.user.full_name,
            "confirmed_at": datetime.now(VIETNAM_TZ).isoformat()
        }
    )
    
    return ConfirmAttendanceResponse(
        success=True,
        record=AttendanceRecordDetail(
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
    )


@router.post("/sessions/{session_id}/confirm-all-pending", response_model=ConfirmAllPendingResponse)
async def confirm_all_pending(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Xác nhận tất cả sinh viên chờ xác nhận trong phiên (chuyển tất cả PENDING → PRESENT).
    
    **Chỉ giáo viên của lớp mới có quyền.**
    
    Use case: Khi giáo viên tin tưởng vào kết quả AI và muốn xác nhận hàng loạt.
    """
    from app.core.enums import UserRole, AttendanceStatus
    from app.models.teacher import Teacher
    from app.models.class_model import Class
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    VIETNAM_TZ = ZoneInfo('Asia/Ho_Chi_Minh')
    
    # Kiểm tra role
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ giáo viên mới có thể xác nhận điểm danh"
        )
    
    # Kiểm tra quyền sở hữu session
    session = db.query(AttendanceSession).filter(
        AttendanceSession.id == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phiên điểm danh"
        )
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    class_obj = db.query(Class).filter(Class.id == session.class_id).first()
    
    if not class_obj or class_obj.teacher_id != teacher.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền với phiên này"
        )
    
    # Lấy tất cả records có status = PENDING
    pending_records = db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session_id,
        AttendanceRecord.status == AttendanceStatus.PENDING
    ).all()
    
    # Cập nhật tất cả
    for record in pending_records:
        record.status = AttendanceStatus.PRESENT
        existing_notes = record.notes or ""
        record.notes = f"{existing_notes} | Teacher confirmed (bulk)"
        record.updated_at = datetime.now(VIETNAM_TZ)
    
    db.commit()
    
    # Refresh để lấy dữ liệu mới
    for record in pending_records:
        db.refresh(record)
    
    # Broadcast bulk confirmation
    await manager.broadcast_to_session(
        session_id,
        {
            "type": "bulk_confirmation",
            "session_id": session_id,
            "confirmed_count": len(pending_records),
            "message": f"Giáo viên đã xác nhận {len(pending_records)} sinh viên"
        }
    )
    
    return ConfirmAllPendingResponse(
        success=True,
        confirmed_count=len(pending_records),
        records=[
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
            for record in pending_records
        ]
    )


