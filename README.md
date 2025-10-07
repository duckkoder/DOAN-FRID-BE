# 🎓 AI-Powered Attendance System - Backend

Backend API cho hệ thống điểm danh nhận diện khuôn mặt sử dụng AI, được xây dựng với FastAPI và PostgreSQL.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.117+-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-blue.svg)](https://www.postgresql.org/)

---

## 📋 Mục lục

- [Tổng quan](#-tổng-quan)
- [Kiến trúc dự án](#-kiến-trúc-dự-án)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Cài đặt](#-cài-đặt)
- [Cấu hình](#️-cấu-hình)
- [Chạy dự án](#-chạy-dự-án)
- [API Documentation](#-api-documentation)
- [Database Migration](#-database-migration)
- [Development Workflow](#-development-workflow)
- [Testing](#-testing)

---

## 🎯 Tổng quan

Hệ thống backend cung cấp RESTful API cho ứng dụng điểm danh thông minh với các tính năng:

- ✅ **Xác thực & Phân quyền**: JWT-based authentication với 3 roles (Admin, Teacher, Student)
- 🤖 **AI Face Recognition**: Nhận diện khuôn mặt sử dụng deep learning
- 📊 **Quản lý lớp học**: Tạo, quản lý lớp và thành viên
- ✅ **Điểm danh tự động**: Điểm danh qua camera với AI
- 📝 **Quản lý đơn xin nghỉ**: Workflow phê duyệt đơn từ
- 📈 **Báo cáo & Thống kê**: Theo dõi tỷ lệ tham gia

---

## 🏗️ Kiến trúc dự án

Dự án áp dụng **Clean Architecture** với kiến trúc **3 lớp** (3-layer architecture):

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer (Controller)               │
│  - Định nghĩa endpoints                                 │
│  - Request/Response handling                            │
│  - Validation với Pydantic                              │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              Service Layer (Business Logic)             │
│  - Business logic & rules                               │
│  - Orchestration giữa các repositories                  │
│  - Transaction management                               │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│            Repository Layer (Data Access)               │
│  - CRUD operations                                      │
│  - Database queries                                     │
│  - Data mapping                                         │
└────────────────────┬────────────────────────────────────┘
                     │
                ┌────▼────┐
                │PostgreSQL│
                └─────────┘
```

### 🔄 Luồng xử lý Request

```
Client Request
    ↓
[API Layer] → Validate request, parse parameters
    ↓
[Service Layer] → Business logic, authorization checks
    ↓
[Repository Layer] → Database operations (SELECT, INSERT, UPDATE)
    ↓
PostgreSQL Database
    ↓
Return response through layers
    ↓
JSON Response to Client
```

---

## 📁 Cấu trúc thư mục

```
back-end/
│
├── app/                                # Application source code
│   ├── __init__.py
│   ├── main.py                        # 🚀 Entry point - FastAPI app
│   │
│   ├── core/                          # ⚙️ Core configuration & utilities
│   │   ├── __init__.py
│   │   ├── config.py                  # Settings (Database, JWT, CORS)
│   │   ├── enums.py                   # Enums (UserRole, Status, etc)
│   │   ├── security.py                # JWT & Password hashing
│   │   ├── dependencies.py            # FastAPI dependencies (get_db, get_current_user)
│   │   └── exceptions.py              # Custom HTTP exceptions
│   │
│   ├── models/                        # 📊 SQLAlchemy Models (Entity Layer)
│   │   ├── __init__.py
│   │   ├── base.py                    # Base model với id, created_at, updated_at
│   │   ├── user.py                    # User, Admin, Teacher, Student (Inheritance)
│   │   ├── class_model.py             # Class, ClassMember
│   │   ├── attendance.py              # AttendanceSession, AttendanceRecord
│   │   ├── face_embedding.py          # FaceEmbedding
│   │   ├── leave_request.py           # LeaveRequest
│   │   └── system.py                  # RefreshToken, SystemLog
│   │
│   ├── schemas/                       # 📝 Pydantic Schemas (DTO - Data Transfer Objects)
│   │   ├── __init__.py
│   │   ├── base.py                    # Base schemas, PaginatedResponse
│   │   ├── user.py                    # UserCreate, UserUpdate, UserResponse
│   │   ├── auth.py                    # LoginRequest, TokenResponse
│   │   ├── class_schema.py            # ClassCreate, ClassResponse
│   │   ├── attendance.py              # AttendanceSessionCreate, AttendanceRecordResponse
│   │   ├── face_embedding.py          # FaceEmbeddingCreate, FaceEmbeddingResponse
│   │   └── leave_request.py           # LeaveRequestCreate, LeaveRequestResponse
│   │
│   ├── repositories/                  # 🗄️ Data Access Layer
│   │   ├── __init__.py
│   │   ├── base.py                    # BaseRepository với CRUD operations
│   │   ├── user_repository.py         # User database operations
│   │   ├── class_repository.py        # Class database operations
│   │   ├── attendance_repository.py   # Attendance database operations
│   │   ├── face_embedding_repository.py
│   │   └── leave_request_repository.py
│   │
│   ├── services/                      # 🔧 Business Logic Layer
│   │   ├── __init__.py
│   │   ├── base.py                    # BaseService pattern
│   │   ├── auth_service.py            # Authentication, registration, JWT
│   │   ├── user_service.py            # User management logic
│   │   ├── class_service.py           # Class management (create, join, leave)
│   │   ├── attendance_service.py      # Attendance logic (create session, mark)
│   │   ├── face_recognition_service.py # AI face recognition logic
│   │   └── leave_request_service.py   # Leave request approval workflow
│   │
│   ├── api/                           # 🌐 API Layer (Controller)
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py              # Main API router aggregation
│   │       ├── auth.py                # POST /login, /register, /refresh
│   │       ├── users.py               # CRUD /users endpoints
│   │       ├── classes.py             # CRUD /classes endpoints
│   │       ├── attendance.py          # Attendance endpoints
│   │       ├── face_embeddings.py     # Face upload/approval endpoints
│   │       └── leave_requests.py      # Leave request endpoints
│   │
│   ├── database/                      # 🗃️ Database configuration
│   │   ├── __init__.py
│   │   └── session.py                 # SQLAlchemy engine & session
│   │
│   └── utils/                         # 🛠️ Utility functions
│       ├── __init__.py
│       ├── pagination.py              # Pagination helpers
│       ├── validators.py              # Custom validators (email, password)
│       └── file_upload.py             # File handling utilities
│
├── alembic/                           # 📦 Database Migrations
│   ├── versions/                      # Migration files (auto-generated)
│   ├── env.py                         # Alembic environment config
│   └── script.py.mako                 # Migration template
│
├── uploads/                           # 📁 User uploaded files
│   ├── face_images/                   # Face images cho AI training
│   └── evidence_documents/            # Leave request evidence files
│
├── tests/                             # 🧪 Tests (TODO)
│   ├── __init__.py
│   ├── test_auth.py
│   └── test_users.py
│
├── .env                               # 🔐 Environment variables (KHÔNG commit)
├── .env.example                       # 📋 Environment template
├── .gitignore                         # 🚫 Git ignore rules
├── alembic.ini                        # ⚙️ Alembic configuration
├── requirements.txt                   # 📦 Python dependencies
└── README.md                          # 📖 Documentation (file này)
```

### 📌 Giải thích các lớp chính:

| Lớp | Mô tả | Ví dụ |
|-----|-------|-------|
| **API Layer** | Xử lý HTTP requests/responses, validation | `@app.get("/users")` |
| **Service Layer** | Business logic, rules, orchestration | `user_service.create_user()` |
| **Repository Layer** | Database CRUD operations | `user_repo.get_by_email()` |
| **Models** | SQLAlchemy ORM models (Entity) | `class User(Base)` |
| **Schemas** | Pydantic models (DTO) | `class UserCreate(BaseModel)` |

---

## 🚀 Cài đặt

### 1️⃣ Prerequisites (Yêu cầu hệ thống)

- **Python**: 3.10 hoặc cao hơn
- **PostgreSQL**: 14 hoặc cao hơn
- **pip**: Package installer
- **Git**: Version control

### 2️⃣ Clone repository

```powershell
git clone https://github.com/PBL6-FRID/back-end.git
cd back-end
```

### 3️⃣ Tạo môi trường ảo (Virtual Environment)

**Windows PowerShell:**
```powershell
# Tạo venv
python -m venv venv

# Kích hoạt
.\venv\Scripts\activate

# Verify
python --version
```

**Linux/MacOS:**
```bash
# Tạo venv
python3 -m venv venv

# Kích hoạt
source venv/bin/activate

# Verify
python --version
```

### 4️⃣ Cài đặt dependencies

```powershell
# Upgrade pip
python -m pip install --upgrade pip

# Cài đặt tất cả packages
pip install -r requirements.txt

# Verify installation
pip list
```

**Dependencies chính:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `sqlalchemy` - ORM
- `psycopg2-binary` - PostgreSQL driver
- `alembic` - Database migrations
- `pydantic` - Data validation
- `python-jose` - JWT handling
- `passlib` - Password hashing
- `pgvector` - Vector similarity search

---

## ⚙️ Cấu hình

### 1️⃣ Tạo file `.env`

```powershell
# Copy template
Copy-Item .env.example .env

# Mở file để edit
notepad .env
```

### 2️⃣ Cấu hình biến môi trường

**File `.env`:**
```env
# ==================== APPLICATION ====================
PROJECT_NAME=AI Attendance System
VERSION=1.0.0
API_V1_STR=/api/v1
DEBUG=True

# ==================== DATABASE ====================
# Format: postgresql://username:password@host:port/database_name
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/ai_attendance

# ==================== SECURITY ====================
SECRET_KEY=your-super-secret-key-here-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ==================== CORS ====================
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# ==================== FILE UPLOAD ====================
MAX_UPLOAD_SIZE_MB=10
UPLOAD_DIR=uploads

# ==================== AI MODEL ====================
FACE_DETECTION_CONFIDENCE=0.7
FACE_DETECTION_IOU=0.45
FACE_RECOGNITION_THRESHOLD=0.6
```

### 3️⃣ Tạo PostgreSQL Database

**Sử dụng pgAdmin hoặc psql:**
```sql
-- Tạo database
CREATE DATABASE ai_attendance;

-- Tạo user (optional)
CREATE USER attendance_admin WITH PASSWORD 'your_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE ai_attendance TO attendance_admin;

-- Enable pgvector extension (cho face embeddings)
\c ai_attendance
CREATE EXTENSION IF NOT EXISTS vector;
```

**Hoặc dùng psql command:**
```powershell
psql -U postgres
CREATE DATABASE ai_attendance;
\q
```

---

## 🏃 Chạy dự án

### 1️⃣ Chạy Database Migrations

```powershell
# Tạo migration đầu tiên (nếu chưa có)
alembic revision --autogenerate -m "Initial schema"

# Apply migrations vào database
alembic upgrade head

# Kiểm tra version hiện tại
alembic current

# Xem lịch sử migrations
alembic history
```

### 2️⃣ Chạy Development Server

**Cách 1: Dùng Uvicorn (Recommended)**
```powershell
# Chạy với auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Hoặc với log level
uvicorn app.main:app --reload --log-level debug
```

**Cách 2: Chạy file main.py**
```powershell
python app/main.py
```

**Cách 3: Dùng script**
```powershell
# Tạo file run.bat (Windows)
@echo off
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Chạy
.\run.bat
```

### 3️⃣ Verify Server đã chạy

Mở trình duyệt và truy cập:

- **Root**: http://localhost:8000/
- **Health Check**: http://localhost:8000/health
- **API Docs (Swagger)**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc

**Kết quả mong đợi:**
```json
{
  "message": "Welcome to AI-Powered Attendance System API",
  "version": "1.0.0",
  "docs": "/api/v1/docs"
}
```

---

## 📚 API Documentation

### Interactive API Docs

Sau khi chạy server, truy cập:

🔗 **Swagger UI**: http://localhost:8000/api/v1/docs

- Giao diện tương tác để test API
- Tự động generate từ code
- Hỗ trợ authentication

🔗 **ReDoc**: http://localhost:8000/api/v1/redoc

- Documentation đẹp hơn Swagger
- Dễ đọc, dễ tìm kiếm

### API Endpoints Overview

| Endpoint | Method | Mô tả | Auth Required |
|----------|--------|-------|---------------|
| `/` | GET | Root endpoint | ❌ |
| `/health` | GET | Health check | ❌ |
| `/api/v1/auth/register` | POST | Đăng ký user mới | ❌ |
| `/api/v1/auth/login` | POST | Login & get JWT | ❌ |
| `/api/v1/auth/refresh` | POST | Refresh access token | ✅ |
| `/api/v1/users/me` | GET | Get current user info | ✅ |
| `/api/v1/classes` | GET | Danh sách lớp học | ✅ |
| `/api/v1/classes` | POST | Tạo lớp mới | ✅ (Teacher) |
| `/api/v1/attendance/sessions` | POST | Tạo buổi điểm danh | ✅ (Teacher) |
| `/api/v1/attendance/mark` | POST | Điểm danh AI | ✅ (Student) |

---

## 🗃️ Database Migration

### Alembic Workflow

**1. Tạo migration mới (sau khi thay đổi models):**
```powershell
# Auto-generate migration từ models
alembic revision --autogenerate -m "Add user roles table"

# Hoặc tạo empty migration (custom)
alembic revision -m "Add custom index"
```

**2. Review migration file:**
```powershell
# File được tạo trong alembic/versions/
# Ví dụ: 2024_10_07_1234_add_user_roles_table.py

# Kiểm tra nội dung
code alembic/versions/2024_10_07_1234_add_user_roles_table.py
```

**3. Apply migration:**
```powershell
# Upgrade lên version mới nhất
alembic upgrade head

# Upgrade tới version cụ thể
alembic upgrade abc123

# Upgrade lên +1 version
alembic upgrade +1
```

**4. Rollback migration:**
```powershell
# Downgrade về version trước
alembic downgrade -1

# Downgrade về version cụ thể
alembic downgrade abc123

# Downgrade về base (xóa tất cả)
alembic downgrade base
```

**5. Xem thông tin migrations:**
```powershell
# Current version
alembic current

# Lịch sử migrations
alembic history

# Lịch sử chi tiết
alembic history --verbose
```

---

## 💻 Development Workflow

### Thêm tính năng mới (Ví dụ: User Management)

**Bước 1: Tạo Model (Entity)**
```python
# app/models/user.py
from sqlalchemy import Column, String, Boolean
from app.models.base import BaseModel
from app.core.enums import UserRole

class User(BaseModel):
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False)
```

**Bước 2: Tạo Schema (DTO)**
```python
# app/schemas/user.py
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    is_verified: bool
```

**Bước 3: Tạo Repository (Data Access)**
```python
# app/repositories/user_repository.py
from app.repositories.base import BaseRepository
from app.models.user import User

class UserRepository(BaseRepository[User]):
    def __init__(self, db):
        super().__init__(User, db)
    
    def get_by_email(self, email: str):
        return self.db.query(User).filter(User.email == email).first()
```

**Bước 4: Tạo Service (Business Logic)**
```python
# app/services/user_service.py
from app.services.base import BaseService
from app.repositories.user_repository import UserRepository
from app.core.security import get_password_hash

class UserService(BaseService):
    def __init__(self, db):
        self.repo = UserRepository(db)
    
    def create_user(self, user_data):
        user_data['password_hash'] = get_password_hash(user_data.pop('password'))
        return self.repo.create(user_data)
```

**Bước 5: Tạo API Endpoint (Controller)**
```python
# app/api/v1/users.py
from fastapi import APIRouter, Depends
from app.services.user_service import UserService
from app.schemas.user import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=UserResponse)
def create_user(data: UserCreate, db = Depends(get_db)):
    service = UserService(db)
    return service.create_user(data.dict())
```

**Bước 6: Include Router**
```python
# app/api/v1/router.py
from app.api.v1 import users

api_router.include_router(users.router)
```

**Bước 7: Create & Run Migration**
```powershell
alembic revision --autogenerate -m "Add users table"
alembic upgrade head
```

### Code Style Guidelines

- **PEP 8**: Follow Python style guide
- **Type Hints**: Sử dụng type hints cho tất cả functions
- **Docstrings**: Viết docstring cho classes và functions
- **Naming Conventions**:
  - Classes: `PascalCase`
  - Functions/Variables: `snake_case`
  - Constants: `UPPER_CASE`
- **Import Order**: stdlib → third-party → local

---

## 🧪 Testing

### Chạy Tests

```powershell
# Cài pytest (nếu chưa có)
pip install pytest pytest-asyncio

# Chạy tất cả tests
pytest

# Chạy với coverage
pytest --cov=app tests/

# Chạy specific test file
pytest tests/test_auth.py

# Chạy với verbose output
pytest -v
```

### Viết Test

```python
# tests/test_users.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_user():
    response = client.post("/api/v1/users/", json={
        "email": "test@example.com",
        "password": "Test123!"
    })
    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
```

---

## 📦 Các lệnh hay dùng

### Pip Commands

```powershell
# Cài package mới
pip install package_name

# Ghi lại dependencies
pip freeze > requirements.txt

# Cài từ requirements.txt
pip install -r requirements.txt

# Upgrade package
pip install --upgrade package_name

# Uninstall package
pip uninstall package_name
```

### Git Commands

```powershell
# Check status
git status

# Add changes
git add .

# Commit
git commit -m "feat: add user management API"

# Push
git push origin main

# Pull latest
git pull origin main
```

### Database Commands

```powershell
# Alembic migration
alembic upgrade head

# Alembic rollback
alembic downgrade -1

# Alembic history
alembic history
```

---

## 🔧 Troubleshooting

### Lỗi thường gặp

**1. Import Error:**
```
ModuleNotFoundError: No module named 'app'
```
**Fix:**
```powershell
# Chạy từ root directory (back-end/)
cd back-end
uvicorn app.main:app --reload
```

**2. Database Connection Error:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```
**Fix:**
- Kiểm tra PostgreSQL đã chạy chưa
- Verify DATABASE_URL trong .env
- Test connection: `psql -U postgres`

**3. Alembic Error:**
```
Can't locate revision identified by 'abc123'
```
**Fix:**
```powershell
# Reset alembic
alembic downgrade base
alembic upgrade head
```

**4. Port already in use:**
```
ERROR: [Errno 10048] error while attempting to bind on address
```
**Fix:**
```powershell
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Hoặc đổi port
uvicorn app.main:app --reload --port 8001
```

---

## 👥 Team & Contributors

- **PBL6 Team** - Đại học Bách Khoa

---

## 📄 License

Private project - All rights reserved

---

## 📞 Contact & Support

Nếu có vấn đề, tạo issue trên GitHub hoặc liên hệ team qua:
- GitHub Issues: https://github.com/PBL6-FRID/back-end/issues

---

**Happy Coding! 🚀**