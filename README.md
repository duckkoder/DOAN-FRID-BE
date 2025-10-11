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

## 🔄 Hướng dẫn chi tiết Database Migration với Alembic

### 📋 Workflow hoàn chỉnh

#### **Bước 1: Khởi tạo Alembic (Chỉ làm 1 lần đầu tiên)**

```powershell
# Khởi tạo Alembic trong project
alembic init alembic
```

**Kết quả:**
```
Creating directory D:\PBL6\PBL6BE\back-end\alembic ...  done
Creating directory D:\PBL6\PBL6BE\back-end\alembic\versions ...  done
Generating D:\PBL6\PBL6BE\back-end\alembic.ini ...  done
Generating D:\PBL6\PBL6BE\back-end\alembic\env.py ...  done
Generating D:\PBL6\PBL6BE\back-end\alembic\script.py.mako ...  done
```

---

#### **Bước 2: Tạo Migration mới**

**Sau khi tạo hoặc sửa Model trong `app/models/`:**

```powershell
# Auto-generate migration từ SQLAlchemy models
alembic revision --autogenerate -m "Create users table"

# Hoặc tạo migration thủ công (empty)
alembic revision -m "Add custom constraints"
```

**Output thành công:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.autogenerate.compare] Detected added table 'users'
INFO  [alembic.autogenerate.compare] Detected added index 'ix_users_email' on '['email']'
  Generating D:\PBL6\PBL6BE\back-end\alembic\versions\2024_10_11_1234_create_users_table.py ...  done
```

---

#### **Bước 3: Kiểm tra Migration File**

```powershell
# Xem file migration vừa tạo
code alembic\versions\2024_10_11_1234_create_users_table.py

# Hoặc dùng editor khác
notepad alembic\versions\2024_10_11_1234_create_users_table.py
```

**Review nội dung migration:**
- Kiểm tra các thay đổi có đúng không
- Verify SQL sẽ được generate
- Sửa thủ công nếu cần (data migration, custom SQL)

---

#### **Bước 4: Apply Migration vào Database**

```powershell
# Upgrade lên version mới nhất
alembic upgrade head

# Upgrade từng bước (1 version)
alembic upgrade +1

# Upgrade đến revision cụ thể
alembic upgrade abc123def456
```

**Output thành công:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> abc123, Create users table
```

---

#### **Bước 5: Verify Migration**

```powershell
# Xem version hiện tại
alembic current

# Xem lịch sử migrations
alembic history

# Xem chi tiết
alembic history --verbose
```

**Kiểm tra trong database:**
```powershell
# Kết nối PostgreSQL
psql -U postgres -d ai_attendance

# Xem danh sách bảng
\dt

# Xem cấu trúc bảng
\d users

# Xem alembic version
SELECT * FROM alembic_version;

# Thoát
\q
```

---

### 🔄 Các lệnh Migration thường dùng

#### **Xem thông tin Migrations**

```powershell
# Hiển thị revision hiện tại
alembic current

# Liệt kê tất cả migrations
alembic history

# Hiển thị chi tiết với date & message
alembic history --verbose

# Hiển thị migrations trong range
alembic history -r base:head

# Show SQL sẽ chạy (không execute)
alembic upgrade head --sql
```

#### **Upgrade Migrations**

```powershell
# Upgrade lên version mới nhất
alembic upgrade head

# Upgrade lên +1 version
alembic upgrade +1

# Upgrade lên +2 versions
alembic upgrade +2

# Upgrade đến revision cụ thể
alembic upgrade abc123def456

# Upgrade từ revision A đến B
alembic upgrade abc123:def456
```

#### **Downgrade (Rollback) Migrations**

```powershell
# Downgrade về version trước đó
alembic downgrade -1

# Downgrade về -2 versions
alembic downgrade -2

# Downgrade về revision cụ thể
alembic downgrade abc123def456

# Downgrade về base (xóa tất cả)
alembic downgrade base

# Show SQL sẽ chạy khi downgrade
alembic downgrade -1 --sql
```

#### **Tạo Migrations**

```powershell
# Auto-generate từ models
alembic revision --autogenerate -m "Description"

# Tạo empty migration (manual)
alembic revision -m "Description"

# Tạo migration với revision ID custom
alembic revision --rev-id abc123 -m "Description"
```

#### **Stamp & Reset**

```powershell
# Đánh dấu database ở revision cụ thể (không chạy SQL)
alembic stamp head
alembic stamp abc123def456

# Stamp về base
alembic stamp base
```

---

### ⚠️ Xử lý lỗi Migration

#### **Lỗi 1: `Can't locate revision identified by 'abc123'`**

**Nguyên nhân:** Database có revision không tồn tại trong `alembic/versions/`

**Cách fix:**

```powershell
# Option 1: Reset alembic_version table
psql -U postgres -d ai_attendance -c "DELETE FROM alembic_version;"

# Option 2: Stamp về revision hiện có
alembic stamp head

# Option 3: Reset hoàn toàn (XÓA DATA)
psql -U postgres -d ai_attendance
```
```sql
-- Trong psql:
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;
\q
```
```powershell
# Sau đó xóa migrations cũ và tạo lại
Remove-Item -Recurse -Force alembic\versions\*
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

---

#### **Lỗi 2: `Target database is not up to date`**

**Nguyên nhân:** Database đang ở version cũ hơn so với code

**Cách fix:**

```powershell
# Xem version hiện tại
alembic current

# Xem các migrations pending
alembic history

# Upgrade lên latest
alembic upgrade head
```

---

#### **Lỗi 3: `FAILED: Multiple head revisions are present`**

**Nguyên nhân:** Có nhiều migrations cùng là "head" (branching)

**Cách fix:**

```powershell
# Xem các heads
alembic heads

# Merge các heads
alembic merge -m "Merge heads" head1_id head2_id

# Apply merge
alembic upgrade head
```

---

#### **Lỗi 4: `Table 'xxx' already exists`**

**Nguyên nhân:** Migration cố tạo bảng đã tồn tại

**Cách fix:**

```powershell
# Option 1: Stamp database về revision hiện tại
alembic stamp head

# Option 2: Edit migration file để skip CREATE TABLE
code alembic\versions\abc123_migration.py
```

Trong migration file, thêm check:
```python
def upgrade():
    # Kiểm tra table có tồn tại không
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if 'users' not in inspector.get_table_names():
        op.create_table('users', ...)
```

---

#### **Lỗi 5: `Database connection error`**

**Nguyên nhân:** Không kết nối được PostgreSQL

**Cách fix:**

```powershell
# Kiểm tra PostgreSQL đang chạy
Get-Service -Name postgresql*

# Kiểm tra DATABASE_URL trong .env
cat .env | Select-String "DATABASE_URL"

# Test connection
psql -U postgres -d ai_attendance

# Nếu password sai, reset trong pgAdmin hoặc:
psql -U postgres
ALTER USER postgres WITH PASSWORD 'new_password';
\q
```

Sau đó update `.env`:
```env
DATABASE_URL=postgresql://postgres:new_password@localhost:5432/ai_attendance
```

---

#### **Lỗi 6: `No changes in schema detected`**

**Nguyên nhân:** Alembic không detect thay đổi trong models

**Cách fix:**

```powershell
# 1. Xóa cache Python
Remove-Item -Recurse -Force app\__pycache__
Remove-Item -Recurse -Force app\models\__pycache__

# 2. Verify models được import trong alembic/env.py
code alembic\env.py
```

Đảm bảo trong `alembic/env.py`:
```python
from app.models.base import Base
from app.models.user import User  # Import TẤT CẢ models
from app.models.class_model import Class
# ...

target_metadata = Base.metadata  # Phải set
```

```powershell
# 3. Tạo lại migration
alembic revision --autogenerate -m "Update schema"
```

---

#### **Lỗi 7: `sqlalchemy.exc.IntegrityError: duplicate key`**

**Nguyên nhân:** Violation unique constraint khi apply migration

**Cách fix:**

```powershell
# Option 1: Clean data trước
psql -U postgres -d ai_attendance
```
```sql
-- Xóa data duplicate
DELETE FROM users WHERE email = 'duplicate@example.com';
\q
```
```powershell
# Sau đó upgrade lại
alembic upgrade head
```

**Option 2: Edit migration để handle duplicates:**
```python
def upgrade():
    # Xóa duplicates trước khi add constraint
    op.execute("""
        DELETE FROM users a USING users b
        WHERE a.id < b.id AND a.email = b.email
    """)
    
    # Sau đó add unique constraint
    op.create_unique_constraint('uq_users_email', 'users', ['email'])
```

---

### 🔄 Workflow Reset Migration hoàn toàn

Khi cần reset database và migrations từ đầu:

```powershell
# Bước 1: Backup database (quan trọng!)
pg_dump -U postgres ai_attendance > backup_$(Get-Date -Format "yyyyMMdd_HHmmss").sql

# Bước 2: Drop và tạo lại database
psql -U postgres
```
```sql
DROP DATABASE ai_attendance;
CREATE DATABASE ai_attendance;
\c ai_attendance
CREATE EXTENSION IF NOT EXISTS vector;
\q
```
```powershell
# Bước 3: Xóa tất cả migrations
Remove-Item -Recurse -Force alembic\versions\*

# Bước 4: Clear cache
Remove-Item -Recurse -Force app\__pycache__
Remove-Item -Recurse -Force app\models\__pycache__
Remove-Item -Recurse -Force app\core\__pycache__

# Bước 5: Tạo migration mới
alembic revision --autogenerate -m "Initial database schema"

# Bước 6: Apply migration
alembic upgrade head

# Bước 7: Verify
alembic current
psql -U postgres -d ai_attendance -c "\dt"
```

---

### 📊 Best Practices

#### **✅ Nên làm:**

1. **Luôn review migration file** trước khi apply
2. **Backup database** trước khi upgrade production
3. **Test migration** trên môi trường dev trước
4. **Viết descriptive messages** cho migrations
5. **Commit migration files** vào Git
6. **Downgrade test** để verify rollback hoạt động

#### **❌ Không nên:**

1. **Không edit migration đã apply** (tạo mới thay vì sửa)
2. **Không xóa migration files** đã apply
3. **Không skip revisions** khi deploy
4. **Không commit `.env`** lên Git
5. **Không apply trực tiếp lên production** chưa test

---

### 🔍 Debug Commands

```powershell
# Xem SQL sẽ chạy mà không execute
alembic upgrade head --sql > migration.sql
alembic downgrade -1 --sql > rollback.sql

# Check connection đến database
python -c "from app.core.config import settings; print(settings.DATABASE_URL)"

# Test import models
python -c "from app.models.user import User; print(User.__table__)"

# Verify alembic config
alembic --help
alembic current -v
```

---

### 📝 Migration File Structure

Migration file mẫu (`alembic/versions/abc123_create_users.py`):

```python
"""Create users table

Revision ID: abc123def456
Revises: previous_revision
Create Date: 2024-10-11 12:34:56.789012
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'abc123def456'
down_revision = 'previous_revision'  # None nếu là migration đầu
branch_labels = None
depends_on = None


def upgrade():
    """Apply changes to database."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_email', 'users', ['email'])


def downgrade():
    """Revert changes from database."""
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
```

---

### 🎯 Quick Reference

| Lệnh | Mô tả |
|------|-------|
| `alembic init alembic` | Khởi tạo Alembic (1 lần) |
| `alembic revision --autogenerate -m "msg"` | Tạo migration tự động |
| `alembic upgrade head` | Apply tất cả migrations |
| `alembic downgrade -1` | Rollback 1 migration |
| `alembic current` | Xem version hiện tại |
| `alembic history` | Xem lịch sử migrations |
| `alembic stamp head` | Đánh dấu database ở version mới nhất |
| `alembic upgrade head --sql` | Xem SQL sẽ chạy |

---

**Happy Migrating! 🚀**