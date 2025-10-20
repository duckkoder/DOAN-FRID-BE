# 🎯 API Đã Triển Khai - PBL6 Backend

> **Ghi chú:** Document này chỉ liệt kê các API đã được triển khai thực tế trong code.

**Base URL**: `http://localhost:8000/api/v1`

---

## 📊 Tổng quan

### ✅ Đã triển khai
- **Authentication APIs**: Login, Register, Refresh Token, Logout
- **Admin - Teachers Management**: CRUD operations
- **Admin - Students Management**: CRUD operations
- **File Upload APIs**: Upload avatar, document, face image to AWS S3

### ⏳ Chưa triển khai
- Teacher Dashboard & Classes Management
- Student Dashboard & Attendance
- Face Recognition APIs
- Leave Requests Management

---

## 🔑 Authentication APIs

### 1. Register User
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "full_name": "Nguyen Van A",
  "password": "password123",
  "phone": "0123456789",
  "role": "teacher|student",
  
  // For Teacher
  "teacher_code": "GV001",
  "department": "Computer Science",
  "specialization": "AI & Machine Learning",
  
  // For Student
  "student_code": "SV001",
  "major": "Information Technology",
  "academic_year": "2021",
  "date_of_birth": "2003-05-15"
}
```

**Response:**
```json
{
  "user": {
    "id": 1,
    "full_name": "Nguyen Van A",
    "email": "user@example.com",
    "role": "teacher|student",
    "is_active": true,
    "avatar_url": null,
    "phone": "0123456789",
    "is_verified": false,
    "created_at": "2025-10-13T13:49:53.772800",
    "teacher_code": "GV001",
    "department": "Computer Science"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 2. Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "user": {
    "id": 1,
    "full_name": "Nguyen Van A",
    "email": "user@example.com",
    "role": "teacher",
    "is_active": true,
    "is_verified": false,
    "created_at": "2025-10-13T13:49:53.772800"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 3. Refresh Token
```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 4. Logout
```http
POST /api/v1/auth/logout
Authorization: Bearer {accessToken}
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

---

## 👨‍💼 Admin APIs - Teachers Management

> **Yêu cầu:** Admin role only

### 1. Get Teachers List
```http
GET /api/v1/admin/teachers?search=nguyen&department=Computer%20Science&is_active=true&page=1&limit=10
Authorization: Bearer {accessToken}
```

**Query Parameters:**
- `search` (optional): Search by name, email, or teacher code
- `department` (optional): Filter by department
- `is_active` (optional): Filter by active status (true/false)
- `page` (optional): Page number, default 1
- `limit` (optional): Items per page, default 10, max 100

**Response:**
```json
{
  "total": 15,
  "page": 1,
  "page_size": 10,
  "total_pages": 2,
  "data": [
    {
      "id": 1,
      "user_id": 3,
      "teacher_code": "GV001",
      "department": "Computer Science",
      "specialization": "Artificial Intelligence",
      "created_at": "2025-10-13T13:49:53.772800",
      "updated_at": "2025-10-13T13:49:53.772800",
      "full_name": "Dr. Nguyen Van A",
      "email": "teacher1@example.com",
      "phone": "0123456789",
      "avatar_url": null,
      "is_active": true
    }
  ],
  "stats": {
    "total": 15,
    "active": 12,
    "inactive": 3
  }
}
```

### 2. Get Teacher by ID
```http
GET /api/v1/admin/teachers/1
Authorization: Bearer {accessToken}
```

**Response:**
```json
{
  "teacher": {
    "id": 1,
    "user_id": 3,
    "teacher_code": "GV001",
    "department": "Computer Science",
    "specialization": "Artificial Intelligence",
    "created_at": "2025-10-13T13:49:53.772800",
    "updated_at": "2025-10-13T13:49:53.772800",
    "full_name": "Dr. Nguyen Van A",
    "email": "teacher1@example.com",
    "phone": "0123456789",
    "avatar_url": null,
    "is_active": true
  }
}
```

### 3. Update Teacher
```http
PUT /api/v1/admin/teachers/1
Authorization: Bearer {accessToken}
Content-Type: application/json

{
  "department": "Software Engineering",
  "specialization": "Machine Learning",
  "phone": "0987654321",
  "is_active": true
}
```

**Response:**
```json
{
  "message": "Teacher updated successfully",
  "teacher": {
    "id": 1,
    "user_id": 3,
    "teacher_code": "GV001",
    "department": "Software Engineering",
    "specialization": "Machine Learning",
    "created_at": "2025-10-13T13:49:53.772800",
    "updated_at": "2025-10-13T15:30:00.000000",
    "full_name": "Dr. Nguyen Van A",
    "email": "teacher1@example.com",
    "phone": "0987654321",
    "avatar_url": null,
    "is_active": true
  }
}
```

### 4. Delete Teacher (Soft Delete)
```http
DELETE /api/v1/admin/teachers/1
Authorization: Bearer {accessToken}
```

**Response:**
```json
{
  "message": "Teacher deactivated successfully"
}
```

**Note:** Đây là soft delete - chỉ set `is_active = false`, không xóa dữ liệu khỏi database.

---

## 👨‍🎓 Admin APIs - Students Management

> **Yêu cầu:** Admin role only

### 1. Get Students List
```http
GET /api/v1/admin/students?search=nguyen&major=IT&academic_year=2021&is_active=true&is_verified=true&page=1&limit=10
Authorization: Bearer {accessToken}
```

**Query Parameters:**
- `search` (optional): Search by name, email, or student code
- `major` (optional): Filter by major
- `academic_year` (optional): Filter by academic year (e.g., "2021")
- `is_active` (optional): Filter by active status (true/false)
- `is_verified` (optional): Filter by verification status (true/false)
- `page` (optional): Page number, default 1
- `limit` (optional): Items per page, default 10, max 100

**Response:**
```json
{
  "total": 250,
  "page": 1,
  "page_size": 10,
  "total_pages": 25,
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "student_code": "SV001",
      "date_of_birth": "2003-05-15",
      "major": "Information Technology",
      "academic_year": "2021",
      "is_verified": true,
      "created_at": "2025-10-12T14:09:08.098512",
      "updated_at": "2025-10-12T14:09:08.098512",
      "full_name": "Nguyen Van A",
      "email": "student1@example.com",
      "phone": "0123456789",
      "avatar_url": null,
      "is_active": true
    }
  ],
  "stats": {
    "total": 250,
    "active": 240,
    "inactive": 10,
    "verified": 200,
    "unverified": 50
  }
}
```

### 2. Get Student by ID
```http
GET /api/v1/admin/students/1
Authorization: Bearer {accessToken}
```

**Response:**
```json
{
  "student": {
    "id": 1,
    "user_id": 1,
    "student_code": "SV001",
    "date_of_birth": "2003-05-15",
    "major": "Information Technology",
    "academic_year": "2021",
    "is_verified": true,
    "created_at": "2025-10-12T14:09:08.098512",
    "updated_at": "2025-10-12T14:09:08.098512",
    "full_name": "Nguyen Van A",
    "email": "student1@example.com",
    "phone": "0123456789",
    "avatar_url": null,
    "is_active": true
  }
}
```

### 3. Update Student
```http
PUT /api/v1/admin/students/1
Authorization: Bearer {accessToken}
Content-Type: application/json

{
  "major": "Computer Science",
  "academic_year": "2022",
  "date_of_birth": "2003-06-20",
  "phone": "0987654321",
  "is_active": true,
  "is_verified": true
}
```

**Response:**
```json
{
  "message": "Student updated successfully",
  "student": {
    "id": 1,
    "user_id": 1,
    "student_code": "SV001",
    "date_of_birth": "2003-06-20",
    "major": "Computer Science",
    "academic_year": "2022",
    "is_verified": true,
    "created_at": "2025-10-12T14:09:08.098512",
    "updated_at": "2025-10-13T15:30:00.000000",
    "full_name": "Nguyen Van A",
    "email": "student1@example.com",
    "phone": "0987654321",
    "avatar_url": null,
    "is_active": true
  }
}
```

### 4. Delete Student (Soft Delete)
```http
DELETE /api/v1/admin/students/1
Authorization: Bearer {accessToken}
```

**Response:**
```json
{
  "message": "Student deactivated successfully"
}
```

**Note:** Đây là soft delete - chỉ set `is_active = false`, không xóa dữ liệu khỏi database.

---

## � File Upload APIs - AWS S3

> **Yêu cầu:** Authenticated users only

### 1. Upload Avatar (Public)
```http
POST /api/v1/files/upload/avatar
Authorization: Bearer {accessToken}
Content-Type: multipart/form-data

file: [image file]
```

**Supported formats**: jpg, jpeg, png, gif, webp  
**Max size**: 10MB

**Response:**
```json
{
  "success": true,
  "data": {
    "file_id": 1,
    "file_key": "public/avatars/20251014_143052_a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg",
    "url": "https://pbl6-bucket.s3.ap-southeast-1.amazonaws.com/public/avatars/20251014_143052_a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg",
    "original_name": "my-avatar.jpg",
    "size": 245678
  },
  "message": "Avatar uploaded successfully"
}
```

**Note:** Public files có thể truy cập trực tiếp qua URL mà không cần authentication.

### 2. Upload Document (Private)
```http
POST /api/v1/files/upload/document
Authorization: Bearer {accessToken}
Content-Type: multipart/form-data

file: [document file]
```

**Supported formats**: pdf, doc, docx, txt, xlsx  
**Max size**: 10MB

**Response:**
```json
{
  "success": true,
  "data": {
    "file_id": 2,
    "file_key": "private/documents/20251014_143052_b2c3d4e5-f6g7-8901-bcde-fg2345678901.pdf",
    "url": "https://pbl6-bucket.s3.ap-southeast-1.amazonaws.com/private/documents/20251014_143052_b2c3d4e5-f6g7-8901-bcde-fg2345678901.pdf?AWSAccessKeyId=AKIAIOSFODNN7EXAMPLE&Signature=...",
    "original_name": "evidence-document.pdf",
    "size": 512345,
    "note": "URL expires in 1 hour"
  },
  "message": "Document uploaded successfully"
}
```

**Note:** Private files được trả về presigned URL có thời hạn 1 giờ.

### 3. Upload Face Image (Private)
```http
POST /api/v1/files/upload/face
Authorization: Bearer {accessToken}
Content-Type: multipart/form-data

file: [image file]
```

**Supported formats**: jpg, jpeg, png  
**Max size**: 10MB

**Response:**
```json
{
  "success": true,
  "data": {
    "file_id": 3,
    "file_key": "private/faces/20251014_143052_c3d4e5f6-g7h8-9012-cdef-gh3456789012.jpg",
    "original_name": "face-photo.jpg",
    "size": 187654
  },
  "message": "Face image uploaded successfully"
}
```

**Note:** Face images được lưu private để bảo mật thông tin sinh trắc học.

### 4. Get Download URL
```http
GET /api/v1/files/download/{file_id}
Authorization: Bearer {accessToken}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "file_id": 2,
    "url": "https://pbl6-bucket.s3.ap-southeast-1.amazonaws.com/private/documents/20251014_143052_b2c3d4e5-f6g7-8901-bcde-fg2345678901.pdf?AWSAccessKeyId=AKIAIOSFODNN7EXAMPLE&Signature=..."
  }
}
```

**Note:** 
- Public files: Trả về direct URL
- Private files: Trả về presigned URL (expires in 1 hour)

### 5. Delete File
```http
DELETE /api/v1/files/{file_id}
Authorization: Bearer {accessToken}
```

**Response:**
```json
{
  "success": true,
  "message": "File deleted successfully"
}
```

**Note:** Chỉ uploader mới có quyền xóa file của mình.

### 6. Get My Files
```http
GET /api/v1/files/my-files
Authorization: Bearer {accessToken}
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "file_id": 1,
      "filename": "20251014_143052_a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg",
      "original_name": "my-avatar.jpg",
      "category": "avatar",
      "size": 245678,
      "is_public": true,
      "created_at": "2025-10-14T14:30:52.123456"
    },
    {
      "file_id": 2,
      "filename": "20251014_143052_b2c3d4e5-f6g7-8901-bcde-fg2345678901.pdf",
      "original_name": "evidence-document.pdf",
      "category": "document",
      "size": 512345,
      "is_public": false,
      "created_at": "2025-10-14T14:32:15.654321"
    }
  ],
  "total": 2
}
```

### File Storage Structure in S3

```
pbl6-bucket/
├── public/
│   └── avatars/
│       └── 20251014_143052_uuid.jpg
└── private/
    ├── documents/
    │   └── 20251014_143052_uuid.pdf
    └── faces/
        └── 20251014_143052_uuid.jpg
```

### File Categories

| Category | Folder | Access | Use Case |
|----------|--------|--------|----------|
| `avatar` | `public/avatars` | Public | User profile pictures |
| `document` | `private/documents` | Private | Leave request attachments |
| `face_image` | `private/faces` | Private | Face recognition training |

### File Validation

**Image files:**
- **Extensions**: jpg, jpeg, png, gif, webp
- **Max size**: 10MB
- **Use for**: avatars, face images

**Document files:**
- **Extensions**: pdf, doc, docx, txt, xlsx
- **Max size**: 10MB
- **Use for**: leave request evidences

### Error Responses

**413 File Too Large**
```json
{
  "detail": "File exceeds 10MB limit"
}
```

**400 Invalid Extension**
```json
{
  "detail": "Extension .exe not allowed"
}
```

**404 File Not Found**
```json
{
  "detail": "File not found"
}
```

**403 Permission Denied**
```json
{
  "detail": "No permission to delete this file"
}
```

**500 AWS Service Error**
```json
{
  "detail": "Upload failed: Access Denied"
}
```

### Configuration

Để sử dụng AWS S3, cần cấu hình các biến môi trường trong file `.env`:

```env
# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=ap-southeast-1
AWS_S3_BUCKET_NAME=pbl6-bucket

# S3 Public URL
S3_BASE_URL=https://pbl6-bucket.s3.ap-southeast-1.amazonaws.com

# File Upload Settings
MAX_FILE_SIZE_MB=10
ALLOWED_IMAGE_EXTENSIONS=jpg,jpeg,png,gif,webp
ALLOWED_DOCUMENT_EXTENSIONS=pdf,doc,docx,txt,xlsx,jpg,jpeg,png,gif,webp
```

### Security Features

1. **File Validation**: Kiểm tra extension và size trước khi upload
2. **UUID Naming**: File được rename với UUID để tránh conflict và bảo mật
3. **Public/Private Separation**: Phân tách rõ ràng giữa public và private files
4. **Presigned URLs**: Private files dùng presigned URL có thời hạn (1 hour)
5. **Permission Check**: Chỉ uploader được phép xóa file của mình
6. **Metadata**: Lưu original filename và upload time trong S3 metadata

---

## �🚨 Error Responses

### 401 Unauthorized
```json
{
  "detail": "Invalid or expired token"
}
```

### 403 Forbidden
```json
{
  "detail": "Access denied. Admin role required."
}
```

### 404 Not Found
```json
{
  "detail": "Teacher not found"
}
```
hoặc
```json
{
  "detail": "Student not found"
}
```

### 400 Bad Request
```json
{
  "detail": "Email already registered"
}
```
hoặc
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["query", "page"],
      "msg": "ensure this value is greater than or equal to 1",
      "type": "value_error.number.not_ge"
    }
  ]
}
```

---

## 📝 Notes

1. **Authentication**: Tất cả API (trừ register/login) đều yêu cầu Bearer Token trong header
2. **Date Format**: ISO 8601 format (`YYYY-MM-DDTHH:mm:ss.ffffffZ`)
3. **Pagination**: Default page=1, limit=10, max limit=100
4. **Soft Delete**: DELETE endpoints chỉ deactivate user, không xóa khỏi database
5. **Role-based Access**: Admin APIs chỉ cho phép role="admin"
6. **File Upload**: 
   - Max size: 10MB per file
   - Images: jpg, jpeg, png, gif, webp
   - Documents: pdf, doc, docx, txt, xlsx
   - Public files (avatars) accessible via direct URL
   - Private files (documents, faces) use presigned URLs (expires in 1 hour)
7. **AWS S3**: Files stored in AWS S3 bucket với cấu trúc `public/` và `private/` folders

---

**Version**: 1.1.0  
**Last Updated**: October 14, 2025  
**Base URL**: `http://localhost:8000/api/v1`
