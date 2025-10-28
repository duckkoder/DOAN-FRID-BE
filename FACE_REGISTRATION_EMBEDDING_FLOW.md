# 🎯 FACE REGISTRATION EMBEDDING FLOW

## 📋 Tổng quan

Tài liệu này mô tả luồng xử lý khi admin duyệt đăng ký khuôn mặt và tạo embeddings.

---

## 🔄 Quy trình hoàn chỉnh

### **Luồng chính:**

```
1. Student thu thập 14 ảnh → 2. Student xác nhận → 3. Admin xem và duyệt
                                                      ↓
                                            4. Gửi ảnh sang AI-service
                                                      ↓
                                            5. Trích xuất embeddings
                                                      ↓
                                            6. Lưu vào face_embeddings table
                                                      ↓
                                            7. Cập nhật status = 'approved'
```

---

## 🏗️ Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────────┐
│                      FRONT-END (Admin UI)                       │
│  - Xem danh sách pending registrations                          │
│  - Xem 14 ảnh với presigned URLs                               │
│  - Approve/Reject button                                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ POST /api/v1/admin/face-registrations/{id}/approve
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      BACK-END (FastAPI)                         │
├─────────────────────────────────────────────────────────────────┤
│  1. Get registration details                                    │
│  2. Download 14 cropped images from S3                         │
│  3. Convert to base64                                          │
│  4. Call AI-service API                                        │
│  5. Receive embeddings (14 x 512-dim vectors)                 │
│  6. Save to face_embeddings table (PostgreSQL + pgvector)      │
│  7. Update registration.status = 'approved'                    │
└────────────────┬──────────────────────────┬─────────────────────┘
                 │                          │
                 ▼                          ▼
        ┌────────────────┐         ┌───────────────────┐
        │   AWS S3       │         │   AI-SERVICE      │
        ├────────────────┤         ├───────────────────┤
        │ • Download     │         │ • Extract         │
        │   cropped      │         │   embeddings      │
        │   face images  │         │ • Apply TTA       │
        │                │         │ • Augmentation    │
        └────────────────┘         └───────────────────┘
                                            │
                                            ▼
                                   ┌────────────────────┐
                                   │  PostgreSQL        │
                                   │  + pgvector        │
                                   ├────────────────────┤
                                   │ face_embeddings    │
                                   │ - student_id       │
                                   │ - student_code     │
                                   │ - embedding (512)  │
                                   │ - status=approved  │
                                   └────────────────────┘
```

---

## 📝 Implementation Details

### **1. API Endpoint (Back-end)**

**File:** `back-end/app/api/v1/admin.py`

```python
@router.post("/face-registrations/{registration_id}/approve")
async def approve_face_registration(
    registration_id: int,
    request: FaceRegistrationApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Approve face registration and process embeddings
    
    Steps:
    1. Validate registration status
    2. Download images from S3
    3. Send to AI-service
    4. Save embeddings to DB
    5. Update status to 'approved'
    """
```

**Process:**
- ✅ Kiểm tra status phải là `pending_admin_review`
- ✅ Download 14 ảnh từ S3 (cropped faces)
- ✅ Convert sang base64
- ✅ Gọi AI-service endpoint
- ✅ Nhận 14 embeddings (512-dim vectors)
- ✅ Lưu vào `face_embeddings` table
- ✅ Update registration status

---

### **2. AI Service Client (Back-end)**

**File:** `back-end/app/services/ai_service_client.py`

```python
class FaceImageData:
    """Face image data for AI service"""
    def __init__(self, image_base64: str, step_name: str, step_number: int):
        self.image_base64 = image_base64
        self.step_name = step_name
        self.step_number = step_number

class AIServiceClient:
    async def register_face_embeddings(
        self,
        student_code: str,
        student_id: int,
        face_images: List[FaceImageData],
        use_augmentation: bool = True,
        augmentation_count: int = 5
    ) -> Dict[str, Any]:
        """
        Send face images to AI service for embedding extraction
        
        Returns:
        {
            "success": True,
            "student_code": "SV862155",
            "embeddings": [
                {
                    "step_name": "face_front",
                    "step_number": 1,
                    "embedding": [0.123, 0.456, ...],  # 512 floats
                    "augmented_count": 5
                },
                ...  # 13 more
            ],
            "total_embeddings_created": 84,  # 14 original + 70 augmented
            "processing_time_seconds": 12.5
        }
        """
```

**Features:**
- ✅ Timeout: 5 minutes (embedding extraction takes time)
- ✅ Retry logic
- ✅ Error handling

---

### **3. AI Service Endpoint (AI-service)**

**File:** `AI-service/app/api/v1/endpoints/registration.py`

```python
@router.post("/register-face")
async def register_student_face(request: RegisterFaceRequest):
    """
    Extract embeddings from 14 face images
    
    Process:
    1. Receive 14 base64 images
    2. For each image:
       a. Decode base64 → RGB numpy array
       b. Extract embedding with TTA (original image)
       c. Generate 5 augmented versions
       d. Extract embeddings (without TTA for speed)
       e. Average all embeddings (1 original + 5 augmented)
       f. Normalize the averaged embedding
    3. Return 14 averaged embeddings
    
    Augmentations applied:
    - Horizontal flip (30% probability)
    - Small rotation (-12° to +12°)
    - Translation (up to 4% of image size)
    - Color jitter (brightness, contrast, saturation)
    - Gaussian blur (15% probability)
    """
```

**Benefits of augmentation:**
- ✅ Robustness to lighting changes
- ✅ Better generalization
- ✅ Handle pose variations
- ✅ Improve recognition accuracy

---

### **4. Face Embedding Service (Back-end)**

**File:** `back-end/app/services/face_embedding_service.py`

```python
class FaceEmbeddingService:
    @staticmethod
    def create_embeddings_batch(
        db: Session,
        student_id: int,
        student_code: str,
        embeddings_data: List[Dict[str, Any]],
        image_prefix: str = "face_registration"
    ) -> List[FaceEmbedding]:
        """
        Create multiple face embeddings for a student
        
        Args:
            embeddings_data: List of {
                "step_name": "face_front",
                "step_number": 1,
                "embedding": [0.123, ...],  # 512 floats
                "augmented_count": 5
            }
        
        Returns:
            List of FaceEmbedding objects (14 records)
        """
```

**Database Schema:**
```sql
CREATE TABLE face_embeddings (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL,
    student_code VARCHAR(20) NOT NULL,  -- Denormalized for fast queries
    image_path VARCHAR(255) NOT NULL,
    embedding vector(512) NOT NULL,  -- pgvector type
    status VARCHAR(50) DEFAULT 'approved',
    uploaded_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP,
    
    -- Index for similarity search
    INDEX idx_face_embeddings_vector_cosine USING ivfflat (embedding vector_cosine_ops)
);
```

---

### **5. S3 Service (Back-end)**

**File:** `back-end/app/services/s3_service.py`

```python
class S3Service:
    async def download_file(self, file_key: str) -> bytes:
        """
        Download file from S3
        
        Args:
            file_key: e.g., "private/faces/student_4/01_face_front_20251027.jpg"
        
        Returns:
            File content as bytes
        """
```

---

## 🔐 Security

### **Authentication & Authorization:**

1. **Admin Only:** Chỉ admin mới có quyền approve
   ```python
   current_user: User = Depends(require_admin)
   ```

2. **JWT Token:** Backend → AI-service (optional)
   - Có thể thêm JWT token vào header nếu cần

3. **Private S3 Bucket:**
   - Ảnh khuôn mặt lưu trong folder `private/faces/`
   - Không public URL
   - Presigned URLs (expires trong 2 giờ)

---

## 📊 Data Flow

### **Request Example:**

```bash
POST /api/v1/admin/face-registrations/34/approve
Authorization: Bearer <admin_token>

{
  "note": "Approved by admin"
}
```

### **AI Service Request:**

```json
{
  "student_code": "SV862155",
  "student_id": 4,
  "face_images": [
    {
      "image_base64": "/9j/4AAQSkZJRgABAQAA...",
      "step_name": "face_front",
      "step_number": 1
    },
    // ... 13 more images
  ],
  "use_augmentation": true,
  "augmentation_count": 5
}
```

### **AI Service Response:**

```json
{
  "success": true,
  "student_code": "SV862155",
  "student_id": 4,
  "total_original_images": 14,
  "total_embeddings_created": 84,
  "embeddings": [
    {
      "step_name": "face_front",
      "step_number": 1,
      "embedding": [0.123, 0.456, ..., 0.789],  // 512 floats
      "augmented_count": 5
    },
    // ... 13 more
  ],
  "processing_time_seconds": 12.5,
  "message": "Successfully registered 14 face images with 84 total embeddings"
}
```

### **Database Records Created:**

```sql
-- 14 records in face_embeddings table
INSERT INTO face_embeddings (student_id, student_code, embedding, status, ...)
VALUES 
  (4, 'SV862155', '[0.123,0.456,...]'::vector, 'approved', ...),
  (4, 'SV862155', '[0.234,0.567,...]'::vector, 'approved', ...),
  ...  -- 12 more
```

---

## ⚙️ Configuration

### **Environment Variables (Back-end)**

```bash
# .env
AI_SERVICE_URL=http://localhost:8001
BACKEND_BASE_URL=http://localhost:8000
AI_SERVICE_SECRET=shared-secret-key
```

### **Environment Variables (AI-service)**

```bash
# .env
TTA_ENABLED=True  # Enable Test-Time Augmentation
RECOGNIZER_CHECKPOINT=models/model_ir_se50.pth
RECOGNIZER_DEVICE=cuda  # or 'cpu'
```

---

## 🧪 Testing

### **1. Test Admin Approve Flow:**

```bash
# 1. Get pending registrations
curl -X GET "http://localhost:8000/api/v1/admin/face-registrations?status=pending_admin_review" \
  -H "Authorization: Bearer <admin_token>"

# 2. Approve registration
curl -X POST "http://localhost:8000/api/v1/admin/face-registrations/34/approve" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"note": "Approved by admin"}'

# Expected Response:
{
  "success": true,
  "message": "Face registration approved and embeddings created successfully",
  "registration_id": 34,
  "status": "approved",
  "embeddings_created": 14,
  "processing_time_seconds": 12.5
}
```

### **2. Verify Embeddings in Database:**

```sql
-- Check embeddings were created
SELECT 
    id,
    student_code,
    image_path,
    status,
    uploaded_at
FROM face_embeddings
WHERE student_code = 'SV862155'
ORDER BY id;

-- Should return 14 records
```

### **3. Test AI Service Directly:**

```bash
curl -X POST "http://localhost:8001/api/v1/register-face" \
  -H "Content-Type: application/json" \
  -d '{
    "student_code": "SV862155",
    "student_id": 4,
    "face_images": [...],  # 14 base64 images
    "use_augmentation": true,
    "augmentation_count": 5
  }'
```

---

## 🐛 Troubleshooting

### **Common Issues:**

#### **1. AI Service Connection Error**

```
Error: Cannot connect to AI service: Connection refused
```

**Solution:**
- Check AI-service is running: `http://localhost:8001/api/v1/health`
- Verify `AI_SERVICE_URL` in `.env`
- Check firewall rules

#### **2. S3 Download Failed**

```
Error: File not found: private/faces/student_4/01_face_front.jpg
```

**Solution:**
- Verify S3 keys in `verification_data`
- Check S3 credentials
- Ensure files were uploaded during student confirmation

#### **3. Embedding Dimension Mismatch**

```
Error: Invalid embedding dimension: 256, expected 512
```

**Solution:**
- Check AI model checkpoint is IR-SE50 (512-dim output)
- Verify TTA settings

#### **4. Database Timeout**

```
Error: Failed to save embeddings: connection timeout
```

**Solution:**
- Check PostgreSQL is running
- Verify `DATABASE_URL`
- Increase connection timeout

---

## 📈 Performance Metrics

### **Expected Processing Time:**

| Task | Time (CPU) | Time (GPU) |
|------|-----------|-----------|
| Download 14 images from S3 | ~2s | ~2s |
| Extract 14 embeddings (no aug) | ~8s | ~2s |
| Extract 84 embeddings (with aug) | ~30s | ~6s |
| Save to database | ~0.5s | ~0.5s |
| **Total (with augmentation)** | **~32s** | **~8s** |

### **Optimization Tips:**

1. **Use GPU:** Set `RECOGNIZER_DEVICE=cuda`
2. **Batch processing:** AI-service processes all 14 images in one request
3. **Database indexing:** pgvector IVFFlat index for fast similarity search
4. **Caching:** Consider caching embeddings in Redis for active sessions

---

## 🎉 Success Criteria

✅ Admin approve → Embeddings created successfully  
✅ 14 records in `face_embeddings` table  
✅ Status changed to `approved`  
✅ Student can now be recognized in attendance sessions  
✅ Processing time < 10 seconds (with GPU)  

---

## 📚 Related Documentation

- [FACE_REGISTRATION_WORKFLOW.md](./FACE_REGISTRATION_WORKFLOW.md) - Full workflow
- [AI_INTEGRATION_ARCHITECTURE.md](./AI_INTEGRATION_ARCHITECTURE.md) - Architecture
- AI-service README - API documentation

---

## 🔄 Next Steps

After successful approval:

1. **Student Dashboard:** Show "Face registered ✅" status
2. **Attendance Sessions:** Student can now be recognized
3. **Admin Panel:** Show embedding count (14) in student details
4. **Analytics:** Track registration success rate

---

**Created:** 2025-10-28  
**Last Updated:** 2025-10-28  
**Version:** 1.0.0
