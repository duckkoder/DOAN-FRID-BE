# 📸 QUY TRÌNH ĐĂNG KÝ SINH TRẮC HỌC KHUÔN MẶT

> **Mô tả:** Quy trình hoàn chỉnh từ khi sinh viên thu thập ảnh khuôn mặt, xác nhận, đến khi admin phê duyệt và lưu trữ trên AWS S3.

---

## 📋 MỤC LỤC

1. [Tổng quan](#-tng-quan)
2. [Kiến trúc hệ thống](#-kin-trc-h-thng)
3. [Workflow chi tiết](#-workflow-chi-tit)
4. [Database Schema](#-database-schema)
5. [API Endpoints](#-api-endpoints)
6. [AWS S3 Storage](#-aws-s3-storage)
7. [Security & Authentication](#-security--authentication)
8. [Error Handling](#-error-handling)

---

## 🎯 TỔNG QUAN

### **Mục đích**
- Thu thập 14 ảnh khuôn mặt của sinh viên từ nhiều góc độ khác nhau
- Sinh viên xem trước và xác nhận ảnh trước khi gửi
- Admin kiểm tra chất lượng và phê duyệt
- Lưu trữ an toàn trên AWS S3 với presigned URLs

### **Các bước chính**
```
1. Thu thập (Collecting) → 2. Xác nhận SV (Student Review) → 3. Chờ duyệt (Admin Review) → 4. Hoàn thành (Approved)
```

### **Thời gian dự kiến**
- Thu thập ảnh: ~2 phút (14 ảnh)
- Xác nhận sinh viên: ~30 giây
- Phê duyệt admin: ~1-2 phút

---

## 🏗️ KIẾN TRÚC HỆ THỐNG

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT (Frontend - React)                    │
├─────────────────────────────────────────────────────────────────────┤
│  1. Camera Capture                                                   │
│  2. MediaPipe Face Detection                                         │
│  3. WebSocket Communication                                          │
│  4. Image Preview & Confirmation                                     │
│  5. Admin Review UI                                                  │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            │ WebSocket + REST API
                            │
┌───────────────────────────▼─────────────────────────────────────────┐
│                      BACKEND (FastAPI + Python)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │          WebSocket Handler (Real-time Communication)        │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  • Receive camera frames                                    │   │
│  │  • Face verification (MediaPipe)                            │   │
│  │  • Temp storage (base64 in memory)                          │   │
│  │  • Student confirmation handling                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Admin API (REST Endpoints)                     │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  • List registrations                                       │   │
│  │  • Get registration detail (with presigned URLs)            │   │
│  │  • Approve/Reject registration                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  S3 Service (AWS Integration)               │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  • Upload images to S3                                      │   │
│  │  • Generate presigned URLs (on-demand)                      │   │
│  │  • Batch operations                                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                ┌───────────┴──────────┐
                │                      │
┌───────────────▼─────────┐  ┌────────▼──────────────┐
│   PostgreSQL Database   │  │   AWS S3 Bucket       │
├─────────────────────────┤  ├───────────────────────┤
│ • face_registration_    │  │ • Private bucket      │
│   requests              │  │ • Folder structure:   │
│ • files                 │  │   private/faces/      │
│ • students              │  │   student_X/          │
│ • users                 │  │ • Image files (.jpg)  │
└─────────────────────────┘  └───────────────────────┘
```

---

## 🔄 WORKFLOW CHI TIẾT

### **PHASE 1: THU THẬP ẢNH (Collecting)**

#### **1.1. Khởi tạo WebSocket Connection**
```typescript
// Frontend
const ws = new WebSocket(`ws://localhost:8000/ws/face-registration/${studentId}`);
ws.onopen = () => {
  console.log("✅ Connected to face registration service");
};
```

#### **1.2. Sinh viên thu thập 14 ảnh**
```
Danh sách 14 bước (steps):
┌──────────────┬────────────────────────────────────┬──────────────┐
│ Bước         │ Mô tả                              │ Yêu cầu      │
├──────────────┼────────────────────────────────────┼──────────────┤
│ 1. front     │ Nhìn thẳng camera                  │ yaw: ±8°     │
│ 2. left_5    │ Quay trái 5°                       │ yaw: 5-10°   │
│ 3. left_10   │ Quay trái 10°                      │ yaw: 10-15°  │
│ 4. left_15   │ Quay trái 15°                      │ yaw: 12-18°  │
│ 5. left_20   │ Quay trái 20°                      │ yaw: 18-25°  │
│ 6. right_5   │ Quay phải 5°                       │ yaw: -5-(-10)│
│ 7. right_10  │ Quay phải 10°                      │ yaw: -10-(-15)│
│ 8. right_15  │ Quay phải 15°                      │ yaw: -12-(-18)│
│ 9. right_20  │ Quay phải 20°                      │ yaw: -18-(-25)│
│ 10. close    │ Gần camera                         │ width > 200  │
│ 11. up_10    │ Ngẩng lên 10°                      │ pitch: -10°  │
│ 12. up_15    │ Ngẩng lên 15°                      │ pitch: -15°  │
│ 13. down_10  │ Cúi xuống 10°                      │ pitch: +10°  │
│ 14. down_15  │ Cúi xuống 15°                      │ pitch: +15°  │
└──────────────┴────────────────────────────────────┴──────────────┘
```

#### **1.3. Backend xử lý frame**
```python
# app/api/v1/face_registration_ws.py

async def handle_frame(self, message: dict):
    """Process camera frame from client."""
    
    # 1. Decode base64 image
    image_data = base64.b64decode(message["frame"])
    
    # 2. Verify face with MediaPipe
    result = self.face_service.verify_face_for_step(
        image_data=image_data,
        current_step=self.current_step
    )
    
    if result["success"]:
        # 3. Save temp data (in memory, NOT in S3 yet)
        temp_data = {
            "step_name": result["step_name"],
            "step_number": result["step_number"],
            "instruction": result["instruction"],
            "image_base64": message["frame"],  # Keep base64 for preview
            "timestamp": datetime.utcnow().isoformat(),
            "pose_angles": result["pose_angles"],
            "face_width": result["face_width"],
            "crop_info": result["crop_info"]
        }
        self.captured_images.append(temp_data)
        
        # 4. Update DB: temp_images_data (for student preview)
        self.db_service.update_registration_temp_data(
            registration_id=self.registration_request.id,
            temp_images_data=self.captured_images,
            status="collecting"
        )
        
        # 5. Send response to client
        await self.websocket.send_json({
            "type": "step_completed",
            "step": self.current_step,
            "total_steps": 14,
            "preview_url": f"data:image/jpeg;base64,{message['frame']}"
        })
```

**❗ LƯU Ý:** Ảnh chưa được upload lên S3 ở bước này, chỉ lưu base64 trong memory.

---

### **PHASE 2: SINH VIÊN XÁC NHẬN (Student Review)**

#### **2.1. Hiển thị 14 ảnh preview**
```typescript
// Frontend - Student Review UI
{tempImages.map((img, index) => (
  <img 
    key={index}
    src={`data:image/jpeg;base64,${img.image_base64}`}  // From temp_images_data
    alt={img.step_name}
  />
))}

<Button onClick={handleAccept}>Chấp nhận</Button>
<Button onClick={handleReject}>Thu lại</Button>
```

#### **2.2. Student gửi confirmation**
```typescript
// Frontend sends confirmation
ws.send(JSON.stringify({
  type: "student_confirm",
  accepted: true,
  student_id: studentId
}));
```

#### **2.3. Backend upload lên S3**
```python
# app/api/v1/face_registration_ws.py

async def handle_student_confirm(self, message: dict):
    """Handle student confirmation and upload to S3."""
    
    if not message.get("accepted"):
        # Student rejected → Clear temp data, restart
        await self.handle_restart()
        return
    
    # ✅ Student accepted → Upload to S3
    temp_images_data = self.registration_request.temp_images_data
    file_metadata_list = []
    
    for temp_data in temp_images_data:
        # 1. Decode base64 back to bytes
        import base64
        image_bytes = base64.b64decode(temp_data["image_base64"])
        
        # 2. Upload to S3
        upload_result = await s3_service.upload_face_image(
            image_data=image_bytes,
            student_id=self.student_id,
            step_name=temp_data["step_name"],
            step_number=temp_data["step_number"],
            metadata=temp_data["pose_angles"]
        )
        
        # 3. Create metadata (NO URL - only S3 key)
        metadata = FaceImageMetadata(
            step_name=temp_data["step_name"],
            step_number=temp_data["step_number"],
            instruction=temp_data["instruction"],
            timestamp=datetime.fromisoformat(temp_data["timestamp"]),
            pose_angles=PoseAngles(**temp_data["pose_angles"]),
            face_width=temp_data["face_width"],
            crop_info=CropInfo(**temp_data["crop_info"]),
            s3_key=upload_result["file_key"],  # ✅ Store S3 key (permanent)
            file_size=upload_result["file_size"]
        )
        file_metadata_list.append(metadata)
    
    # 4. Create file records in DB
    self.file_records = self.db_service.batch_create_file_records(
        uploader_id=self.student.user_id,  # ✅ Use user_id, not student_id
        file_metadata_list=file_metadata_list,
        category="face_registration"
    )
    
    # 5. Update registration status
    verification_data = FaceRegistrationVerificationData(
        verification_date=datetime.utcnow(),
        total_steps=14,
        completed_steps=len(file_metadata_list),
        success=True,
        steps=file_metadata_list
    )
    
    self.db_service.update_registration_status(
        registration_id=self.registration_request.id,
        status="pending_admin_review",  # ✅ Ready for admin
        verification_data=verification_data.model_dump(mode='json'),
        temp_images_data=None,  # ✅ Clear temp data
        student_reviewed_at=datetime.utcnow(),
        student_accepted=True
    )
```

**✅ KẾT QUẢ:**
- 14 ảnh đã được upload lên S3: `private/faces/student_4/01_face_front_20251027_142559.jpg`
- `files` table có 14 records với S3 keys
- `face_registration_requests` table: `status = "pending_admin_review"`
- `verification_data` chứa metadata (có `s3_key`, KHÔNG có `url`)

---

### **PHASE 3: ADMIN PHÊ DUYỆT (Admin Review)**

#### **3.1. Admin xem danh sách chờ duyệt**
```http
GET /api/v1/admin/face-registrations?status=pending_admin_review
Authorization: Bearer <admin_token>
```

**Response:**
```json
{
  "items": [
    {
      "id": 34,
      "student_code": "SV862155",
      "student_name": "Nguyễn Văn B",
      "status": "pending_admin_review",
      "total_images_captured": 14,
      "registration_progress": 100.0,
      "student_reviewed_at": "2025-10-27T14:25:59.505276",
      "student_accepted": true,
      "created_at": "2025-10-27T14:24:41.908325"
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 10
}
```

#### **3.2. Admin xem chi tiết (với presigned URLs)**
```http
GET /api/v1/admin/face-registrations/34
Authorization: Bearer <admin_token>
```

**Backend xử lý:**
```python
# app/api/v1/admin.py

@router.get("/face-registrations/{registration_id}")
async def get_face_registration(
    registration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = FaceRegistrationDBService(db)
    reg = service.get_registration_detail(registration_id)
    
    # ✅ Generate fresh presigned URLs on-demand
    verification_data_with_urls = reg.verification_data
    
    if reg.verification_data and "steps" in reg.verification_data:
        # 1. Extract S3 keys from verification_data
        s3_keys = [
            step.get("s3_key") 
            for step in reg.verification_data["steps"] 
            if step.get("s3_key")
        ]
        
        if s3_keys:
            from app.services.s3_service import S3Service
            import copy
            s3_service = S3Service()
            
            # 2. Generate fresh presigned URLs (expires in 2 hours)
            presigned_urls = s3_service.batch_generate_presigned_urls(
                file_keys=s3_keys,
                expires_in=7200  # 2 hours
            )
            
            # 3. Deep copy and add URLs dynamically
            verification_data_with_urls = copy.deepcopy(reg.verification_data)
            for step in verification_data_with_urls["steps"]:
                s3_key = step.get("s3_key")
                if s3_key and s3_key in presigned_urls:
                    step["url"] = presigned_urls[s3_key]  # ✅ Add fresh URL
    
    return FaceRegistrationDetailResponse(
        id=reg.id,
        verification_data=verification_data_with_urls,  # ✅ With URLs
        # ... other fields
    )
```

**Response:**
```json
{
  "id": 34,
  "student_code": "SV862155",
  "student_name": "Nguyễn Văn B",
  "status": "pending_admin_review",
  "verification_data": {
    "steps": [
      {
        "step_name": "face_front",
        "step_number": 1,
        "s3_key": "private/faces/student_4/01_face_front_20251027_142559.jpg",
        "url": "https://pbl6-attendance-files.s3.amazonaws.com/private/faces/student_4/01_face_front_20251027_142559.jpg?AWSAccessKeyId=AKIAUMYCIDSSLMRAGMJ3&Signature=iY6XnnuIfHazzxLvyICGcvJg%2BOg%3D&Expires=1761584116"
      }
      // ... 13 more steps
    ]
  }
}
```

**🔑 QUAN TRỌNG:**
- `s3_key`: Lưu permanent trong DB
- `url`: Generate mới mỗi lần request (expires 2h)
- URL có `AWSAccessKeyId`, `Signature`, `Expires` để xác thực

#### **3.3. Admin phê duyệt**
```http
POST /api/v1/admin/face-registrations/34/approve
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "note": "Ảnh rõ nét, đạt yêu cầu"
}
```

**Backend xử lý:**
```python
# app/api/v1/admin.py

@router.post("/face-registrations/{registration_id}/approve")
async def approve_face_registration(
    registration_id: int,
    request: FaceRegistrationApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    service = FaceRegistrationDBService(db)
    reg = service.approve_registration(
        registration_id=registration_id,
        admin_id=current_user.id,
        note=request.note
    )
    
    # Update student verification status
    student = db.query(Student).filter(Student.id == reg.student_id).first()
    student.is_verified = True
    db.commit()
    
    return {
        "success": True,
        "message": "Face registration approved successfully",
        "registration_id": reg.id,
        "status": reg.status  # "approved"
    }
```

#### **3.4. Admin từ chối**
```http
POST /api/v1/admin/face-registrations/34/reject
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "rejection_reason": "Ảnh bị mờ, cần chụp lại",
  "note": "Yêu cầu sinh viên chụp lại trong điều kiện ánh sáng tốt hơn"
}
```

---

## 💾 DATABASE SCHEMA

### **1. Table: `face_registration_requests`**
```sql
CREATE TABLE face_registration_requests (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(id) NOT NULL,
    status VARCHAR(50) DEFAULT 'collecting',
    total_images_captured INTEGER DEFAULT 0,
    registration_progress FLOAT DEFAULT 0.0,
    
    -- Temp data for student preview (before upload to S3)
    temp_images_data JSONB,  -- List[{step_name, image_base64, timestamp, ...}]
    
    -- Final verification data (after upload to S3)
    verification_data JSONB,  -- {steps: [{s3_key, step_name, pose_angles, ...}]}
    
    -- Student review
    student_reviewed_at TIMESTAMP,
    student_accepted BOOLEAN,
    
    -- Admin review
    admin_reviewed_at TIMESTAMP,
    reviewed_by INTEGER REFERENCES users(id),
    rejection_reason TEXT,
    note TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Workflow của các fields:**

| Phase | temp_images_data | verification_data | status |
|-------|------------------|-------------------|--------|
| Thu thập | `[{base64, ...}, ...]` | `null` | `collecting` |
| SV xác nhận | `[{base64, ...}, ...]` | `null` | `pending_student_review` |
| Upload S3 | `null` ✅ | `{steps: [{s3_key, ...}]}` ✅ | `pending_admin_review` |
| Admin duyệt | `null` | `{steps: [{s3_key, ...}]}` | `approved` |

### **2. Table: `files`**
```sql
CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    uploader_id INTEGER REFERENCES users(id) NOT NULL,  -- ⚠️ user_id, not student_id
    file_key VARCHAR(500) NOT NULL,  -- S3 key (permanent)
    filename VARCHAR(255),
    original_name VARCHAR(255),
    mime_type VARCHAR(100),
    size INTEGER,
    category VARCHAR(50),  -- 'face_registration'
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Example records:**
```sql
INSERT INTO files VALUES
(1, 10, 'private/faces/student_4/01_face_front_20251027_142559.jpg', 'face_front.jpg', 'face_front_1.jpg', 'image/jpeg', 10123, 'face_registration', false),
(2, 10, 'private/faces/student_4/02_face_left_5_20251027_142600.jpg', 'face_left_5.jpg', 'face_left_5_2.jpg', 'image/jpeg', 7738, 'face_registration', false),
-- ... 12 more records
```

⚠️ **QUAN TRỌNG:** `uploader_id` phải là `user.id` (không phải `student.id`):
```
Student (id=4) → user_id=10
                 ↓
              Users (id=10)
                 ↑
Files.uploader_id=10 ✅
```

### **3. Table: `students`**
```sql
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    student_code VARCHAR(20) UNIQUE,
    is_verified BOOLEAN DEFAULT FALSE,  -- ✅ Set to true when approved
    -- ... other fields
);
```

---

## 🌐 API ENDPOINTS

### **Student APIs**

#### **1. Start WebSocket Registration**
```
WS /ws/face-registration/{student_id}
Authentication: Required (JWT token in query or header)
```

**Messages:**
```json
// Client → Server: Send frame
{
  "type": "frame",
  "frame": "base64_encoded_image",
  "current_step": 1
}

// Server → Client: Step completed
{
  "type": "step_completed",
  "step": 1,
  "total_steps": 14,
  "preview_url": "data:image/jpeg;base64,...",
  "message": "Step 1 completed"
}

// Client → Server: Student confirm
{
  "type": "student_confirm",
  "accepted": true,
  "student_id": 4
}

// Server → Client: Registration completed
{
  "type": "registration_completed",
  "registration_id": 34,
  "status": "pending_admin_review",
  "message": "Registration submitted for admin review"
}
```

#### **2. Get Student Registration Status**
```http
GET /api/v1/students/me/face-registration
Authorization: Bearer <student_token>
```

### **Admin APIs**

#### **1. List Face Registrations**
```http
GET /api/v1/admin/face-registrations
  ?status=pending_admin_review
  &search=SV862155
  &page=1
  &limit=10
Authorization: Bearer <admin_token>
```

#### **2. Get Registration Detail**
```http
GET /api/v1/admin/face-registrations/{registration_id}
Authorization: Bearer <admin_token>
```

**Response includes fresh presigned URLs (expires 2h).**

#### **3. Approve Registration**
```http
POST /api/v1/admin/face-registrations/{registration_id}/approve
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "note": "Approved - good quality images"
}
```

#### **4. Reject Registration**
```http
POST /api/v1/admin/face-registrations/{registration_id}/reject
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "rejection_reason": "Image quality too low",
  "note": "Please retake in better lighting"
}
```

---

## ☁️ AWS S3 STORAGE

### **Bucket Configuration**
```
Bucket Name: pbl6-attendance-files
Region: ap-southeast-1 (Singapore)
Access: Private (Block all public access)
Encryption: AES-256
```

### **Folder Structure**
```
pbl6-attendance-files/
├── private/
│   └── faces/
│       ├── student_4/
│       │   ├── 01_face_front_20251027_142559.jpg
│       │   ├── 02_face_left_5_20251027_142600.jpg
│       │   ├── 03_face_left_10_20251027_142600.jpg
│       │   └── ... (14 files total)
│       ├── student_5/
│       │   └── ...
│       └── student_6/
│           └── ...
└── public/
    └── (other public files)
```

### **File Naming Convention**
```
Format: {step_number:02d}_{step_name}_{timestamp}.jpg

Examples:
- 01_face_front_20251027_142559.jpg
- 02_face_left_5_20251027_142600.jpg
- 14_face_down_15_20251027_142602.jpg

Timestamp format: YYYYMMDDHHmmss
```

### **S3 Upload Code**
```python
# app/services/s3_service.py

async def upload_face_image(
    self,
    image_data: bytes,
    student_id: int,
    step_name: str,
    step_number: int,
    metadata: dict = None
) -> dict:
    """Upload face image to S3."""
    
    # 1. Generate S3 key
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    s3_key = f"private/faces/student_{student_id}/{step_number:02d}_{step_name}_{timestamp}.jpg"
    
    # 2. Prepare metadata
    s3_metadata = {
        'student-id': str(student_id),
        'step-name': step_name,
        'step-number': str(step_number),
        'uploaded-at': datetime.utcnow().isoformat()
    }
    
    if metadata:
        for key, value in metadata.items():
            s3_metadata[f'custom-{key}'] = str(value)
    
    # 3. Upload to S3
    self.s3_client.put_object(
        Bucket=self.bucket_name,
        Key=s3_key,
        Body=image_data,
        ContentType="image/jpeg",
        Metadata=s3_metadata
    )
    
    # 4. Return S3 key (NOT URL)
    return {
        "file_key": s3_key,
        "file_size": len(image_data),
        "step_name": step_name,
        "step_number": step_number,
        "is_public": False
    }
```

### **Presigned URL Generation**
```python
# app/services/s3_service.py

def batch_generate_presigned_urls(
    self, 
    file_keys: list[str], 
    expires_in: int = 7200
) -> dict[str, str]:
    """
    Batch generate presigned URLs for multiple files.
    
    Args:
        file_keys: List of S3 keys
        expires_in: URL expiration in seconds (default: 2 hours)
    
    Returns:
        Dict mapping file_key → presigned URL
    """
    urls = {}
    for file_key in file_keys:
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': file_key},
                ExpiresIn=expires_in
            )
            urls[file_key] = url
        except Exception as e:
            logger.error(f"Failed to generate URL for {file_key}: {e}")
            urls[file_key] = None
    
    return urls
```

**Generated URL example:**
```
https://pbl6-attendance-files.s3.amazonaws.com/private/faces/student_4/01_face_front_20251027_142559.jpg
?AWSAccessKeyId=AKIAUMYCIDSSLMRAGMJ3
&Signature=iY6XnnuIfHazzxLvyICGcvJg%2BOg%3D
&Expires=1761584116

Components:
- AWSAccessKeyId: Public key identifier (safe to expose)
- Signature: HMAC-SHA256(secret_key, request_info) 
- Expires: Unix timestamp (URL valid until this time)
```

### **Why NOT store URLs in DB?**
```
❌ BAD PRACTICE: Store URL in database
{
  "url": "https://...?Signature=...&Expires=1730035200"
}
Problem: 
- URL expires after 1-2 hours
- Admin cannot view images after expiration
- Need to regenerate URLs → but they're already in DB

✅ GOOD PRACTICE: Store S3 key, generate URL on-demand
{
  "s3_key": "private/faces/student_4/01_face_front.jpg",
  "url": null  // Generate when needed
}
Benefit:
- S3 key never expires
- Generate fresh URL whenever admin requests
- Always works, no matter when admin reviews
```

---

## 🔐 SECURITY & AUTHENTICATION

### **IAM Permissions Required**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::pbl6-attendance-files/*",
        "arn:aws:s3:::pbl6-attendance-files"
      ]
    }
  ]
}
```

### **Environment Variables**
```bash
# .env file (NEVER commit to Git!)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=<secret_key_here>
AWS_REGION=ap-southeast-1
S3_BUCKET_NAME=pbl6-attendance-files
```

### **Authentication Flow**
```
1. Student login → JWT token
2. WebSocket connection with token
3. Backend validates token
4. Extract student_id from token
5. All operations tied to student_id

Admin:
1. Admin login → JWT token (role="admin")
2. API requests with token
3. Backend checks role === "admin"
4. Allow admin operations
```

---

## ⚠️ ERROR HANDLING

### **Common Errors**

#### **1. Foreign Key Violation**
```python
# ❌ WRONG
uploader_id = student_id  # student.id = 4

# ✅ CORRECT
uploader_id = student.user_id  # user.id = 10
```

**Error:**
```
psycopg2.errors.ForeignKeyViolation: 
insert or update on table "files" violates foreign key constraint "files_uploader_id_fkey"
DETAIL: Key (uploader_id)=(4) is not present in table "users".
```

#### **2. Presigned URL 403 Forbidden**
```
Causes:
- File doesn't exist on S3
- IAM user lacks s3:GetObject permission
- Signature mismatch
- URL expired

Solution:
- Verify file uploaded: s3_client.head_object()
- Check IAM permissions
- Regenerate URL with longer expiration
```

#### **3. Pydantic Validation Error**
```python
# ❌ WRONG schema
temp_images_data: Optional[Dict[str, Any]] = None

# ✅ CORRECT schema
temp_images_data: Optional[List[Dict[str, Any]]] = None
```

**Error:**
```
pydantic_core._pydantic_core.ValidationError: 
1 validation error for FaceRegistrationDetailResponse
temp_images_data
  Input should be a valid dictionary [type=dict_type, input_value=[...], input_type=list]
```

#### **4. WebSocket Disconnection**
```python
try:
    await websocket.send_json(message)
except WebSocketDisconnect:
    logger.warning(f"Client disconnected during registration")
    # Cleanup: Don't save partial data
    await self.db_service.cancel_registration(registration_id)
```

---

## 📊 STATUS DIAGRAM

```
┌─────────────────────────────────────────────────────────────────┐
│                    FACE REGISTRATION STATUS                      │
└─────────────────────────────────────────────────────────────────┘

    START
      ↓
┌─────────────────┐
│   collecting    │  ← Student capturing 14 images
└────────┬────────┘
         │ (14/14 completed)
         ↓
┌──────────────────────────┐
│ pending_student_review   │  ← Show preview, wait for confirmation
└────────┬─────────────────┘
         │
         ├─(accepted)─────→ Upload to S3
         │                       ↓
         │              ┌──────────────────────┐
         │              │ pending_admin_review │  ← Admin reviews
         │              └────────┬─────────────┘
         │                       │
         │              ┌────────┴────────┐
         │              ↓                 ↓
         │        ┌──────────┐    ┌──────────┐
         │        │ approved │    │ rejected │
         │        └──────────┘    └────┬─────┘
         │                              │
         └─(rejected)──────────────────┘
                 │
                 ↓
           ┌───────────┐
           │ cancelled │  ← Student can restart
           └───────────┘
```

---

## 🎯 BEST PRACTICES

### **1. S3 Key Management**
✅ **DO:**
- Store S3 keys permanently in DB
- Generate presigned URLs on-demand
- Use deep copy when modifying verification_data

❌ **DON'T:**
- Store presigned URLs in DB
- Use shallow copy (`.copy()`) for nested dicts
- Hardcode AWS credentials

### **2. Image Storage**
✅ **DO:**
- Store temp images as base64 during collection
- Clear temp data after S3 upload
- Use batch operations for efficiency

❌ **DON'T:**
- Upload to S3 before student confirmation
- Keep base64 data after upload (wastes space)
- Make individual S3 calls in loops

### **3. Database Operations**
✅ **DO:**
- Use `user_id` for file uploader
- Update status atomically
- Use transactions for multi-step operations

❌ **DON'T:**
- Use `student_id` as foreign key to users
- Forget to update student.is_verified
- Mix temporary and permanent data

### **4. Frontend**
✅ **DO:**
- Use `step.url` for image src
- Handle loading states
- Show clear error messages

❌ **DON'T:**
- Use `step.s3_url` (doesn't exist)
- Assume URLs are permanent
- Ignore error responses

---

## 📝 CHECKLIST

### **Backend Implementation**
- [x] WebSocket endpoint for real-time collection
- [x] MediaPipe face verification
- [x] Temp storage with base64
- [x] Student confirmation handling
- [x] S3 upload service
- [x] Presigned URL generation (on-demand)
- [x] Admin APIs (list, detail, approve, reject)
- [x] Database schema and migrations
- [x] Error handling and logging

### **Frontend Implementation**
- [x] Camera capture UI
- [x] WebSocket communication
- [x] Image preview grid
- [x] Student confirmation modal
- [x] Admin review table
- [x] Image display with presigned URLs
- [x] Approve/reject actions

### **Testing**
- [x] S3 upload functionality
- [x] Presigned URL download
- [x] WebSocket message flow
- [x] Database constraints
- [x] Admin permissions
- [ ] Load testing (multiple concurrent uploads)
- [ ] Error scenarios (network failure, S3 timeout)

---

## 🚀 DEPLOYMENT CHECKLIST

### **Environment Setup**
- [ ] Configure AWS IAM user with proper permissions
- [ ] Create S3 bucket with private access
- [ ] Set up environment variables
- [ ] Verify PostgreSQL database
- [ ] Test WebSocket connectivity

### **Security**
- [ ] Rotate AWS credentials regularly
- [ ] Enable S3 bucket encryption
- [ ] Set up CloudWatch logging
- [ ] Implement rate limiting
- [ ] Add CORS configuration

### **Monitoring**
- [ ] S3 storage usage alerts
- [ ] Failed upload notifications
- [ ] Presigned URL generation errors
- [ ] WebSocket connection metrics
- [ ] Admin approval turnaround time

---

## 📞 SUPPORT

**Issues?**
- Check logs: `logs/app.log`
- Verify S3 connectivity: `python test_presigned_url.py`
- Test database: `python test_db_connection.py`
- Validate IAM permissions in AWS Console

**Documentation:**
- AWS S3 Presigned URLs: https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html
- FastAPI WebSockets: https://fastapi.tiangolo.com/advanced/websockets/
- MediaPipe Face Detection: https://developers.google.com/mediapipe/solutions/vision/face_detector

---

**Generated:** October 27, 2025  
**Version:** 1.0  
**Last Updated:** After implementing on-demand presigned URL generation
