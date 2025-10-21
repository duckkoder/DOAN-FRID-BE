"""Attendance service with business logic and AI service integration."""
import httpx
import base64
import time
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.repositories.attendance_repository import (
    AttendanceSessionRepository,
    AttendanceRecordRepository,
    ClassMemberRepository
)
from app.models.user import User
from app.models.class_model import Class
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.class_member import ClassMember
from app.core.enums import SessionStatus, AttendanceStatus, UserRole
from app.core.config import settings
from app.schemas.attendance import (
    StartSessionRequest,
    SessionResponse,
    EndSessionRequest,
    EndSessionResponse,
    RecognizeFrameRequest,
    RecognizeFrameResponse,
    RecognizedStudent,
    DetectionInfo,
    AttendanceRecordDetail,
    SessionAttendanceListResponse
)


class AttendanceService:
    """Service xử lý logic điểm danh."""
    
    def __init__(self, db: Session):
        self.db = db
        self.session_repo = AttendanceSessionRepository(db)
        self.record_repo = AttendanceRecordRepository(db)
        self.member_repo = ClassMemberRepository(db)
    
    async def start_session(
        self, 
        current_user: User, 
        request: StartSessionRequest
    ) -> SessionResponse:
        """
        Bắt đầu phiên điểm danh.
        
        Logic:
        1. Kiểm tra user là giáo viên
        2. Kiểm tra quyền sở hữu lớp
        3. Kiểm tra không có phiên nào đang chạy
        4. Tạo phiên mới với status="ongoing"
        """
        # Kiểm tra role
        if current_user.role != UserRole.TEACHER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ giáo viên mới có thể bắt đầu phiên điểm danh"
            )
        
        # Lấy thông tin giáo viên
        teacher = self.db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy thông tin giáo viên"
            )
        
        # Kiểm tra lớp tồn tại và thuộc sở hữu
        class_obj = self.db.query(Class).filter(Class.id == request.class_id).first()
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
        
        # Kiểm tra không có phiên nào đang chạy
        ongoing_session = self.session_repo.get_ongoing_session_by_class(request.class_id)
        if ongoing_session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lớp đang có phiên điểm danh đang diễn ra (ID: {ongoing_session.id})"
            )
        
        # Tạo phiên mới
        session_data = {
            "class_id": request.class_id,
            "session_name": request.session_name or f"Điểm danh {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "start_time": datetime.utcnow(),
            "status": SessionStatus.ONGOING,
            "late_threshold_minutes": request.late_threshold_minutes,
            "location": request.location,
            "allow_late_checkin": True
        }
        
        new_session = self.session_repo.create(session_data)
        
        return SessionResponse.model_validate(new_session)
    
    async def end_session(
        self,
        current_user: User,
        session_id: int,
        request: EndSessionRequest
    ) -> EndSessionResponse:
        """
        Kết thúc phiên điểm danh.
        
        Logic:
        1. Kiểm tra quyền
        2. Cập nhật status = "finished"
        3. Tự động đánh dấu absent nếu cần
        4. Trả về thống kê
        """
        # Kiểm tra role
        if current_user.role != UserRole.TEACHER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ giáo viên mới có thể kết thúc phiên"
            )
        
        # Lấy phiên
        session = self.session_repo.get(session_id)
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
        if session.status != SessionStatus.ONGOING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Phiên không ở trạng thái đang diễn ra (status: {session.status})"
            )
        
        # Tự động đánh dấu absent nếu được yêu cầu
        if request.mark_absent:
            # Lấy tất cả sinh viên trong lớp
            all_student_ids = self.member_repo.get_student_ids_by_class(session.class_id)
            
            # Lấy các sinh viên đã điểm danh
            existing_records = self.record_repo.get_records_by_session(session_id)
            recorded_student_ids = {record.student_id for record in existing_records}
            
            # Tìm sinh viên chưa điểm danh
            absent_student_ids = [sid for sid in all_student_ids if sid not in recorded_student_ids]
            
            # Tạo bản ghi absent
            if absent_student_ids:
                self.record_repo.bulk_create_absent_records(session_id, absent_student_ids)
        
        # Cập nhật trạng thái phiên
        session.status = SessionStatus.FINISHED
        session.end_time = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)
        
        # Tính thống kê
        total_students = len(self.member_repo.get_student_ids_by_class(session.class_id))
        present_count = self.record_repo.count_by_session_and_status(session_id, AttendanceStatus.PRESENT)
        late_count = self.record_repo.count_by_session_and_status(session_id, AttendanceStatus.LATE)
        absent_count = self.record_repo.count_by_session_and_status(session_id, AttendanceStatus.ABSENT)
        
        attendance_rate = (present_count + late_count) / total_students * 100 if total_students > 0 else 0
        
        return EndSessionResponse(
            session=SessionResponse.model_validate(session),
            total_students=total_students,
            present_count=present_count,
            late_count=late_count,
            absent_count=absent_count,
            attendance_rate=round(attendance_rate, 2)
        )
    
    async def recognize_frame(
        self,
        current_user: User,
        request: RecognizeFrameRequest
    ) -> RecognizeFrameResponse:
        """
        Nhận diện khuôn mặt từ frame camera.
        
        Logic:
        1. Kiểm tra quyền và phiên hợp lệ
        2. Gọi AI Service để nhận diện
        3. Map person_name -> student_id
        4. Tạo/cập nhật attendance_records
        5. Trả về danh sách sinh viên được nhận diện
        """
        start_time = time.time()
        
        # Kiểm tra role
        if current_user.role != UserRole.TEACHER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ giáo viên mới có thể nhận diện"
            )
        
        # Lấy phiên
        session = self.session_repo.get(request.session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy phiên điểm danh"
            )
        
        # Kiểm tra phiên đang ongoing
        if session.status != SessionStatus.ONGOING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phiên không ở trạng thái đang diễn ra"
            )
        
        # Kiểm tra quyền sở hữu
        teacher = self.db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        class_obj = self.db.query(Class).filter(Class.id == session.class_id).first()
        
        if not class_obj or class_obj.teacher_id != teacher.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền với phiên này"
            )
        
        # Gọi AI Service
        ai_result = await self._call_ai_service(request.image_base64)
        
        # Lấy danh sách sinh viên trong lớp
        class_members = self.member_repo.get_students_by_class(session.class_id)
        student_map = {
            member.student.student_code: member.student  # Map student_code -> Student
            for member in class_members
        }
        
        # DEBUG: Log để kiểm tra
        print(f"[DEBUG] AI Service returned {len(ai_result.get('faces', []))} faces")
        print(f"[DEBUG] Students in class: {list(student_map.keys())}")
        
        # Xử lý kết quả nhận diện
        recognized_students = []
        detections_info = []  # Thêm list để lưu thông tin detections
        
        for face in ai_result.get("faces", []):
            print(f"[DEBUG] Processing face: person_name={face.get('person_name')}, confidence={face.get('recognition_confidence')}")
            person_name = face.get("person_name")
            recognition_confidence = face.get("recognition_confidence")
            bbox = face.get("bbox", [])
            detection_confidence = face.get("confidence", 0.0)
            
            # Kiểm tra xem có phải sinh viên trong lớp không
            student = None
            if person_name and person_name != "Unknown":
                student = student_map.get(person_name)
            
            # Tạo detection info
            if student:
                # Trường hợp 1: Sinh viên TRONG lớp
                print(f"[DEBUG] Student FOUND: {student.student_code} - {student.user.full_name}")
                detection = DetectionInfo(
                    bbox=bbox,
                    confidence=detection_confidence,
                    track_id=face.get("track_id"),
                    student_id=str(student.id),
                    student_code=student.student_code,
                    student_name=student.user.full_name,
                    recognition_confidence=recognition_confidence
                )
            else:
                # Trường hợp 2: Unknown (bao gồm cả người không trong lớp)
                print(f"[DEBUG] Unknown face: person_name={person_name}")
                detection = DetectionInfo(
                    bbox=bbox,
                    confidence=detection_confidence,
                    track_id=face.get("track_id"),
                    student_id=None,
                    student_code=None,
                    student_name="Unknown",
                    recognition_confidence=recognition_confidence
                )
            
            detections_info.append(detection)
            
            # Chỉ xử lý attendance nếu là sinh viên trong lớp
            if not student:
                continue
            
            # Kiểm tra xem sinh viên đã được điểm danh chưa
            existing_record = self.record_repo.get_record_by_session_and_student(
                session.id, student.id
            )
            
            # Chỉ xử lý nếu chưa điểm danh hoặc đang absent
            if not existing_record or existing_record.status == AttendanceStatus.ABSENT:
                # Xác định trạng thái (present/late)
                status = self._determine_status(session)
                
                # Tạo/cập nhật bản ghi
                record = self.record_repo.create_or_update_record(
                    session_id=session.id,
                    student_id=student.id,
                    status=status,
                    confidence_score=recognition_confidence,
                    notes=f"Nhận diện tự động (confidence: {recognition_confidence:.2f})"
                )
                
                # Thêm vào danh sách kết quả
                recognized_students.append(RecognizedStudent(
                    student_id=student.id,
                    student_code=student.student_code,
                    full_name=student.user.full_name,
                    status=status,
                    confidence_score=recognition_confidence or 0.0,
                    recorded_at=record.recorded_at
                ))
        
        processing_time = (time.time() - start_time) * 1000
        
        return RecognizeFrameResponse(
            success=True,
            message=f"Nhận diện thành công {len(recognized_students)}/{ai_result.get('total_faces', 0)} khuôn mặt",
            total_faces_detected=ai_result.get("total_faces", 0),
            students_recognized=recognized_students,
            processing_time_ms=round(processing_time, 2),
            detections=detections_info  # Thêm thông tin detections vào response
        )
    
    async def get_session_attendance(
        self,
        current_user: User,
        session_id: int
    ) -> SessionAttendanceListResponse:
        """Lấy danh sách điểm danh của phiên."""
        # Kiểm tra quyền
        session = self.session_repo.get(session_id)
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
        records = self.record_repo.get_records_by_session(session_id)
        
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
        total_students = len(self.member_repo.get_student_ids_by_class(session.class_id))
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
    ) -> Dict[str, Any]:
        """
        Lấy danh sách các phiên điểm danh của lớp.
        
        Returns:
            {
                "sessions": [...],
                "total": int
            }
        """
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
        
        # Lấy danh sách phiên
        sessions = self.session_repo.get_sessions_by_class(
            class_id=class_id,
            status=status_filter,
            skip=skip,
            limit=limit
        )
        
        # Đếm tổng số phiên
        total = self.session_repo.count_sessions_by_class(
            class_id=class_id,
            status=status_filter
        )
        
        # Chuyển đổi sang schema và thêm statistics cho mỗi phiên
        session_responses = []
        for session in sessions:
            # Lấy statistics của phiên
            records = self.record_repo.get_records_by_session(session.id)
            total_students = len(self.member_repo.get_student_ids_by_class(session.class_id))
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
    
    # ============= Helper Methods =============
    
    def _determine_status(self, session) -> str:
        """Xác định trạng thái điểm danh dựa vào thời gian."""
        now = datetime.utcnow()
        late_threshold = session.start_time + timedelta(minutes=session.late_threshold_minutes)
        
        if now <= late_threshold:
            return AttendanceStatus.PRESENT
        else:
            return AttendanceStatus.LATE
    
    async def _call_ai_service(self, image_base64: str) -> Dict[str, Any]:
        """
        Gọi AI Service để nhận diện khuôn mặt.
        
        Returns:
            {
                "total_faces": int,
                "recognized_count": int,
                "faces": [
                    {
                        "bbox": [x1, y1, x2, y2],
                        "confidence": float,
                        "person_name": str,
                        "recognition_confidence": float
                    }
                ],
                "processing_time_ms": float
            }
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.AI_SERVICE_URL}/api/v1/detect",
                    json={"image_base64": image_base64}
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"AI Service error: {response.text}"
                    )
                
                return response.json()
        
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="AI Service timeout"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cannot connect to AI Service: {str(e)}"
            )

