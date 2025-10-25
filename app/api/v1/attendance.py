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
    RecognizeFrameRequest,
    RecognizeFrameResponse,
    SessionAttendanceListResponse,
    WSAttendanceUpdate,
    WSSessionStatus,
    StudentCurrentSessionResponse,
    WSStudentAttendanceUpdate,
    StartSessionWithAIResponse,
    AICallbackPayload,
    AICallbackResponse
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
    - Trả về thống kê điểm danh
    """
    service = AttendanceService(db)
    result = await service.end_session(current_user, session_id, request)
    
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


@router.post("/recognize-frame", response_model=RecognizeFrameResponse)
async def recognize_frame(
    request: RecognizeFrameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    [DEPRECATED] Nhận diện khuôn mặt từ frame camera (HTTP - Legacy).
    
    ⚠️ Endpoint này đã deprecated. Vui lòng sử dụng WebSocket endpoint thay thế:
    - POST /sessions/start → Nhận WebSocket URL
    - Connect WebSocket → Gửi frames real-time
    
    Endpoint này sẽ bị xóa trong phiên bản tương lai.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="This endpoint is deprecated. Please use WebSocket for real-time face recognition."
    )


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

@router.get("/classes/{class_id}/current-session", response_model=StudentCurrentSessionResponse)
async def get_current_session_for_student(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    [DEPRECATED] Use /current-session-attendance instead.
    
    Sinh viên check xem lớp có phiên điểm danh đang diễn ra không.
    Kèm theo trạng thái điểm danh của sinh viên đó.
    
    Returns:
        - has_active_session: bool
        - session: Session info nếu có
        - my_status: Trạng thái điểm danh của sinh viên
    """
    # 1. Tìm session đang ongoing
    session = db.query(AttendanceSession).filter(
        AttendanceSession.class_id == class_id,
        AttendanceSession.status == "ongoing"
    ).first()
    
    if not session:
        return StudentCurrentSessionResponse(
            has_active_session=False,
            session=None,
            my_status=None
        )
    
    # 2. Lấy thông tin student từ user
    student = db.query(Student).filter(
        Student.user_id == current_user.id
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không phải là sinh viên"
        )
    
    # 3. Check xem sinh viên đã điểm danh chưa
    attendance_record = db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session.id,
        AttendanceRecord.student_id == student.id
    ).first()
    
    my_status = None
    if attendance_record:
        from app.schemas.attendance import StudentAttendanceStatus
        my_status = StudentAttendanceStatus(
            is_present=attendance_record.status in ["present", "late"],
            status=attendance_record.status,
            recorded_at=attendance_record.recorded_at,
            confidence_score=attendance_record.confidence_score
        )
    
    # 4. Return response
    return StudentCurrentSessionResponse(
        has_active_session=True,
        session=SessionResponse.from_orm(session),
        my_status=my_status
    )


# ============= Additional Endpoints =============

# ============= Additional Endpoints =============

@router.post("/webhook/ai-recognition", status_code=status.HTTP_200_OK)
async def ai_recognition_webhook(
    request: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Webhook endpoint for AI service to send recognition results.
    
    Request body:
    {
        "session_id": "string",
        "class_id": int,
        "recognized_students": [student_id1, student_id2, ...],
        "timestamp": "ISO datetime string",
        "total_faces_detected": int
    }
    
    This endpoint:
    1. Validates the session exists
    2. Creates attendance records for recognized students
    3. Broadcasts updates via WebSocket to connected clients
    """
    try:
        # Extract data from request
        session_id_str = request.get("session_id")
        class_id = request.get("class_id")
        recognized_students = request.get("recognized_students", [])
        timestamp = request.get("timestamp")
        
        # Parse session_id (format: "class_{class_id}_session_{session_id}")
        # Extract numeric session_id
        import re
        match = re.search(r'session_(\d+)', session_id_str)
        if not match:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session_id format"
            )
        session_id = int(match.group(1))
        
        # Verify session exists and is ongoing
        session = db.query(AttendanceSession).filter(
            AttendanceSession.id == session_id,
            AttendanceSession.class_id == class_id,
            AttendanceSession.status == "ongoing"
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or not active"
            )
        
        # Process each recognized student
        newly_recorded = []
        for student_id in recognized_students:
            # Check if already recorded
            existing_record = db.query(AttendanceRecord).filter(
                AttendanceRecord.session_id == session_id,
                AttendanceRecord.student_id == student_id
            ).first()
            
            if existing_record:
                continue  # Skip already recorded students
            
            # Create new attendance record
            new_record = AttendanceRecord(
                session_id=session_id,
                student_id=student_id,
                status="present",
                recorded_at=datetime.utcnow(),
                confidence_score=0.85  # Default confidence
            )
            db.add(new_record)
            newly_recorded.append(student_id)
        
        # Commit all new records
        if newly_recorded:
            db.commit()
            
            # Broadcast updates via WebSocket
            for student_id in newly_recorded:
                # Get student info
                student = db.query(Student).filter(Student.id == student_id).first()
                if not student:
                    continue
                
                # Get the attendance record we just created
                record = db.query(AttendanceRecord).filter(
                    AttendanceRecord.session_id == session_id,
                    AttendanceRecord.student_id == student_id
                ).first()
                
                # Broadcast to session (for teacher view)
                await manager.broadcast_to_session(
                    session_id,
                    {
                        "type": "attendance_update",
                        "session_id": session_id,
                        "student": {
                            "student_id": student.id,
                            "student_code": student.student_code,
                            "full_name": f"{student.first_name} {student.last_name}",
                            "status": record.status,
                            "confidence_score": record.confidence_score,
                            "recorded_at": record.recorded_at.isoformat() if record.recorded_at else None
                        }
                    }
                )
                
                # ✅ NEW: Broadcast student-specific update
                # This message will be picked up by the student's WebSocket connection
                student_message = WSStudentAttendanceUpdate(
                    type="student_attendance_update",
                    session_id=session_id,
                    student_id=student.id,
                    status=record.status,
                    recorded_at=record.recorded_at.isoformat() if record.recorded_at else None,
                    confidence_score=record.confidence_score,
                    message=f"✅ Bạn đã được điểm danh thành công lúc {record.recorded_at.strftime('%H:%M:%S') if record.recorded_at else 'N/A'}"
                )
                
                await manager.broadcast_to_session(
                    session_id,
                    student_message.model_dump()
                )
        
        return {
            "success": True,
            "message": f"Processed {len(newly_recorded)} new attendance records",
            "newly_recorded": newly_recorded
        }
        
    except Exception as e:
        print(f"Error in AI recognition webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process recognition results: {str(e)}"
        )


@router.get("/sessions")
async def get_sessions(
    class_id: int = None,
    status: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lấy danh sách phiên điểm danh.
    
    - Filter theo class_id và status
    - Hỗ trợ pagination
    """
    # TODO: Implement logic lấy danh sách phiên với quyền phù hợp
    pass

