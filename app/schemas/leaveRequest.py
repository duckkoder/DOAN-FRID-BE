from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class CreateLeaveRequestRequest(BaseModel):
    """Request to create a leave request."""
    class_id: int = Field(..., description="Class ID")
    reason: str = Field(..., min_length=10, max_length=1000, description="Reason for leave")
    leave_date: datetime = Field(..., description="Date of leave (YYYY-MM-DD)")
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week as integer: 0=Monday, 1=Tuesday, ..., 6=Sunday")
    time_slot: str = Field(..., description="Time slot in format 'x-y' where x,y are 1-10 (e.g., '1-3', '4-4')")
    evidence_file_id: Optional[int] = Field(None, description="ID of uploaded evidence file")
    
    @field_validator('time_slot')
    @classmethod
    def validate_time_slot(cls, v):
        """Validate time slot format: 'x-y' or 'x' where x,y are 1-10. Normalizes 'x' to 'x-x'."""
        import re
        if not v:
            raise ValueError("time_slot is required")
        
        # Allow single number 'x' -> normalize to 'x-x'
        single_pattern = r'^(\d+)$'
        single_match = re.match(single_pattern, v)
        if single_match:
            n = int(single_match.group(1))
            if n < 1 or n > 10:
                raise ValueError("time_slot period must be between 1 and 10")
            return f"{n}-{n}"
        
        # Check format x-y
        pattern = r'^(\d+)-(\d+)$'
        match = re.match(pattern, v)
        if not match:
            raise ValueError("time_slot must be in format 'x-y' or 'x' (e.g., '1-3', '4-4', '4')")
        
        start = int(match.group(1))
        end = int(match.group(2))
        
        if start < 1 or start > 10 or end < 1 or end > 10:
            raise ValueError("time_slot periods must be between 1 and 10")
        
        if start > end:
            raise ValueError("time_slot start must be less than or equal to end")
        
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "class_id": 1,
                    "reason": "I have a doctor appointment and need to attend a medical checkup.",
                    "leave_date": "2024-10-20T00:00:00Z",
                    "day_of_week": "Monday",
                    "time_slot": "1-3",
                    "evidence_file_id": 5
                }
            ]
        }
    }


class UpdateLeaveRequestRequest(BaseModel):
    """Request to update a leave request (only for pending status)."""
    reason: Optional[str] = Field(None, min_length=10, max_length=1000)
    leave_date: Optional[datetime] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="Day of week as integer: 0=Monday..6=Sunday")
    time_slot: Optional[str] = None
    evidence_file_id: Optional[int] = None
    
    @field_validator('time_slot')
    @classmethod
    def validate_time_slot(cls, v):
        """Validate time slot format: 'x-y' or 'x' where x,y are 1-10. Normalizes 'x' to 'x-x'."""
        if v is not None:
            import re
            single_pattern = r'^(\d+)$'
            single_match = re.match(single_pattern, v)
            if single_match:
                n = int(single_match.group(1))
                if n < 1 or n > 10:
                    raise ValueError("time_slot period must be between 1 and 10")
                return f"{n}-{n}"
            
            pattern = r'^(\d+)-(\d+)$'
            match = re.match(pattern, v)
            if not match:
                raise ValueError("time_slot must be in format 'x-y' or 'x' (e.g., '1-3', '4-4', '4')")
            
            start = int(match.group(1))
            end = int(match.group(2))
            
            if start < 1 or start > 10 or end < 1 or end > 10:
                raise ValueError("time_slot periods must be between 1 and 10")
            
            if start > end:
                raise ValueError("time_slot start must be less than or equal to end")
        
        return v


class ReviewLeaveRequestRequest(BaseModel):
    """Request to review (approve/reject) a leave request - Teacher only."""
    status: str = Field(..., description="approved or rejected")
    review_notes: Optional[str] = Field(None, max_length=500, description="Review notes/comments")
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v not in ['approved', 'rejected']:
            raise ValueError("status must be 'approved' or 'rejected'")
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "approved",
                    "review_notes": "Medical certificate verified. Approved."
                }
            ]
        }
    }


# ========================================
# Response Schemas
# ========================================

class LeaveRequestResponse(BaseModel):
    """Leave request detail response."""
    id: int
    studentId: int = Field(..., alias="studentId")
    studentName: str = Field(..., alias="studentName")
    studentCode: Optional[str] = Field(None, alias="studentCode")  # Added student code
    classId: int = Field(..., alias="classId")
    className: str = Field(..., alias="className")
    reason: str
    leaveDate: str = Field(..., alias="leaveDate")  # ISO format
    dayOfWeek: str = Field(..., alias="dayOfWeek")
    timeSlot: Optional[str] = Field(None, alias="timeSlot")
    evidenceFileId: Optional[int] = Field(None, alias="evidenceFileId")
    evidenceFileUrl: Optional[str] = Field(None, alias="evidenceFileUrl")  # Added file URL
    status: str  # pending, approved, rejected, cancelled
    reviewedBy: Optional[int] = Field(None, alias="reviewedBy")
    reviewerName: Optional[str] = Field(None, alias="reviewerName")
    reviewNotes: Optional[str] = Field(None, alias="reviewNotes")
    reviewedAt: Optional[str] = Field(None, alias="reviewedAt")
    createdAt: str = Field(..., alias="createdAt")
    updatedAt: Optional[str] = Field(None, alias="updatedAt")
    
    model_config = {"populate_by_name": True}


class CreateLeaveRequestResponse(BaseModel):
    """Response for POST /leave-requests."""
    success: bool = True
    data: dict
    message: str = "Leave request created successfully"


class GetLeaveRequestsResponse(BaseModel):
    """Response for GET /leave-requests."""
    success: bool = True
    data: dict


class GetLeaveRequestDetailResponse(BaseModel):
    """Response for GET /leave-requests/{id}."""
    success: bool = True
    data: dict


class UpdateLeaveRequestResponse(BaseModel):
    """Response for PUT /leave-requests/{id}."""
    success: bool = True
    data: dict
    message: str = "Leave request updated successfully"


class ReviewLeaveRequestResponse(BaseModel):
    """Response for POST /leave-requests/{id}/review."""
    success: bool = True
    data: dict
    message: str = "Leave request reviewed successfully"


class CancelLeaveRequestResponse(BaseModel):
    """Response for DELETE /leave-requests/{id}."""
    success: bool = True
    message: str = "Leave request cancelled successfully"


# ========================================
# Teacher-specific Schemas
# ========================================

class TeacherLeaveRequestSummary(BaseModel):
    """Summary statistics for teacher's leave requests."""
    totalRequests: int = Field(..., alias="totalRequests")
    pendingCount: int = Field(..., alias="pendingCount")
    approvedCount: int = Field(..., alias="approvedCount")
    rejectedCount: int = Field(..., alias="rejectedCount")
    cancelledCount: int = Field(..., alias="cancelledCount")
    
    model_config = {"populate_by_name": True}


class TeacherClassLeaveRequestStats(BaseModel):
    """Leave request statistics per class."""
    classId: int = Field(..., alias="classId")
    className: str = Field(..., alias="className")
    totalRequests: int = Field(..., alias="totalRequests")
    pendingCount: int = Field(..., alias="pendingCount")
    approvedCount: int = Field(..., alias="approvedCount")
    rejectedCount: int = Field(..., alias="rejectedCount")
    
    model_config = {"populate_by_name": True}


class GetTeacherLeaveRequestsResponse(BaseModel):
    """Response for GET /teacher/leave-requests - Enhanced for teachers."""
    success: bool = True
    data: dict  # Contains: leaveRequests, total, summary, classSummary
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "data": {
                        "leaveRequests": [
                            {
                                "id": 1,
                                "studentId": 10,
                                "studentName": "Nguyen Van A",
                                "studentCode": "SV001",
                                "classId": 1,
                                "className": "Java Programming",
                                "reason": "Medical appointment",
                                "leaveDate": "2024-10-20T00:00:00Z",
                                "dayOfWeek": "Monday",
                                "timeSlot": "1-3",
                                "evidenceFileId": 5,
                                "evidenceFileUrl": "https://...",
                                "status": "pending",
                                "createdAt": "2024-10-19T10:00:00Z"
                            }
                        ],
                        "total": 15,
                        "summary": {
                            "totalRequests": 15,
                            "pendingCount": 5,
                            "approvedCount": 8,
                            "rejectedCount": 2,
                            "cancelledCount": 0
                        },
                        "classSummary": [
                            {
                                "classId": 1,
                                "className": "Java Programming",
                                "totalRequests": 10,
                                "pendingCount": 3,
                                "approvedCount": 6,
                                "rejectedCount": 1
                            }
                        ]
                    }
                }
            ]
        }
    }


class BatchReviewRequest(BaseModel):
    """Request to review multiple leave requests at once."""
    request_ids: List[int] = Field(..., min_items=1, description="List of leave request IDs")
    status: str = Field(..., description="approved or rejected")
    review_notes: Optional[str] = Field(None, max_length=500, description="Review notes for all requests")
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v not in ['approved', 'rejected']:
            raise ValueError("status must be 'approved' or 'rejected'")
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "request_ids": [1, 2, 3],
                    "status": "approved",
                    "review_notes": "All medical certificates verified."
                }
            ]
        }
    }


class BatchReviewResponse(BaseModel):
    """Response for batch review."""
    success: bool = True
    data: dict  # Contains: successCount, failedCount, results
    message: str = "Batch review completed"
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "data": {
                        "successCount": 3,
                        "failedCount": 0,
                        "results": [
                            {"id": 1, "status": "approved", "success": True},
                            {"id": 2, "status": "approved", "success": True},
                            {"id": 3, "status": "approved", "success": True}
                        ]
                    },
                    "message": "Batch review completed: 3 approved, 0 failed"
                }
            ]
        }
    }