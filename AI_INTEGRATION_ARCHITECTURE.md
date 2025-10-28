# AI-Service Integration Architecture

## Tổng Quan Kiến Trúc

```
┌─────────┐                                    ┌────────────┐
│ Client  │◄────────WebSocket─────────────────►│ AI-Service │
│ (React) │                                    │            │
└─────────┘                                    └────────────┘
     │                                               │
     │ HTTP                                          │ HTTP Callback
     │                                               │
     ▼                                               ▼
┌─────────┐                                    ┌─────────┐
│ Backend │────────────────────────────────────│   DB    │
│(FastAPI)│                                    │Postgres │
└─────────┘                                    └─────────┘
```

## Flow Điểm Danh Chi Tiết

### 1. Start Session (Teacher)

```typescript
// Client: Teacher starts attendance session
POST /api/v1/attendance/sessions/start
{
  "class_id": 123,
  "session_name": "Buổi học ngày 24/10",
  "late_threshold_minutes": 15
}

// Backend Response:
{
  "session_id": 50,                    // Backend session ID
  "ai_session_id": "uuid-abc-123",     // AI Service session ID
  "ai_ws_url": "ws://ai-service/api/v1/sessions/uuid-abc-123/stream",
  "ai_ws_token": "eyJhbGc...",         // JWT token
  "expires_at": "2025-10-24T10:30:00Z",
  "status": "active"
}
```

**Backend Flow:**
1. ✅ Validate teacher permission
2. ✅ Create session in DB với `status="pending"`
3. ✅ Generate JWT token cho WebSocket
4. ✅ Call AI-Service: `POST /api/v1/sessions`
5. ✅ Receive `ai_session_id` từ AI-Service
6. ✅ Update session: `ai_session_id`, `status="active"`
7. ✅ Return response với WebSocket URL + token

### 2. Client Connect WebSocket (Teacher)

```javascript
// Client connects directly to AI-Service
const ws = new WebSocket(
  `${ai_ws_url}?token=${ai_ws_token}`
);

ws.onopen = () => {
  console.log("Connected to AI-Service");
  startCamera();
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case "frame_processed":
      // Real-time detections với bbox
      updateDetections(data.detections);
      break;
      
    case "student_validated":
      // Sinh viên pass validation
      addValidatedStudent(data.student);
      break;
      
    case "session_status":
      // Session statistics
      updateStats(data.stats);
      break;
  }
};

// Send frames continuously
function sendFrame(imageBlob) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(imageBlob);
  }
}
```

### 3. AI-Service Processing

**AI-Service nhận frame và xử lý:**
```python
# AI-Service: app/api/v1/endpoints/frames.py
@router.websocket("/sessions/{session_id}/stream")
async def stream_frames(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...)
):
    # 1. Verify JWT token
    payload = verify_jwt_token(token)
    
    # 2. Check session exists
    session = await session_manager.get_session(session_id)
    
    # 3. Check permission
    if not verify_permission(payload, session):
        await websocket.close(code=1008)
        return
    
    await websocket.accept()
    
    async for frame_data in websocket.iter_bytes():
        # 4. Detect faces
        detections = face_detector.detect(frame_data)
        
        # 5. Track faces
        tracks = tracker.update(detections)
        
        # 6. Recognize faces
        for track in tracks:
            recognition = face_recognizer.recognize(
                track.embedding,
                session.student_embeddings
            )
            
            # 7. Validate (multi-frame)
            if validator.should_validate(track):
                validated = validator.validate(track)
                
                if validated:
                    # 8. Send callback to Backend
                    await send_callback_to_backend(
                        session_id,
                        validated_student
                    )
                    
                    # 9. Send validated message to client
                    await websocket.send_json({
                        "type": "student_validated",
                        "student": validated_student
                    })
        
        # 10. Send frame_processed message
        await websocket.send_json({
            "type": "frame_processed",
            "detections": detections,
            "total_faces": len(detections)
        })
```

### 4. AI-Service → Backend Callback

```python
# AI-Service sends callback when student validated
POST http://backend/api/v1/attendance/webhook/ai-recognition
Headers:
  X-AI-Signature: hmac_sha256(payload, shared_secret)
  
Body:
{
  "session_id": "uuid-abc-123",
  "validated_students": [
    {
      "student_code": "102220347",
      "student_name": "Nguyen Van A",
      "track_id": 1,
      "avg_confidence": 0.85,
      "frame_count": 10,
      "recognition_count": 8,
      "validation_passed_at": "2025-10-24T10:00:03Z"
    }
  ],
  "timestamp": "2025-10-24T10:00:03Z"
}
```

**Backend Webhook Handler:**
```python
# Backend: app/api/v1/attendance.py
@router.post("/webhook/ai-recognition")
async def ai_recognition_webhook(
    payload: AICallbackPayload,
    x_ai_signature: str = Header(...)
):
    # 1. ✅ Verify HMAC signature
    verify_signature(payload, x_ai_signature)
    
    # 2. ✅ Find session by ai_session_id
    session = db.query(AttendanceSession).filter(
        AttendanceSession.ai_session_id == payload.session_id
    ).first()
    
    # 3. ✅ Process validated students
    for student_data in payload.validated_students:
        # Find student
        student = db.query(Student).filter(
            Student.student_code == student_data.student_code
        ).first()
        
        # ✅ Idempotency check
        existing = db.query(AttendanceRecord).filter(
            AttendanceRecord.session_id == session.id,
            AttendanceRecord.student_id == student.id
        ).first()
        
        if existing:
            continue  # Skip duplicate
        
        # Calculate status (present/late)
        is_late = (datetime.utcnow() - session.start_time).total_seconds() / 60 > session.late_threshold_minutes
        
        # Create attendance record
        record = AttendanceRecord(
            session_id=session.id,
            student_id=student.id,
            status="late" if is_late else "present",
            check_in_time=student_data.validation_passed_at,
            confidence_score=student_data.avg_confidence,
            recognition_method="AI"
        )
        db.add(record)
    
    db.commit()
    
    return {"status": "ok", "processed_students": len(payload.validated_students)}
```

### 5. Client Polling (All Users)

```javascript
// Client polls Backend để update UI
async function pollAttendance(sessionId) {
  let interval = 2000; // Start with 2s
  let lastRecordCount = 0;
  
  const poll = async () => {
    const response = await fetch(
      `/api/v1/attendance/sessions/${sessionId}`
    );
    const data = await response.json();
    
    // Update UI
    updateAttendanceList(data.records);
    updateStatistics(data.statistics);
    
    // Smart interval adjustment
    if (data.records.length > lastRecordCount) {
      interval = 2000; // Reset to 2s when new data
    } else {
      interval = Math.min(interval * 1.5, 10000); // Max 10s
    }
    
    lastRecordCount = data.records.length;
    
    // Continue polling if session active
    if (data.status === "active") {
      setTimeout(poll, interval);
    }
  };
  
  poll();
}
```

## Security

### 1. WebSocket Authentication

**JWT Token Structure:**
```json
{
  "user_id": 123,
  "session_id": 50,
  "role": "teacher",
  "type": "websocket",
  "exp": 1729764600
}
```

**AI-Service verifies:**
- ✅ Token signature (JWT secret from Backend)
- ✅ Token type = "websocket"
- ✅ Token not expired
- ✅ User has permission to session

### 2. Webhook Security

**HMAC-SHA256 Signature:**
```python
# AI-Service signs payload
signature = hmac.new(
    SHARED_SECRET.encode(),
    json.dumps(payload).encode(),
    hashlib.sha256
).hexdigest()

# Backend verifies
expected = hmac.new(
    SHARED_SECRET.encode(),
    request_body,
    hashlib.sha256
).hexdigest()

if not hmac.compare_digest(signature, expected):
    raise HTTPException(401, "Invalid signature")
```

### 3. Rate Limiting

**AI-Service WebSocket:**
```python
# Max 30 FPS
if time.time() - last_frame_time < 1/30:
    continue

# Max frame size: 2MB
if len(frame_data) > 2 * 1024 * 1024:
    await websocket.send_json({
        "type": "error",
        "message": "Frame too large"
    })
```

## Error Handling

### 1. AI-Service Unavailable

```python
# Backend: Start session fails
try:
    ai_response = await ai_service_client.create_session(...)
except httpx.HTTPError:
    # Rollback session
    db.delete(new_session)
    db.commit()
    
    raise HTTPException(
        503,
        "AI-Service không khả dụng"
    )
```

### 2. WebSocket Disconnect

```javascript
// Client: Auto-reconnect
ws.onclose = (event) => {
  if (event.code === 1008) {
    // Unauthorized/Expired
    alert("Session đã hết hạn");
    return;
  }
  
  // Retry with exponential backoff
  if (reconnectAttempts < 3) {
    setTimeout(() => {
      reconnect();
    }, 1000 * reconnectAttempts);
  }
};
```

### 3. Callback Failure

```python
# AI-Service: Retry callback
async def send_callback_with_retry(
    session_id: str,
    validated_student: dict,
    max_retries: int = 3
):
    for attempt in range(max_retries):
        try:
            response = await http_client.post(
                callback_url,
                json=payload,
                headers={"X-AI-Signature": signature}
            )
            response.raise_for_status()
            break
        except httpx.HTTPError as e:
            if attempt == max_retries - 1:
                logger.error(f"Callback failed after {max_retries} retries")
                # Store in dead letter queue
                await store_failed_callback(payload)
```

## Database Schema

### AttendanceSession

```sql
ALTER TABLE attendance_sessions 
ADD COLUMN ai_session_id VARCHAR(255) UNIQUE,
ADD COLUMN status VARCHAR(50) DEFAULT 'pending';

-- Status values:
-- 'pending': Session created, waiting for AI-Service
-- 'active': AI-Service ready, accepting frames
-- 'finished': Session ended
```

### AttendanceRecord

```sql
-- Existing columns:
-- id, session_id, student_id, status, check_in_time
-- confidence_score, recognition_method, created_at
```

## Environment Variables

```bash
# Backend .env
AI_SERVICE_URL=http://localhost:8096
BACKEND_BASE_URL=http://localhost:8001
AI_SERVICE_SECRET=shared-secret-key-change-this
AI_WEBSOCKET_TOKEN_EXPIRE_MINUTES=30
```

```bash
# AI-Service .env
BACKEND_JWT_SECRET=same-as-backend-secret-key
BACKEND_CALLBACK_SECRET=shared-secret-key-change-this
```

## API Endpoints Summary

### Backend

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/attendance/sessions/start` | Start session với AI-Service |
| POST | `/api/v1/attendance/webhook/ai-recognition` | Webhook từ AI-Service |
| GET | `/api/v1/attendance/sessions/{id}` | Polling endpoint |
| POST | `/api/v1/attendance/sessions/{id}/end` | End session |

### AI-Service

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/sessions` | Create session |
| WS | `/api/v1/sessions/{id}/stream` | WebSocket stream frames |
| POST | `/api/v1/sessions/{id}/end` | End session |
| GET | `/api/v1/health` | Health check |

## Testing Flow

### 1. Start Session
```bash
curl -X POST http://localhost:8001/api/v1/attendance/sessions/start \
  -H "Authorization: Bearer {teacher_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "class_id": 1,
    "session_name": "Test Session"
  }'
```

### 2. Connect WebSocket
```javascript
const ws = new WebSocket(
  "ws://localhost:8096/api/v1/sessions/uuid-abc/stream?token=eyJhbGc..."
);
```

### 3. Poll Attendance
```bash
curl http://localhost:8001/api/v1/attendance/sessions/50 \
  -H "Authorization: Bearer {token}"
```

### 4. Test Webhook (Manual)
```bash
# Generate signature
echo -n '{"session_id":"uuid","validated_students":[...]}' | \
  openssl dgst -sha256 -hmac "shared-secret" | \
  awk '{print $2}'

curl -X POST http://localhost:8001/api/v1/attendance/webhook/ai-recognition \
  -H "X-AI-Signature: {signature}" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

## Monitoring & Logging

### Backend Logs
```python
logger.info("Session created", extra={
    "session_id": session.id,
    "ai_session_id": ai_session_id,
    "class_id": class_id
})

logger.info("Attendance record created", extra={
    "session_id": session.id,
    "student_code": student_code,
    "confidence": confidence
})
```

### AI-Service Logs
```python
logger.info("Session initialized", extra={
    "session_id": session_id,
    "student_count": len(student_codes),
    "gpu_memory_used": get_gpu_memory()
})

logger.info("Student validated", extra={
    "session_id": session_id,
    "student_code": student_code,
    "avg_confidence": confidence,
    "frame_count": frame_count
})
```

## Performance Considerations

1. **WebSocket Connection**: Direct client → AI-Service giảm latency
2. **HTTP Polling**: Smart interval (2s → 10s) giảm load
3. **Idempotency**: Prevent duplicate records
4. **Caching**: AI-Service cache embeddings trong VRAM
5. **Rate Limiting**: Max 30 FPS, max 2MB frame size

## Next Steps

- [ ] Implement AI-Service endpoints
- [ ] Add monitoring dashboard
- [ ] Setup alert system cho failures
- [ ] Load testing với concurrent sessions
- [ ] Optimize polling strategy
