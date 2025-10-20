"""Attendance endpoints with WebSocket support for real-time updates."""
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Set
import json

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.attendance import (
    StartSessionRequest,
    SessionResponse,
    EndSessionRequest,
    EndSessionResponse,
    RecognizeFrameRequest,
    RecognizeFrameResponse,
    SessionAttendanceListResponse,
    WSAttendanceUpdate,
    WSSessionStatus
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

@router.post("/sessions/start", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def start_attendance_session(
    request: StartSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Bắt đầu phiên điểm danh mới.
    
    - Chỉ giáo viên có thể bắt đầu phiên
    - Kiểm tra quyền sở hữu lớp
    - Không được có phiên nào đang chạy
    """
    service = AttendanceService(db)
    session = await service.start_session(current_user, request)
    
    # Broadcast thông báo phiên bắt đầu
    await manager.broadcast_to_session(
        session.id,
        WSSessionStatus(
            type="session_status",
            session_id=session.id,
            status="ongoing",
            message="Phiên điểm danh đã bắt đầu"
        ).model_dump()
    )
    
    return session


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
    Nhận diện khuôn mặt từ frame camera.
    
    - Nhận frame dạng base64
    - Gọi AI Service để nhận diện
    - Tự động tạo bản ghi điểm danh
    - Broadcast real-time update qua WebSocket
    """
    service = AttendanceService(db)
    result = await service.recognize_frame(current_user, request)
    
    # Broadcast các sinh viên vừa được nhận diện qua WebSocket
    for student in result.students_recognized:
        await manager.broadcast_to_session(
            request.session_id,
            WSAttendanceUpdate(
                type="attendance_update",
                session_id=request.session_id,
                student=student
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
    Lấy danh sách điểm danh của phiên.
    
    - Giáo viên: Xem tất cả sinh viên
    - Sinh viên: Chỉ xem nếu thuộc lớp
    """
    service = AttendanceService(db)
    return await service.get_session_attendance(current_user, session_id)


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


# ============= Additional Endpoints =============

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

