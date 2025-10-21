"""Attendance repository for database operations."""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from datetime import datetime

from app.repositories.base import BaseRepository
from app.models.attendance_session import AttendanceSession
from app.models.attendance_record import AttendanceRecord
from app.models.class_member import ClassMember
from app.models.student import Student
from app.models.user import User
from app.core.enums import SessionStatus, AttendanceStatus


class AttendanceSessionRepository(BaseRepository[AttendanceSession]):
    """Repository for AttendanceSession operations."""
    
    def __init__(self, db: Session):
        super().__init__(AttendanceSession, db)
    
    def get_ongoing_session_by_class(self, class_id: int) -> Optional[AttendanceSession]:
        """Lấy phiên đang diễn ra của lớp."""
        return self.db.query(AttendanceSession).filter(
            and_(
                AttendanceSession.class_id == class_id,
                AttendanceSession.status == SessionStatus.ONGOING
            )
        ).first()
    
    def get_session_with_records(self, session_id: int) -> Optional[AttendanceSession]:
        """Lấy phiên với các bản ghi điểm danh."""
        return self.db.query(AttendanceSession).options(
            joinedload(AttendanceSession.records).joinedload(AttendanceRecord.student).joinedload(Student.user)
        ).filter(AttendanceSession.id == session_id).first()
    
    def get_sessions_by_class(
        self, 
        class_id: int, 
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[AttendanceSession]:
        """Lấy danh sách phiên của lớp."""
        query = self.db.query(AttendanceSession).filter(
            AttendanceSession.class_id == class_id
        )
        
        if status:
            query = query.filter(AttendanceSession.status == status)
        
        return query.order_by(AttendanceSession.start_time.desc()).offset(skip).limit(limit).all()
    
    def count_sessions_by_class(self, class_id: int, status: Optional[str] = None) -> int:
        """Đếm số phiên của lớp."""
        query = self.db.query(func.count(AttendanceSession.id)).filter(
            AttendanceSession.class_id == class_id
        )
        
        if status:
            query = query.filter(AttendanceSession.status == status)
        
        return query.scalar()


class AttendanceRecordRepository(BaseRepository[AttendanceRecord]):
    """Repository for AttendanceRecord operations."""
    
    def __init__(self, db: Session):
        super().__init__(AttendanceRecord, db)
    
    def get_record_by_session_and_student(
        self, 
        session_id: int, 
        student_id: int
    ) -> Optional[AttendanceRecord]:
        """Lấy bản ghi điểm danh của sinh viên trong phiên."""
        return self.db.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.session_id == session_id,
                AttendanceRecord.student_id == student_id
            )
        ).first()
    
    def get_records_by_session(self, session_id: int) -> List[AttendanceRecord]:
        """Lấy tất cả bản ghi của phiên."""
        return self.db.query(AttendanceRecord).options(
            joinedload(AttendanceRecord.student).joinedload(Student.user)
        ).filter(AttendanceRecord.session_id == session_id).all()
    
    def count_by_session_and_status(self, session_id: int, status: str) -> int:
        """Đếm số bản ghi theo trạng thái trong phiên."""
        return self.db.query(func.count(AttendanceRecord.id)).filter(
            and_(
                AttendanceRecord.session_id == session_id,
                AttendanceRecord.status == status
            )
        ).scalar()
    
    def create_or_update_record(
        self,
        session_id: int,
        student_id: int,
        status: str,
        confidence_score: Optional[float] = None,
        image_path: Optional[str] = None,
        notes: Optional[str] = None
    ) -> AttendanceRecord:
        """Tạo hoặc cập nhật bản ghi điểm danh."""
        existing = self.get_record_by_session_and_student(session_id, student_id)
        
        if existing:
            # Chỉ cập nhật nếu trạng thái hiện tại là absent
            if existing.status == AttendanceStatus.ABSENT:
                existing.status = status
                existing.confidence_score = confidence_score
                existing.recorded_at = datetime.utcnow()
                if image_path:
                    existing.image_path = image_path
                if notes:
                    existing.notes = notes
                self.db.commit()
                self.db.refresh(existing)
            return existing
        else:
            # Tạo mới
            record_data = {
                "session_id": session_id,
                "student_id": student_id,
                "status": status,
                "confidence_score": confidence_score,
                "image_path": image_path,
                "notes": notes,
                "recorded_at": datetime.utcnow()
            }
            return self.create(record_data)
    
    def bulk_create_absent_records(self, session_id: int, student_ids: List[int]) -> int:
        """Tạo hàng loạt bản ghi vắng mặt."""
        records = []
        for student_id in student_ids:
            records.append(AttendanceRecord(
                session_id=session_id,
                student_id=student_id,
                status=AttendanceStatus.ABSENT,
                recorded_at=datetime.utcnow()
            ))
        
        self.db.bulk_save_objects(records)
        self.db.commit()
        return len(records)


class ClassMemberRepository(BaseRepository[ClassMember]):
    """Repository for ClassMember operations."""
    
    def __init__(self, db: Session):
        super().__init__(ClassMember, db)
    
    def get_students_by_class(self, class_id: int) -> List[ClassMember]:
        """Lấy danh sách sinh viên trong lớp."""
        return self.db.query(ClassMember).options(
            joinedload(ClassMember.student).joinedload(Student.user)
        ).filter(ClassMember.class_id == class_id).all()
    
    def get_student_ids_by_class(self, class_id: int) -> List[int]:
        """Lấy danh sách ID sinh viên trong lớp."""
        return [member.student_id for member in self.db.query(ClassMember.student_id).filter(
            ClassMember.class_id == class_id
        ).all()]

