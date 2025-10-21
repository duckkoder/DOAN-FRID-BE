# Real-time Attendance System với Teacher Confirmation

## 🎯 Mục tiêu

Xây dựng hệ thống điểm danh AI với 2 luồng chính:
1. **Giáo viên**: Xem sinh viên AI nhận diện (pending) → Xác nhận/Từ chối
2. **Sinh viên**: Xem trạng thái điểm danh real-time khi vào trang lớp học

## 📊 Workflow

###  Luồng Teacher (AttendanceCamera)

```
AI Service              Backend                  Teacher UI
    |                      |                          |
    |--recognizes face-->  |                          |
    |                      |                          |
    |                   create record                 |
    |                status="pending"                 |
    |                is_ai_detected=true              |
    |                      |                          |
    |                      |---WebSocket broadcast--->|
    |                      |    "pending_confirmation"|
    |                      |                          |
    |                      |                   Display in
    |                      |                   "Đang giờ" list
    |                      |                          |
    |                      |<--Teacher confirms-------|
    |                      |                          |
    |                   update record                 |
    |                status="present"                 |
    |                confirmed_by_teacher_id=X        |
    |                confirmed_at=now()               |
    |                      |                          |
    |                      |---WebSocket broadcast--->|
    |                      |    "confirmed"           |
```

### Luồng Student (StudentClassDetailPage)

```
Student UI              Backend                WebSocket
    |                      |                       |
    |--Open class page-->  |                       |
    |                      |                       |
    |<--Check ongoing------|                       |
    |    session?          |                       |
    |                      |                       |
    |--Connect WS----------|                       |
    |                      |                       |
    |                      |<--AI recognizes-------|
    |                      |   student             |
    |                      |                       |
    |<--Broadcast----------|                       |
    |   "You're pending"   |                       |
    |                      |                       |
    Display banner:        |                       |
    "⏳ Đang chờ xác nhận"  |                       |
    |                      |                       |
    |                      |<--Teacher confirms----|
    |                      |                       |
    |<--Broadcast----------|                       |
    |   "You're present"   |                       |
    |                      |                       |
    Update banner:         |                       |
    "✅ Đã điểm danh"       |                       |
```

## 🗄️ Database Schema Changes

### AttendanceRecord Model

```python
class AttendanceRecord:
    # Existing fields
    session_id: int
    student_id: int
    status: str  # NEW VALUES: "pending_confirmation", "present", "late", "absent"
    confidence_score: float
    recorded_at: datetime
    
    # NEW FIELDS
    is_ai_detected: bool = False  # True nếu AI nhận diện
    confirmed_by_teacher_id: int | None  # ID giáo viên xác nhận
    confirmed_at: datetime | None  # Thời gian xác nhận
```

### Status Values

- `pending_confirmation`: AI đã nhận diện, chờ giáo viên xác nhận
- `present`: Đã điểm danh (đúng giờ)
- `late`: Đã điểm danh (trễ)
- `absent`: Vắng mặt
- `excused`: Có phép (leave request được approve)

## 🔌 WebSocket Messages

### 1. Attendance Update (gửi cho Teacher)

```json
{
  "type": "attendance_update",
  "session_id": 123,
  "student": {
    "id": 456,
    "student_code": "102220347",
    "full_name": "Nguyễn Văn A",
    "status": "pending_confirmation",
    "confidence_score": 0.75,
    "recorded_at": "2025-10-21T09:05:30Z"
  }
}
```

### 2. Student Status Update (gửi cho Student)

```json
{
  "type": "student_status_update",
  "session_id": 123,
  "student_id": 456,
  "status": "pending_confirmation",
  "confidence_score": 0.75,
  "message": "Hệ thống đã nhận diện bạn. Đang chờ giáo viên xác nhận.",
  "recorded_at": "2025-10-21T09:05:30Z"
}
```

### 3. Confirmation Update (gửi cho cả Teacher và Student)

```json
{
  "type": "confirmation_update",
  "session_id": 123,
  "student_id": 456,
  "student_code": "102220347",
  "status": "present",
  "confirmed_by": "Giáo viên X",
  "confirmed_at": "2025-10-21T09:06:00Z"
}
```

## 🔗 API Endpoints

### For Teachers

#### 1. Confirm Single Student
```http
POST /api/v1/attendance/records/{record_id}/confirm
Authorization: Bearer {token}

Response:
{
  "success": true,
  "record": {
    "id": 789,
    "student_id": 456,
    "status": "present",
    "confirmed_at": "2025-10-21T09:06:00Z"
  }
}
```

#### 2. Confirm All Pending
```http
POST /api/v1/attendance/sessions/{session_id}/confirm-all
Authorization: Bearer {token}

Response:
{
  "success": true,
  "confirmed_count": 5,
  "records": [...]
}
```

#### 3. Reject Attendance
```http
POST /api/v1/attendance/records/{record_id}/reject
Authorization: Bearer {token}
Content-Type: application/json

{
  "reason": "Không phải sinh viên này"
}

Response:
{
  "success": true,
  "message": "Đã từ chối xác nhận"
}
```

#### 4. Get Pending Students
```http
GET /api/v1/attendance/sessions/{session_id}/pending
Authorization: Bearer {token}

Response:
{
  "pending_count": 3,
  "students": [
    {
      "record_id": 789,
      "student_id": 456,
      "student_code": "102220347",
      "full_name": "Nguyễn Văn A",
      "confidence_score": 0.75,
      "recorded_at": "2025-10-21T09:05:30Z"
    }
  ]
}
```

### For Students

#### 1. Get Current Session Status
```http
GET /api/v1/attendance/classes/{class_id}/current-session
Authorization: Bearer {token}

Response:
{
  "has_active_session": true,
  "session": {
    "id": 123,
    "start_time": "2025-10-21T09:00:00Z",
    "status": "ongoing"
  },
  "my_attendance": {
    "status": "pending_confirmation",
    "confidence_score": 0.75,
    "recorded_at": "2025-10-21T09:05:30Z"
  }
}
```

#### 2. Get My Attendance Status
```http
GET /api/v1/attendance/sessions/{session_id}/my-status
Authorization: Bearer {token}

Response:
{
  "student_id": 456,
  "status": "present",
  "recorded_at": "2025-10-21T09:05:30Z",
  "confirmed_at": "2025-10-21T09:06:00Z",
  "is_ai_detected": true
}
```

## 🎨 Frontend Components

### Teacher Side: AttendanceCamera

```tsx
<AttendanceCamera>
  <Row>
    <Col span={16}>
      <VideoFeed />
      <DetectionOverlay />
    </Col>
    
    <Col span={8}>
      <Card title="Đang giờ (Chờ xác nhận)" extra={<Button>Chấp nhận tất cả</Button>}>
        {pendingStudents.map(student => (
          <PendingStudentCard
            student={student}
            onConfirm={() => confirmStudent(student.id)}
            onReject={() => rejectStudent(student.id)}
          />
        ))}
      </Card>
      
      <Card title="Đúng giờ">
        {confirmedStudents.map(student => (
          <ConfirmedStudentCard student={student} />
        ))}
      </Card>
    </Col>
  </Row>
</AttendanceCamera>
```

### Student Side: StudentClassDetailPage

```tsx
<StudentClassDetailPage>
  {ongoingSession && (
    <Alert
      type={getAlertType(myAttendanceStatus)}
      message={getAttendanceMessage(myAttendanceStatus)}
      description={getAttendanceDescription(myAttendanceStatus)}
      showIcon
      icon={getStatusIcon(myAttendanceStatus)}
    />
  )}
  
  {/* Rest of class details */}
</StudentClassDetailPage>
```

## 🔄 Real-time Updates Flow

1. **AI nhận diện** → Backend tạo record `pending_confirmation`
2. **Backend broadcast** → Teacher nhìn thấy trong "Đang giờ"
3. **Backend broadcast** → Student nhìn thấy "⏳ Đang chờ xác nhận"
4. **Teacher confirms** → Backend update record `present`
5. **Backend broadcast** → Teacher thấy chuyển sang "Đúng giờ"
6. **Backend broadcast** → Student thấy "✅ Đã điểm danh"

## ⚙️ Configuration

```python
# settings.py
ATTENDANCE_CONFIRMATION_REQUIRED = True  # Bật/tắt confirmation mode
ATTENDANCE_AUTO_CONFIRM_THRESHOLD = 0.85  # Tự động confirm nếu confidence >= 85%
ATTENDANCE_PENDING_TIMEOUT_MINUTES = 30  # Timeout cho pending records
```

## 🧪 Testing Scenarios

### Scenario 1: Happy Path
1. Giáo viên start session
2. Sinh viên vào lớp, AI nhận diện (75%)
3. Sinh viên thấy "Đang chờ xác nhận"
4. Giáo viên xác nhận
5. Sinh viên thấy "Đã điểm danh"

### Scenario 2: Rejection
1. AI nhận diện nhầm
2. Giáo viên từ chối
3. Record bị xóa hoặc đánh dấu rejected
4. Sinh viên vẫn thấy "Chưa điểm danh"

### Scenario 3: Bulk Confirm
1. 10 sinh viên được AI nhận diện
2. Giáo viên click "Chấp nhận tất cả"
3. Tất cả chuyển thành "present"
4. 10 sinh viên đều nhận notification

## 📝 Migration Script

```python
# migrations/xxx_add_confirmation_fields.py
def upgrade():
    op.add_column('attendance_records', 
        sa.Column('is_ai_detected', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('attendance_records',
        sa.Column('confirmed_by_teacher_id', sa.Integer(), nullable=True))
    op.add_column('attendance_records',
        sa.Column('confirmed_at', sa.DateTime(), nullable=True))
    
    op.create_foreign_key(
        'fk_attendance_record_confirmed_by',
        'attendance_records', 'teachers',
        ['confirmed_by_teacher_id'], ['id'],
        ondelete='SET NULL'
    )

def downgrade():
    op.drop_constraint('fk_attendance_record_confirmed_by', 'attendance_records')
    op.drop_column('attendance_records', 'confirmed_at')
    op.drop_column('attendance_records', 'confirmed_by_teacher_id')
    op.drop_column('attendance_records', 'is_ai_detected')
```

## 🚀 Deployment Checklist

- [ ] Run database migration
- [ ] Update attendance service logic
- [ ] Add new API endpoints
- [ ] Update WebSocket message handlers
- [ ] Deploy frontend components
- [ ] Test WebSocket connections
- [ ] Monitor system performance
