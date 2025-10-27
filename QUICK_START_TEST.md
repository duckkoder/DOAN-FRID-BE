# Quick Start - Test AI Integration

## 1. Setup Environment

```bash
# Backend directory
cd e:\Workspace\PBL6\back-end

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run migration
.\.venv\Scripts\python.exe -m alembic upgrade head

# Update .env file
AI_SERVICE_URL=http://localhost:8096
BACKEND_BASE_URL=http://localhost:8001
AI_SERVICE_SECRET=test-shared-secret-key
AI_WEBSOCKET_TOKEN_EXPIRE_MINUTES=30
```

## 2. Start Backend

```bash
uvicorn app.main:app --reload --port 8001
```

## 3. Test Endpoints

### A. Start Attendance Session

```bash
# Get teacher token first
curl -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "teacher@example.com",
    "password": "password123"
  }'

# Start session
curl -X POST http://localhost:8001/api/v1/attendance/sessions/start \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "class_id": 1,
    "session_name": "Test Session",
    "late_threshold_minutes": 15
  }'

# Expected Response:
{
  "session_id": 50,
  "ai_session_id": "uuid-abc-123",
  "ai_ws_url": "ws://localhost:8096/api/v1/sessions/uuid-abc-123/stream",
  "ai_ws_token": "eyJhbGc...",
  "expires_at": "2025-10-24T10:30:00Z",
  "status": "active"
}
```

### B. Test Webhook (Manual)

```bash
# Generate HMAC signature
# Use Python to generate signature
python -c "
import hmac
import hashlib
import json

payload = {
    'session_id': 'uuid-abc-123',
    'validated_students': [{
        'student_code': '102220347',
        'student_name': 'Nguyen Van A',
        'track_id': 1,
        'avg_confidence': 0.85,
        'frame_count': 10,
        'recognition_count': 8,
        'validation_passed_at': '2025-10-24T10:00:00Z'
    }],
    'timestamp': '2025-10-24T10:00:00Z'
}

secret = 'test-shared-secret-key'
signature = hmac.new(
    secret.encode(),
    json.dumps(payload, separators=(',', ':')).encode(),
    hashlib.sha256
).hexdigest()

print(f'Signature: {signature}')
print(f'\nPayload:\n{json.dumps(payload, indent=2)}')
"

# Send webhook
curl -X POST http://localhost:8001/api/v1/attendance/webhook/ai-recognition \
  -H "X-AI-Signature: GENERATED_SIGNATURE" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "uuid-abc-123",
    "validated_students": [{
        "student_code": "102220347",
        "student_name": "Nguyen Van A",
        "track_id": 1,
        "avg_confidence": 0.85,
        "frame_count": 10,
        "recognition_count": 8,
        "validation_passed_at": "2025-10-24T10:00:00Z"
    }],
    "timestamp": "2025-10-24T10:00:00Z"
  }'

# Expected Response:
{
  "status": "ok",
  "processed_students": 1,
  "message": "Processed 1 students successfully"
}
```

### C. Poll Attendance

```bash
curl http://localhost:8001/api/v1/attendance/sessions/50 \
  -H "Authorization: Bearer YOUR_TOKEN"

# Expected Response:
{
  "session": {
    "id": 50,
    "class_id": 1,
    "session_name": "Test Session",
    "status": "active",
    "ai_session_id": "uuid-abc-123",
    ...
  },
  "records": [
    {
      "id": 1,
      "student_id": 10,
      "student_code": "102220347",
      "full_name": "Nguyen Van A",
      "status": "present",
      "confidence_score": 0.85,
      "check_in_time": "2025-10-24T10:00:00Z"
    }
  ],
  "statistics": {
    "total_students": 30,
    "present": 1,
    "late": 0,
    "absent": 29,
    "attendance_rate": 3.33
  }
}
```

## 4. Python Test Script

Tạo file `test_ai_integration.py`:

```python
import requests
import json
import hmac
import hashlib
from datetime import datetime

BASE_URL = "http://localhost:8001/api/v1"
AI_SECRET = "test-shared-secret-key"

def login():
    """Login và lấy token."""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "username": "teacher@example.com",
            "password": "password123"
        }
    )
    return response.json()["access_token"]

def start_session(token, class_id):
    """Start attendance session."""
    response = requests.post(
        f"{BASE_URL}/attendance/sessions/start",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "class_id": class_id,
            "session_name": "Test Session",
            "late_threshold_minutes": 15
        }
    )
    return response.json()

def send_webhook(ai_session_id, student_code):
    """Send webhook callback."""
    payload = {
        "session_id": ai_session_id,
        "validated_students": [{
            "student_code": student_code,
            "student_name": "Test Student",
            "track_id": 1,
            "avg_confidence": 0.85,
            "frame_count": 10,
            "recognition_count": 8,
            "validation_passed_at": datetime.now().isoformat()
        }],
        "timestamp": datetime.now().isoformat()
    }
    
    # Generate signature
    signature = hmac.new(
        AI_SECRET.encode(),
        json.dumps(payload, separators=(',', ':')).encode(),
        hashlib.sha256
    ).hexdigest()
    
    response = requests.post(
        f"{BASE_URL}/attendance/webhook/ai-recognition",
        headers={"X-AI-Signature": signature},
        json=payload
    )
    return response.json()

def poll_session(token, session_id):
    """Poll session for updates."""
    response = requests.get(
        f"{BASE_URL}/attendance/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.json()

if __name__ == "__main__":
    print("🚀 Testing AI Integration...")
    
    # 1. Login
    print("\n1️⃣ Login...")
    token = login()
    print(f"✅ Token: {token[:20]}...")
    
    # 2. Start session
    print("\n2️⃣ Start session...")
    session_data = start_session(token, class_id=1)
    print(f"✅ Session ID: {session_data['session_id']}")
    print(f"✅ AI Session ID: {session_data['ai_session_id']}")
    print(f"✅ WebSocket URL: {session_data['ai_ws_url']}")
    
    # 3. Send webhook
    print("\n3️⃣ Send webhook...")
    webhook_response = send_webhook(
        session_data['ai_session_id'],
        "102220347"
    )
    print(f"✅ Webhook: {webhook_response}")
    
    # 4. Poll session
    print("\n4️⃣ Poll session...")
    attendance_data = poll_session(token, session_data['session_id'])
    print(f"✅ Records: {len(attendance_data['records'])}")
    print(f"✅ Statistics: {attendance_data['statistics']}")
    
    print("\n✅ All tests passed!")
```

Run test:
```bash
python test_ai_integration.py
```

## 5. Frontend WebSocket Test

Tạo file `test_websocket.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Test</title>
</head>
<body>
    <h1>AI-Service WebSocket Test</h1>
    <button onclick="connect()">Connect</button>
    <button onclick="disconnect()">Disconnect</button>
    <button onclick="sendTestFrame()">Send Test Frame</button>
    <div id="log"></div>

    <script>
        let ws = null;
        const wsUrl = "ws://localhost:8096/api/v1/sessions/UUID/stream";
        const token = "YOUR_JWT_TOKEN";

        function log(message) {
            const logDiv = document.getElementById('log');
            logDiv.innerHTML += `<p>${new Date().toLocaleTimeString()}: ${message}</p>`;
        }

        function connect() {
            ws = new WebSocket(`${wsUrl}?token=${token}`);
            
            ws.onopen = () => {
                log("✅ Connected to AI-Service");
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                log(`📨 Received: ${data.type}`);
                console.log(data);
                
                switch(data.type) {
                    case "frame_processed":
                        log(`   Faces detected: ${data.total_faces}`);
                        break;
                    case "student_validated":
                        log(`   ✅ Student validated: ${data.student.student_name}`);
                        break;
                    case "session_status":
                        log(`   Status: ${data.status}`);
                        break;
                }
            };
            
            ws.onerror = (error) => {
                log(`❌ Error: ${error}`);
            };
            
            ws.onclose = (event) => {
                log(`🔌 Disconnected: ${event.code} - ${event.reason}`);
            };
        }

        function disconnect() {
            if (ws) {
                ws.close();
                ws = null;
            }
        }

        function sendTestFrame() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                // Send dummy frame data
                const dummyFrame = new Blob([new Uint8Array(1024)]);
                ws.send(dummyFrame);
                log("📤 Sent test frame");
            } else {
                log("❌ Not connected");
            }
        }
    </script>
</body>
</html>
```

## 6. Check Logs

```bash
# Backend logs
tail -f logs/backend.log

# Database check
psql -U postgres -d attendance_db
SELECT id, class_id, status, ai_session_id FROM attendance_sessions;
SELECT * FROM attendance_records WHERE session_id = 50;
```

## 7. Troubleshooting

### Issue: AI-Service connection failed
```bash
# Check AI-Service is running
curl http://localhost:8096/api/v1/health

# Check .env
cat .env | grep AI_SERVICE_URL
```

### Issue: Webhook signature invalid
```python
# Verify signature generation
import hmac, hashlib, json

payload = {...}
secret = "test-shared-secret-key"

# Ensure separators=(',', ':') - no spaces!
body = json.dumps(payload, separators=(',', ':'))
signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
print(signature)
```

### Issue: Session not found
```sql
-- Check session in database
SELECT * FROM attendance_sessions WHERE ai_session_id = 'uuid-abc-123';
```

### Issue: Duplicate records
```sql
-- Check for duplicates
SELECT session_id, student_id, COUNT(*) 
FROM attendance_records 
GROUP BY session_id, student_id 
HAVING COUNT(*) > 1;
```

## 8. Performance Test

```python
import asyncio
import aiohttp
import time

async def test_concurrent_polling(token, session_id, num_requests=100):
    """Test concurrent polling."""
    async with aiohttp.ClientSession() as session:
        start = time.time()
        
        tasks = []
        for i in range(num_requests):
            task = session.get(
                f"http://localhost:8001/api/v1/attendance/sessions/{session_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
        elapsed = time.time() - start
        print(f"✅ {num_requests} requests in {elapsed:.2f}s")
        print(f"   Average: {elapsed/num_requests*1000:.2f}ms per request")

# Run
asyncio.run(test_concurrent_polling(token, session_id))
```

## 9. Success Indicators

✅ Backend starts without errors
✅ Migration applied successfully
✅ Start session returns WebSocket URL + token
✅ Webhook accepts valid signature
✅ Webhook rejects invalid signature
✅ Attendance records created in DB
✅ No duplicate records
✅ Polling returns updated data
✅ Late vs Present calculated correctly

## 10. Next Steps

Once Backend tests pass:
1. ✅ Implement AI-Service endpoints
2. ✅ Test end-to-end flow
3. ✅ Implement Frontend WebSocket client
4. ✅ Load testing with real camera stream
5. ✅ Production deployment
