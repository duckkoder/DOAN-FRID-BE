# 📤 File Upload APIs - Testing Guide

## 🎯 Mục đích

Hướng dẫn chi tiết cách test các API upload file lên AWS S3 sử dụng Thunder Client/Postman.

---

## 📋 Danh sách APIs cần test

1. ✅ Upload Avatar (Public)
2. ✅ Upload Document (Private) 
3. ✅ Upload Face Image (Private)
4. ✅ Get Download URL
5. ✅ Delete File
6. ✅ Get My Files

---

## 🔐 Bước 1: Đăng nhập để lấy Access Token

### Request
```
POST http://localhost:8000/api/v1/auth/login
Content-Type: application/json

{
  "email": "student1@example.com",
  "password": "password123"
}
```

### Response
```json
{
  "user": { ... },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "...",
  "token_type": "bearer"
}
```

**👉 Copy `access_token` để dùng cho các requests tiếp theo**

---

## 📤 Bước 2: Test Upload Avatar (Public)

### Thunder Client / Postman Setup

**Method**: `POST`  
**URL**: `http://localhost:8000/api/v1/files/upload/avatar`

**Headers**:
```
Authorization: Bearer {your_access_token}
```

**Body** (chọn form-data):
- Key: `file` (chọn type: File)
- Value: Chọn 1 file ảnh từ máy (jpg, png, gif, webp)

### Expected Response (200 OK)
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

### ✅ Kiểm tra kết quả

1. Copy URL từ response
2. Mở URL trong browser → File phải hiển thị được (public access)
3. Kiểm tra trong AWS S3 Console → File phải có trong bucket tại folder `public/avatars/`

### ❌ Error Cases

**File quá lớn (>10MB)**
```json
{
  "detail": "File exceeds 10MB limit"
}
```

**Extension không hợp lệ** (ví dụ: .exe, .zip)
```json
{
  "detail": "Extension .exe not allowed"
}
```

---

## 📄 Bước 3: Test Upload Document (Private)

### Thunder Client / Postman Setup

**Method**: `POST`  
**URL**: `http://localhost:8000/api/v1/files/upload/document`

**Headers**:
```
Authorization: Bearer {your_access_token}
```

**Body** (chọn form-data):
- Key: `file` (chọn type: File)
- Value: Chọn 1 file document (pdf, doc, docx, txt, xlsx)

### Expected Response (200 OK)
```json
{
  "success": true,
  "data": {
    "file_id": 2,
    "file_key": "private/documents/20251014_143052_b2c3d4e5-f6g7-8901-bcde-fg2345678901.pdf",
    "url": "https://pbl6-bucket.s3.ap-southeast-1.amazonaws.com/private/documents/...?AWSAccessKeyId=...&Signature=...&Expires=...",
    "original_name": "evidence-document.pdf",
    "size": 512345,
    "note": "URL expires in 1 hour"
  },
  "message": "Document uploaded successfully"
}
```

### ✅ Kiểm tra kết quả

1. Copy presigned URL từ response
2. Mở URL trong browser → File phải download được (trong vòng 1 giờ)
3. Sau 1 giờ, URL sẽ hết hạn → Cần request lại URL mới

---

## 🤳 Bước 4: Test Upload Face Image (Private)

### Thunder Client / Postman Setup

**Method**: `POST`  
**URL**: `http://localhost:8000/api/v1/files/upload/face`

**Headers**:
```
Authorization: Bearer {your_access_token}
```

**Body** (chọn form-data):
- Key: `file` (chọn type: File)
- Value: Chọn 1 ảnh khuôn mặt (jpg, jpeg, png)

### Expected Response (200 OK)
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

**👉 Lưu `file_id` để test các endpoints tiếp theo**

---

## 📥 Bước 5: Test Get Download URL

### Thunder Client / Postman Setup

**Method**: `GET`  
**URL**: `http://localhost:8000/api/v1/files/download/{file_id}`

**Ví dụ**: `http://localhost:8000/api/v1/files/download/2`

**Headers**:
```
Authorization: Bearer {your_access_token}
```

### Expected Response (200 OK)

**Public File (avatar)**:
```json
{
  "success": true,
  "data": {
    "file_id": 1,
    "url": "https://pbl6-bucket.s3.ap-southeast-1.amazonaws.com/public/avatars/20251014_143052_uuid.jpg"
  }
}
```

**Private File (document/face)**:
```json
{
  "success": true,
  "data": {
    "file_id": 2,
    "url": "https://pbl6-bucket.s3.ap-southeast-1.amazonaws.com/private/documents/20251014_143052_uuid.pdf?AWSAccessKeyId=...&Signature=...&Expires=..."
  }
}
```

### ✅ Kiểm tra kết quả

- Public files: URL không có query parameters
- Private files: URL có query parameters (AWSAccessKeyId, Signature, Expires)

---

## 📋 Bước 6: Test Get My Files

### Thunder Client / Postman Setup

**Method**: `GET`  
**URL**: `http://localhost:8000/api/v1/files/my-files`

**Headers**:
```
Authorization: Bearer {your_access_token}
```

### Expected Response (200 OK)
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

### ✅ Kiểm tra kết quả

- Chỉ hiển thị files do user hiện tại upload
- Mỗi file có đầy đủ thông tin: id, filename, category, size, is_public

---

## 🗑️ Bước 7: Test Delete File

### Thunder Client / Postman Setup

**Method**: `DELETE`  
**URL**: `http://localhost:8000/api/v1/files/{file_id}`

**Ví dụ**: `http://localhost:8000/api/v1/files/1`

**Headers**:
```
Authorization: Bearer {your_access_token}
```

### Expected Response (200 OK)
```json
{
  "success": true,
  "message": "File deleted successfully"
}
```

### ✅ Kiểm tra kết quả

1. File bị xóa khỏi database
2. File bị xóa khỏi AWS S3
3. URL cũ không truy cập được nữa
4. Gọi lại `GET /files/my-files` → File không còn trong danh sách

### ❌ Error Cases

**File not found**:
```json
{
  "detail": "File not found"
}
```

**No permission** (user khác upload):
```json
{
  "detail": "No permission to delete this file"
}
```

---

## 🧪 Test Scenarios đầy đủ

### Scenario 1: Upload và Download Avatar
1. ✅ Login → Lấy access token
2. ✅ Upload avatar → Lưu file_id
3. ✅ Get download URL → Verify public URL
4. ✅ Open URL in browser → Image hiển thị
5. ✅ Get my files → Avatar có trong list

### Scenario 2: Upload Document riêng tư
1. ✅ Login → Lấy access token
2. ✅ Upload document → Lưu file_id
3. ✅ Get download URL → Verify presigned URL
4. ✅ Download file → Success trong 1h
5. ✅ Wait >1h → URL expired
6. ✅ Get new URL → Download lại OK

### Scenario 3: Permission Check
1. ✅ User A upload file → Lưu file_id
2. ✅ User B login → Lấy token của B
3. ❌ User B delete file của A → 403 Forbidden
4. ✅ User A delete file → Success

### Scenario 4: File Validation
1. ❌ Upload file >10MB → 413 Request Entity Too Large
2. ❌ Upload .exe file → 400 Bad Request
3. ❌ Upload image to /upload/document endpoint → Still works (no restriction)
4. ✅ Upload valid image → Success

### Scenario 5: Complete Flow
1. ✅ Register new student
2. ✅ Login → Get token
3. ✅ Upload avatar → Update profile picture
4. ✅ Upload face images (3 photos) → For face recognition
5. ✅ Upload leave request document → Attach to leave request
6. ✅ Get all my files → Verify 5 files uploaded
7. ✅ Delete avatar → Upload new one
8. ✅ Get all my files → Verify only 4 files remain

---

## 🔍 Debugging Tips

### 1. Kiểm tra AWS Credentials
```python
# Trong terminal
python -c "import boto3; print(boto3.client('s3').list_buckets())"
```

### 2. Kiểm tra S3 Bucket Permissions
- Public files: Bucket policy phải allow public read
- Private files: Bucket phải allow presigned URLs

### 3. Kiểm tra File Size
```bash
# Windows PowerShell
(Get-Item "path\to\file.jpg").Length / 1MB
```

### 4. Kiểm tra Database
```sql
SELECT * FROM files WHERE uploader_id = 1;
```

### 5. Common Issues

**Issue**: Upload thành công nhưng không thấy file trong S3
- **Solution**: Kiểm tra bucket name trong .env

**Issue**: Presigned URL không download được
- **Solution**: Kiểm tra bucket CORS configuration

**Issue**: Public URL 403 Forbidden
- **Solution**: Kiểm tra bucket policy cho phép public read

**Issue**: File upload rất chậm
- **Solution**: Kiểm tra AWS region (nên chọn region gần nhất)

---

## 📊 Expected Results Summary

| API | Status Code | Public/Private | URL Type |
|-----|-------------|----------------|----------|
| Upload Avatar | 200 | Public | Direct URL |
| Upload Document | 200 | Private | Presigned URL (1h) |
| Upload Face | 200 | Private | No URL returned |
| Get Download URL | 200 | Both | Direct/Presigned |
| Delete File | 200 | Both | N/A |
| Get My Files | 200 | Both | N/A |

---

## 🎓 Best Practices

1. **Always validate file size** trước khi upload
2. **Use presigned URLs** cho private files
3. **Delete old files** khi upload new avatar
4. **Store file_id** trong database (không store URL)
5. **Generate URL on-demand** khi cần hiển thị file
6. **Set appropriate expiration** cho presigned URLs (default 1h)
7. **Use UUID filenames** để avoid conflicts
8. **Add metadata** để track original filename

---

**Version**: 1.0.0  
**Last Updated**: October 14, 2025  
**Author**: PBL6 Team
