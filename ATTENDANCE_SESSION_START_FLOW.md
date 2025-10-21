# Flow Bắt Đầu Phiên Điểm Danh - Implementation Guide

## Overview

Khi giáo viên bắt đầu phiên điểm danh, Backend sẽ gọi AI-Service để load embeddings vào VRAM (GPU memory).

## Complete Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: Client Request                                              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
Frontend (Teacher)                  │
POST /api/v1/attendance/sessions/start
{
  "class_id": 123,
  "session_name": "Điểm danh 21/10/2025",
  "late_threshold_minutes": 15
}
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: Backend - AttendanceService.start_session()                │
└─────────────────────────────────────────────────────────────────────┘

File: app/services/attendance_service.py

async def start_session(...):
    # 1. Validate teacher permissions
    # 2. Check no ongoing session exists
    
    # 3. Get all student codes in class
    class_members = self.member_repo.get_multi_by_filter(class_id=class_id)
    student_codes = [member.student.student_code for member in class_members]
    # → student_codes = ["102220312", "102220347", ..., "102220411"]  # 100 codes
    
    # 4. Create session in database
    new_session = self.session_repo.create({
        "class_id": class_id,
        "status": "ongoing",
        ...
    })
    
    # 5. ⚡ Call AI-Service to load embeddings to VRAM
    await self._initialize_ai_session(
        session_id=new_session.id,
        class_id=class_id,
        student_codes=student_codes  # 100 codes
    )
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: Backend → AI-Service                                       │
└─────────────────────────────────────────────────────────────────────┘

File: app/services/attendance_service.py

async def _initialize_ai_session(...):
    payload = {
        "class_id": "123",
        "student_codes": ["102220312", "102220347", ..., "102220411"],  # 100
        "backend_callback_url": "http://backend:8080/api/v1/attendance/webhook/ai-recognition",
        "max_duration_minutes": 120
    }
    
    # POST to AI-Service
    response = await client.post(
        "http://ai-service:8000/api/v1/sessions",
        json=payload
    )
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: AI-Service - SessionManager.create_session()               │
└─────────────────────────────────────────────────────────────────────┘

File: AI-service/app/services/session_manager.py

async def create_session(request: SessionCreateRequest):
    # 1. Create session_id = uuid4()
    session_id = "550e8400-e29b-41d4-a716-446655440000"
    
    # 2. Query embeddings from PostgreSQL pgvector (1 QUERY DUY NHẤT!)
    embeddings_data = await _load_embeddings_from_database(
        student_codes=["102220312", "102220347", ..., "102220411"]  # 100
    )
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 5: AI-Service → PostgreSQL pgvector                           │
└─────────────────────────────────────────────────────────────────────┘

File: AI-service/app/services/database_service.py

def get_embeddings_by_student_codes(student_codes):
    query = """
        SELECT student_code, student_id, embedding
        FROM face_embeddings
        WHERE student_code = ANY(%s)
          AND status = 'approved'
        ORDER BY student_code, id
    """
    cursor.execute(query, (student_codes, ))
    rows = cursor.fetchall()
    
    # Returns: 500 rows (100 students × 5 embeddings/student avg)
    # [
    #   {"student_code": "102220312", "student_id": 101, "embedding": [0.1, 0.2, ..., 0.5]},
    #   {"student_code": "102220312", "student_id": 101, "embedding": [0.2, 0.3, ..., 0.6]},
    #   ...
    # ]
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 6: AI-Service - Load to VRAM (GPU Memory)                     │
└─────────────────────────────────────────────────────────────────────┘

File: AI-service/app/services/session_manager.py

async def _load_embeddings_to_vram(session_data, embeddings_data):
    # 1. Extract embeddings: List[List[float]] (500, 512)
    embeddings_list = [emb['embedding'] for emb in embeddings_data]  # 500 vectors
    labels_list = [emb['student_code'] for emb in embeddings_data]
    
    # 2. Stack to numpy array
    embeddings_array = np.stack(embeddings_list)  # Shape: (500, 512)
    
    # 3. Convert to torch tensor
    embeddings_tensor = torch.from_numpy(embeddings_array).float()
    
    # 4. Move to GPU
    if torch.cuda.is_available():
        embeddings_tensor = embeddings_tensor.cuda()
    
    # 5. Store in SessionData (in memory)
    session_data.gallery_embeddings = embeddings_tensor  # On GPU!
    session_data.gallery_labels = labels_list
    session_data.embedding_count = 500
    session_data.embeddings_loaded = True
    
    # Memory on GPU: 500 × 512 × 4 bytes = ~1 MB
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 7: AI-Service Response to Backend                             │
└─────────────────────────────────────────────────────────────────────┘

Response:
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "class_id": "123",
  "status": "active",
  "embeddings_loaded": true,  // ✅ Important!
  "total_frames_processed": 0
}
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 8: Backend validates & responds to Client                     │
└─────────────────────────────────────────────────────────────────────┘

File: app/services/attendance_service.py

async def _initialize_ai_session(...):
    ai_session_data = response.json()
    
    # Verify embeddings loaded
    if not ai_session_data.get("embeddings_loaded", False):
        raise Exception("AI-Service failed to load embeddings to VRAM")
    
    return ai_session_data

# If success → return SessionResponse to client
# If fail → rollback database session
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ DONE: Ready to Process Frames!                                     │
└─────────────────────────────────────────────────────────────────────┘

Now when Frontend sends frames:
- All embeddings are already in VRAM
- No database queries needed
- Face comparison happens in GPU (<1ms)
```

## Implementation Files

### Backend Files Modified

1. **`app/services/attendance_service.py`**
   - Added `_initialize_ai_session()` method
   - Updated `start_session()` to call AI-Service

2. **`app/core/config.py`**
   - Added `BACKEND_BASE_URL` for callback URL

### AI-Service Files (Already Implemented)

1. **`app/services/database_service.py`**
   - Query pgvector with `get_embeddings_by_student_codes()`

2. **`app/services/session_manager.py`**
   - `create_session()` - Create session and load embeddings
   - `_load_embeddings_from_database()` - Query PostgreSQL
   - `_load_embeddings_to_vram()` - Load to GPU

3. **`app/api/v1/endpoints/sessions.py`**
   - `POST /sessions` endpoint

## Code Details

### Backend: AttendanceService.start_session()

```python
async def start_session(self, current_user: User, request: StartSessionRequest):
    # ... validation code ...
    
    # Get student codes
    class_members = self.member_repo.get_multi_by_filter(class_id=request.class_id)
    student_codes = [
        member.student.student_code 
        for member in class_members 
        if member.student and member.student.student_code
    ]
    
    # Create database session
    new_session = self.session_repo.create({...})
    
    # ⚡ Initialize AI-Service session
    try:
        await self._initialize_ai_session(
            session_id=new_session.id,
            class_id=request.class_id,
            student_codes=student_codes
        )
    except Exception as e:
        # Rollback if AI-Service fails
        self.session_repo.delete(new_session.id)
        raise HTTPException(503, f"Cannot initialize AI-Service: {e}")
    
    return SessionResponse.model_validate(new_session)
```

### Backend: _initialize_ai_session()

```python
async def _initialize_ai_session(
    self,
    session_id: int,
    class_id: int,
    student_codes: List[str]
) -> Dict[str, Any]:
    """Load embeddings vào VRAM qua AI-Service."""
    
    callback_url = f"{settings.BACKEND_BASE_URL}/api/v1/attendance/webhook/ai-recognition"
    
    payload = {
        "class_id": str(class_id),
        "student_codes": student_codes,  # 100 codes
        "backend_callback_url": callback_url,
        "max_duration_minutes": 120
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.AI_SERVICE_URL}/api/v1/sessions",
            json=payload
        )
        
        ai_session_data = response.json()
        
        # Verify success
        if not ai_session_data.get("embeddings_loaded", False):
            raise Exception("Failed to load embeddings to VRAM")
        
        return ai_session_data
```

## Configuration

### Backend `.env`

```env
# AI Service
AI_SERVICE_URL=http://localhost:8000
BACKEND_BASE_URL=http://localhost:8080

# Database (for face_embeddings table)
DATABASE_URL=postgresql://user:pass@localhost:5432/attendance_db
```

### AI-Service `.env`

```env
# PostgreSQL pgvector
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=attendance_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# GPU
RECOGNIZER_DEVICE=cuda
DETECTOR_DEVICE=cuda
```

## Error Handling

### If AI-Service is Down

```python
# Backend will catch exception and rollback session
try:
    await self._initialize_ai_session(...)
except Exception as e:
    self.session_repo.delete(new_session.id)
    raise HTTPException(503, "AI-Service unavailable")
```

### If No Embeddings Found

```python
# AI-Service will return embeddings_loaded=false
if not ai_session_data.get("embeddings_loaded"):
    # Backend rolls back
    raise Exception("No embeddings loaded")
```

### If Database Connection Failed

```python
# AI-Service's database_service.py will raise exception
# Backend catches and rolls back session
```

## Testing

### 1. Test Backend Endpoint

```bash
# Start session
curl -X POST http://localhost:8080/api/v1/attendance/sessions/start \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "class_id": 1,
    "session_name": "Test Session"
  }'
```

Expected response:
```json
{
  "id": 123,
  "class_id": 1,
  "session_name": "Test Session",
  "status": "ongoing",
  "start_time": "2025-10-21T10:00:00Z"
}
```

### 2. Verify AI-Service Session Created

```bash
# Check AI-Service logs
# Should see:
# ✅ AI-Service session created: 550e8400-...
#    - Students: 100
#    - Embeddings loaded: True
```

### 3. Verify Embeddings in VRAM

```python
# In AI-Service
import torch
print(f"GPU memory: {torch.cuda.memory_allocated() / 1024**2:.2f} MB")
# Should show ~1 MB per session
```

## Performance Metrics

### Session Start Time
- Database query (Backend): ~10ms
- Get student codes: ~20ms
- AI-Service HTTP request: ~50ms
- PostgreSQL query (500 embeddings): ~50-100ms
- Load to VRAM: ~10-20ms
- **Total: ~150-200ms** (one-time cost)

### Frame Processing (After Session Start)
- No database queries!
- All comparisons in VRAM: <1ms
- Total frame processing: 30-70ms

## Callback URL

Callback URL là để AI-Service gọi về Backend khi nhận diện được sinh viên:

```
AI-Service → Backend: POST /api/v1/attendance/webhook/ai-recognition
{
  "session_id": "550e8400-...",
  "class_id": 123,
  "recognized_students": [101, 102, 103],
  "timestamp": "2025-10-21T10:05:23Z"
}
```

Backend xử lý callback:
1. Create attendance records
2. Broadcast via WebSocket to clients

## Next Steps

1. ✅ Test session creation end-to-end
2. 🔄 Update frame processing to use AI-Service session
3. 🔄 Test callback webhook
4. 🔄 Add session cleanup on end_session
5. 🔄 Add monitoring for VRAM usage

## Troubleshooting

### "AI-Service unavailable"
- Check AI-Service is running: `curl http://localhost:8000/health`
- Check AI-Service logs for errors

### "No embeddings loaded"
- Verify students have face_embeddings in database
- Check PostgreSQL pgvector extension is enabled
- Run: `SELECT COUNT(*) FROM face_embeddings WHERE status='approved'`

### "Session creation fails"
- Check Backend logs for exception details
- Verify database connection
- Check AI_SERVICE_URL in .env

---

**Status**: ✅ Implementation Complete
**Location**: `app/services/attendance_service.py`
**Methods**: `start_session()`, `_initialize_ai_session()`
