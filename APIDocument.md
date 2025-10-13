# 🔌 PBL6 Smart Attendance System - API Documentation

## 📋 Mô tả tổng quan

Tài liệu này mô tả chi tiết tất cả các API endpoints của hệ thống PBL6 Smart Attendance System. Hệ thống hỗ trợ 3 vai trò chính: Admin, Teacher, và Student.

**Base URL**: `http://localhost:3001/api`

## 🔐 Authentication

Tất cả các API (trừ login/register) đều yêu cầu Bearer Token trong header:
```
Authorization: Bearer {accessToken}
```

---

## 🔑 AUTH APIs

### Login
```json
{
  "endpoint": "/auth/login",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "username": "string",
    "password": "string", 
    "isRemember": "boolean"
  },
  "response": {
    "success": true,
    "data": {
      "user": {
        "id": "number",
        "username": "string",
        "email": "string",
        "role": "admin|teacher|student",
        "avatar": "string",
        "fullName": "string",
        "isVerified": "boolean",
        "createdAt": "string",
        "updatedAt": "string"
      },
      "tokens": {
        "accessToken": "string",
        "refreshToken": "string",
        "expiresIn": "number"
      }
    },
    "message": "Login successful"
  },
  "errorResponse": {
    "success": false,
    "error": {
      "code": "INVALID_CREDENTIALS",
      "message": "Username or password is incorrect"
    }
  }
}
```

### Register
```json
{
  "endpoint": "/auth/register",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "username": "string",
    "password": "string",
    "email": "string",
    "fullName": "string",
    "role": "teacher|student"
  },
  "response": {
    "success": true,
    "data": {
      "user": {
        "id": "number",
        "username": "string",
        "email": "string",
        "role": "teacher|student",
        "fullName": "string",
        "isVerified": false
      }
    },
    "message": "Registration successful. Please verify your email."
  }
}
```

### Refresh Token
```json
{
  "endpoint": "/auth/refresh",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "refreshToken": "string"
  },
  "response": {
    "success": true,
    "data": {
      "accessToken": "string",
      "refreshToken": "string",
      "expiresIn": "number"
    }
  }
}
```

### Logout
```json
{
  "endpoint": "/auth/logout",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "refreshToken": "string"
  },
  "response": {
    "success": true,
    "message": "Logout successful"
  }
}
```

---

## 👨‍🎓 STUDENT APIs

### Get Dashboard Stats
```json
{
  "endpoint": "/student/dashboard/stats",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "response": {
    "success": true,
    "data": {
      "totalClasses": 4,
      "attendanceRate": 95.5,
      "totalAbsences": 3,
      "weeklyAttendance": [
        { "day": "Mon", "present": 4, "absent": 0 },
        { "day": "Tue", "present": 3, "absent": 1 },
        { "day": "Wed", "present": 4, "absent": 0 },
        { "day": "Thu", "present": 3, "absent": 1 },
        { "day": "Fri", "present": 4, "absent": 0 }
      ],
      "monthlyTrend": [
        { "month": "Jan", "rate": 95 },
        { "month": "Feb", "rate": 88 },
        { "month": "Mar", "rate": 92 },
        { "month": "Apr", "rate": 96 },
        { "month": "May", "rate": 89 },
        { "month": "Jun", "rate": 94 }
      ],
      "subjectAttendance": [
        { "subject": "Java", "rate": 95, "sessions": 20 },
        { "subject": "Database", "rate": 88, "sessions": 16 },
        { "subject": "Web Dev", "rate": 92, "sessions": 18 },
        { "subject": "AI/ML", "rate": 85, "sessions": 14 }
      ]
    }
  }
}
```

### Get Classes List
```json
{
  "endpoint": "/student/classes",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "queryParams": {
    "status": "active|upcoming|completed",
    "page": "number",
    "limit": "number"
  },
  "response": {
    "success": true,
    "data": {
      "classes": [
        {
          "id": "string",
          "name": "Advanced Java Programming",
          "subject": "Java Programming",
          "teacher": "Dr. Nguyen Van A",
          "teacherId": "string",
          "students": 25,
          "maxStudents": 30,
          "schedule": "Mon, Wed, Fri - 07:30-09:30",
          "room": "LAB-101",
          "isPinned": true,
          "status": "active|upcoming|completed",
          "classCode": "JAVA2024",
          "startDate": "2024-01-15",
          "endDate": "2024-05-15",
          "createdAt": "string",
          "updatedAt": "string"
        }
      ],
      "pagination": {
        "page": 1,
        "limit": 10,
        "total": 4,
        "totalPages": 1
      }
    }
  }
}
```

### Join Class
```json
{
  "endpoint": "/student/classes/join",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "classCode": "JAVA2024"
  },
  "response": {
    "success": true,
    "data": {
      "class": {
        "id": "string",
        "name": "Advanced Java Programming",
        "teacher": "Dr. Nguyen Van A",
        "classCode": "JAVA2024"
      }
    },
    "message": "Successfully joined the class"
  },
  "errorResponse": {
    "success": false,
    "error": {
      "code": "CLASS_NOT_FOUND",
      "message": "Class with this code does not exist"
    }
  }
}
```

### Get Class Details
```json
{
  "endpoint": "/student/classes/{classId}",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "response": {
    "success": true,
    "data": {
      "class": {
        "id": "string",
        "name": "Advanced Java Programming",
        "subject": "Java Programming",
        "teacher": "Dr. Nguyen Van A",
        "teacherId": "string",
        "students": 25,
        "maxStudents": 30,
        "schedule": {
          "monday": ["(7:30 - 9:30)", "Buổi 2 (9:45 - 11:45)"],
          "wednesday": ["Buổi 1 (7:30 - 9:30)", "Buổi 2 (9:45 - 11:45)"],
          "friday": ["Buổi 1 (7:30 - 9:30)", "Buổi 2 (9:45 - 11:45)"]
        },
        "room": "LAB-101",
        "status": "active",
        "classCode": "JAVA2024",
        "startDate": "2024-01-15",
        "endDate": "2024-05-15",
        "description": "Advanced Java Programming Course"
      },
      "attendanceStats": {
        "totalSessions": 20,
        "presentCount": 18,
        "absentCount": 2,
        "attendanceRate": 90
      }
    }
  }
}
```

### Pin/Unpin Class
```json
{
  "endpoint": "/student/classes/{classId}/pin",
  "method": "PUT",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "isPinned": true
  },
  "response": {
    "success": true,
    "message": "Class pinned successfully"
  }
}
```

### Get Attendance History
```json
{
  "endpoint": "/student/attendance/{classId}",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "queryParams": {
    "startDate": "2024-01-01",
    "endDate": "2024-12-31",
    "page": "number",
    "limit": "number"
  },
  "response": {
    "success": true,
    "data": {
      "attendance": [
        {
          "id": "string",
          "sessionId": "string",
          "sessionName": "Java Programming - Session 1",
          "date": "2024-10-15",
          "status": "present|absent|late",
          "checkInTime": "07:35:00",
          "checkOutTime": "09:25:00",
          "note": "string",
          "createdAt": "string"
        }
      ],
      "stats": {
        "totalSessions": 20,
        "presentCount": 18,
        "absentCount": 1,
        "lateCount": 1,
        "attendanceRate": 90
      },
      "pagination": {
        "page": 1,
        "limit": 10,
        "total": 20,
        "totalPages": 2
      }
    }
  }
}
```

### Get Attendance Stats
```json
{
  "endpoint": "/student/attendance/stats",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "queryParams": {
    "classId": "string",
    "period": "week|month|semester|year"
  },
  "response": {
    "success": true,
    "data": {
      "overall": {
        "totalSessions": 80,
        "presentCount": 72,
        "absentCount": 6,
        "lateCount": 2,
        "attendanceRate": 92.5
      },
      "bySubject": [
        {
          "classId": "string",
          "className": "Advanced Java Programming",
          "totalSessions": 20,
          "presentCount": 18,
          "absentCount": 1,
          "lateCount": 1,
          "attendanceRate": 90
        }
      ]
    }
  }
}
```

### Get Leave Requests
```json
{
  "endpoint": "/student/leave-requests",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "queryParams": {
    "status": "pending|approved|rejected",
    "page": "number",
    "limit": "number"
  },
  "response": {
    "success": true,
    "data": {
      "leaveRequests": [
        {
          "id": "string",
          "classId": "string",
          "className": "Advanced Java Programming",
          "subject": "Advanced Java Programming",
          "date": "2024-10-15",
          "dayOfWeek": "Thứ 3",
          "timeSlot": "Buổi 1 (7:30 - 9:30)",
          "reason": "Bị sốt cao, cần nghỉ ngơi và đi khám bác sĩ",
          "status": "pending|approved|rejected",
          "submittedDate": "2024-10-10",
          "approvedDate": "2024-10-11",
          "approverNote": "Đơn hợp lệ, chúc em sớm khỏe",
          "attachments": [
            {
              "id": "string",
              "filename": "medical_certificate.pdf",
              "url": "string",
              "size": 1024000
            }
          ],
          "createdAt": "string",
          "updatedAt": "string"
        }
      ],
      "stats": {
        "total": 5,
        "pending": 1,
        "approved": 3,
        "rejected": 1
      },
      "pagination": {
        "page": 1,
        "limit": 10,
        "total": 5,
        "totalPages": 1
      }
    }
  }
}
```

### Create Leave Request
```json
{
  "endpoint": "/student/leave-requests",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "classId": "string",
    "subject": "java",
    "dayOfWeek": "monday",
    "timeSlot": "Buổi 1 (7:30 - 9:30)",
    "date": "2024-10-15",
    "reason": "Bị sốt cao, cần nghỉ ngơi và đi khám bác sĩ",
    "attachments": ["attachment_id_1", "attachment_id_2"]
  },
  "response": {
    "success": true,
    "data": {
      "leaveRequest": {
        "id": "string",
        "classId": "string",
        "subject": "Advanced Java Programming",
        "date": "2024-10-15",
        "dayOfWeek": "Thứ 2",
        "timeSlot": "Buổi 1 (7:30 - 9:30)",
        "reason": "Bị sốt cao, cần nghỉ ngơi và đi khám bác sĩ",
        "status": "pending",
        "submittedDate": "2024-10-10"
      }
    },
    "message": "Leave request submitted successfully"
  }
}
```

### Update Leave Request
```json
{
  "endpoint": "/student/leave-requests/{requestId}",
  "method": "PUT",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "subject": "java",
    "dayOfWeek": "monday",
    "timeSlot": "Buổi 1 (7:30 - 9:30)",
    "date": "2024-10-15",
    "reason": "Updated reason",
    "attachments": ["attachment_id_1"]
  },
  "response": {
    "success": true,
    "data": {
      "leaveRequest": {
        "id": "string",
        "reason": "Updated reason",
        "updatedAt": "string"
      }
    },
    "message": "Leave request updated successfully"
  },
  "errorResponse": {
    "success": false,
    "error": {
      "code": "CANNOT_EDIT",
      "message": "Cannot edit leave request that is already processed"
    }
  }
}
```

### Delete Leave Request
```json
{
  "endpoint": "/student/leave-requests/{requestId}",
  "method": "DELETE",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "response": {
    "success": true,
    "message": "Leave request deleted successfully"
  },
  "errorResponse": {
    "success": false,
    "error": {
      "code": "CANNOT_DELETE",
      "message": "Cannot delete leave request that is already processed"
    }
  }
}
```

### Face Registration
```json
{
  "endpoint": "/student/face-register",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "multipart/form-data"
  },
  "body": {
    "images": ["File", "File", "File"],
    "userId": "string"
  },
  "response": {
    "success": true,
    "data": {
      "faceModel": {
        "id": "string",
        "userId": "string",
        "modelPath": "string",
        "accuracy": 95.5,
        "imagesCount": 10,
        "createdAt": "string"
      }
    },
    "message": "Face registration completed successfully"
  }
}
```

---

## 👨‍🏫 TEACHER APIs

### Get Dashboard Stats
```json
{
  "endpoint": "/teacher/dashboard/stats",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "response": {
    "success": true,
    "data": {
      "totalClasses": 6,
      "todayAttendance": 85,
      "absentStudents": 12,
      "pendingRequests": 3,
      "recentClasses": [
        {
          "id": "string",
          "subject": "Advanced Java Programming",
          "time": "07:30 - 09:30",
          "room": "LAB-101",
          "status": "upcoming|ongoing|completed|cancelled",
          "studentCount": 25,
          "date": "2024-10-15"
        }
      ],
      "notifications": [
        {
          "id": "string",
          "type": "leave_request|attendance|system",
          "title": "New Leave Request",
          "message": "Nguyen Van A submitted a leave request",
          "time": "2024-10-15T08:30:00Z",
          "isRead": false,
          "data": {
            "requestId": "string",
            "studentName": "Nguyen Van A"
          }
        }
      ]
    }
  }
}
```

### Get Classes List
```json
{
  "endpoint": "/teacher/classes",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "queryParams": {
    "status": "upcoming|ongoing|completed|cancelled",
    "date": "2024-10-15",
    "page": "number",
    "limit": "number"
  },
  "response": {
    "success": true,
    "data": {
      "classes": [
        {
          "id": "string",
          "subject": "Advanced Java Programming",
          "name": "Java Programming Advanced",
          "time": "07:30 - 09:30",
          "duration": "120",
          "room": "LAB-101",
          "studentCount": 25,
          "maxStudents": 30,
          "status": "upcoming|ongoing|completed|cancelled",
          "day": 1,
          "classCode": "JAVA2024",
          "startDate": "2024-01-15",
          "endDate": "2024-05-15",
          "schedule": {
            "monday": ["Buổi 1 (7:30 - 9:30)", "Buổi 2 (9:45 - 11:45)"],
            "wednesday": ["Buổi 1 (7:30 - 9:30)", "Buổi 2 (9:45 - 11:45)"],
            "friday": ["Buổi 1 (7:30 - 9:30)", "Buổi 2 (9:45 - 11:45)"]
          },
          "createdAt": "string",
          "updatedAt": "string"
        }
      ],
      "pagination": {
        "page": 1,
        "limit": 10,
        "total": 6,
        "totalPages": 1
      }
    }
  }
}
```

### Create Class
```json
{
  "endpoint": "/teacher/classes",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "subject": "Advanced Java Programming",
    "name": "Java Programming Advanced",
    "time": "07:30 - 09:30",
    "duration": "120",
    "room": "LAB-101",
    "maxStudents": 30,
    "day": 1,
    "startDate": "2024-01-15",
    "endDate": "2024-05-15",
    "description": "Advanced Java Programming Course",
    "schedule": {
      "monday": ["Buổi 1 (7:30 - 9:30)", "Buổi 2 (9:45 - 11:45)"],
      "wednesday": ["Buổi 1 (7:30 - 9:30)", "Buổi 2 (9:45 - 11:45)"],
      "friday": ["Buổi 1 (7:30 - 9:30)", "Buổi 2 (9:45 - 11:45)"]
    }
  },
  "response": {
    "success": true,
    "data": {
      "class": {
        "id": "string",
        "subject": "Advanced Java Programming",
        "classCode": "JAVA2024",
        "createdAt": "string"
      }
    },
    "message": "Class created successfully"
  }
}
```

### Get Class Details
```json
{
  "endpoint": "/teacher/classes/{classId}",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "response": {
    "success": true,
    "data": {
      "class": {
        "id": "string",
        "subject": "Advanced Java Programming",
        "name": "Java Programming Advanced",
        "teacher": "Dr. Nguyen Van A",
        "teacherId": "string",
        "students": 25,
        "maxStudents": 30,
        "schedule": "Mon, Wed, Fri - 07:30-09:30",
        "room": "LAB-101",
        "status": "active",
        "classCode": "JAVA2024",
        "startDate": "2024-01-15",
        "endDate": "2024-05-15",
        "description": "Advanced Java Programming Course"
      },
      "students": [
        {
          "id": "string",
          "studentId": "2021001",
          "fullName": "Nguyen Van A",
          "email": "student@example.com",
          "attendanceRate": 90,
          "totalSessions": 20,
          "presentCount": 18,
          "absentCount": 1,
          "lateCount": 1,
          "joinedAt": "string"
        }
      ],
      "attendanceStats": {
        "totalSessions": 20,
        "averageAttendance": 85,
        "totalStudents": 25
      }
    }
  }
}
```

### Get Attendance List
```json
{
  "endpoint": "/teacher/attendance/{classId}",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "queryParams": {
    "sessionId": "string",
    "date": "2024-10-15",
    "page": "number",
    "limit": "number"
  },
  "response": {
    "success": true,
    "data": {
      "attendance": [
        {
          "id": "string",
          "studentId": "string",
          "studentName": "Nguyen Van A",
          "studentCode": "2021001",
          "sessionId": "string",
          "sessionName": "Java Programming - Session 1",
          "date": "2024-10-15",
          "status": "present|absent|late",
          "checkInTime": "07:35:00",
          "checkOutTime": "09:25:00",
          "note": "string",
          "faceDetected": true
        }
      ],
      "summary": {
        "totalStudents": 25,
        "presentCount": 20,
        "absentCount": 3,
        "lateCount": 2,
        "attendanceRate": 88
      },
      "pagination": {
        "page": 1,
        "limit": 25,
        "total": 25,
        "totalPages": 1
      }
    }
  }
}
```

### Start Attendance Session
```json
{
  "endpoint": "/teacher/attendance/session/start",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "classId": "string",
    "sessionName": "Java Programming - Session 1",
    "duration": 30,
    "allowLateCheckIn": true,
    "lateThreshold": 15
  },
  "response": {
    "success": true,
    "data": {
      "session": {
        "id": "string",
        "classId": "string",
        "sessionName": "Java Programming - Session 1",
        "startTime": "2024-10-15T07:30:00Z",
        "endTime": "2024-10-15T08:00:00Z",
        "duration": 30,
        "status": "active",
        "qrCode": "string",
        "allowLateCheckIn": true,
        "lateThreshold": 15
      }
    },
    "message": "Attendance session started successfully"
  }
}
```

### Stop Attendance Session
```json
{
  "endpoint": "/teacher/attendance/session/{sessionId}/stop",
  "method": "PUT",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "response": {
    "success": true,
    "data": {
      "session": {
        "id": "string",
        "endTime": "2024-10-15T08:00:00Z",
        "status": "completed",
        "summary": {
          "totalStudents": 25,
          "presentCount": 20,
          "absentCount": 3,
          "lateCount": 2
        }
      }
    },
    "message": "Attendance session stopped successfully"
  }
}
```

### Get Leave Requests
```json
{
  "endpoint": "/teacher/leave-requests",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "queryParams": {
    "status": "pending|approved|rejected",
    "classId": "string",
    "page": "number",
    "limit": "number"
  },
  "response": {
    "success": true,
    "data": {
      "leaveRequests": [
        {
          "id": "string",
          "studentId": "string",
          "studentName": "Nguyen Van A",
          "studentCode": "2021001",
          "classId": "string",
          "className": "Advanced Java Programming",
          "subject": "Advanced Java Programming",
          "date": "2024-10-15",
          "dayOfWeek": "Thứ 3",
          "timeSlot": "Buổi 1 (7:30 - 9:30)",
          "reason": "Bị sốt cao, cần nghỉ ngơi và đi khám bác sĩ",
          "status": "pending|approved|rejected",
          "submittedDate": "2024-10-10",
          "approvedDate": "2024-10-11",
          "approverNote": "string",
          "attachments": [
            {
              "id": "string",
              "filename": "medical_certificate.pdf",
              "url": "string",
              "size": 1024000
            }
          ],
          "createdAt": "string",
          "updatedAt": "string"
        }
      ],
      "stats": {
        "total": 10,
        "pending": 3,
        "approved": 5,
        "rejected": 2
      },
      "pagination": {
        "page": 1,
        "limit": 10,
        "total": 10,
        "totalPages": 1
      }
    }
  }
}
```

### Approve Leave Request
```json
{
  "endpoint": "/teacher/leave-requests/{requestId}/approve",
  "method": "PUT",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "approverNote": "Đơn hợp lệ, chúc em sớm khỏe"
  },
  "response": {
    "success": true,
    "data": {
      "leaveRequest": {
        "id": "string",
        "status": "approved",
        "approvedDate": "2024-10-11T10:30:00Z",
        "approverNote": "Đơn hợp lệ, chúc em sớm khỏe"
      }
    },
    "message": "Leave request approved successfully"
  }
}
```

### Reject Leave Request
```json
{
  "endpoint": "/teacher/leave-requests/{requestId}/reject",
  "method": "PUT",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "approverNote": "Cần bổ sung lý do cụ thể hơn"
  },
  "response": {
    "success": true,
    "data": {
      "leaveRequest": {
        "id": "string",
        "status": "rejected",
        "approvedDate": "2024-10-11T10:30:00Z",
        "approverNote": "Cần bổ sung lý do cụ thể hơn"
      }
    },
    "message": "Leave request rejected"
  }
}
```

### Get Attendance Reports
```json
{
  "endpoint": "/teacher/reports/attendance",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "queryParams": {
    "classId": "string",
    "startDate": "2024-01-01",
    "endDate": "2024-12-31",
    "format": "json|csv|excel"
  },
  "response": {
    "success": true,
    "data": {
      "summary": {
        "totalStudents": 25,
        "totalSessions": 20,
        "averageAttendance": 85.5,
        "period": {
          "startDate": "2024-01-01",
          "endDate": "2024-12-31"
        }
      },
      "students": [
        {
          "studentId": "string",
          "studentName": "Nguyen Van A",
          "studentCode": "2021001",
          "totalSessions": 20,
          "presentCount": 18,
          "absentCount": 1,
          "lateCount": 1,
          "attendanceRate": 90,
          "sessions": [
            {
              "sessionId": "string",
              "date": "2024-10-15",
              "status": "present|absent|late",
              "checkInTime": "07:35:00"
            }
          ]
        }
      ],
      "sessions": [
        {
          "sessionId": "string",
          "sessionName": "Java Programming - Session 1",
          "date": "2024-10-15",
          "totalStudents": 25,
          "presentCount": 20,
          "absentCount": 3,
          "lateCount": 2,
          "attendanceRate": 88
        }
      ]
    }
  }
}
```

---

## 👨‍💼 ADMIN APIs

### Get Dashboard Stats
```json
{
  "endpoint": "/admin/dashboard/stats",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "response": {
    "success": true,
    "data": {
      "overview": {
        "totalTeachers": 15,
        "totalStudents": 250,
        "totalClasses": 45,
        "activeClasses": 12,
        "systemHealth": 98.5
      },
      "recentActivities": [
        {
          "id": "string",
          "type": "user_created|class_created|attendance|system",
          "description": "New teacher Dr. Nguyen Van A was added",
          "timestamp": "2024-10-15T08:30:00Z",
          "userId": "string",
          "metadata": {
            "entityType": "teacher",
            "entityId": "string"
          }
        }
      ],
      "statistics": {
        "todayAttendance": 85,
        "weeklyAttendance": [
          { "day": "Mon", "rate": 88 },
          { "day": "Tue", "rate": 92 },
          { "day": "Wed", "rate": 85 },
          { "day": "Thu", "rate": 90 },
          { "day": "Fri", "rate": 87 }
        ],
        "monthlyGrowth": {
          "teachers": 5.2,
          "students": 12.8,
          "classes": 8.1
        }
      }
    }
  }
}
```

### Get Teachers List
```json
{
  "endpoint": "/admin/teachers",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "queryParams": {
    "status": "active|inactive",
    "department": "string",
    "search": "string",
    "page": "number",
    "limit": "number"
  },
  "response": {
    "success": true,
    "data": {
      "teachers": [
        {
          "id": "string",
          "username": "teacher01",
          "fullName": "Dr. Nguyen Van A",
          "email": "teacher@example.com",
          "phone": "+84123456789",
          "department": "Computer Science",
          "status": "active|inactive",
          "avatar": "string",
          "joinDate": "2024-01-15",
          "totalClasses": 6,
          "totalStudents": 150,
          "lastLogin": "2024-10-15T08:30:00Z",
          "createdAt": "string",
          "updatedAt": "string"
        }
      ],
      "stats": {
        "total": 15,
        "active": 12,
        "inactive": 3
      },
      "pagination": {
        "page": 1,
        "limit": 10,
        "total": 15,
        "totalPages": 2
      }
    }
  }
}
```

### Create Teacher
```json
{
  "endpoint": "/admin/teachers",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "username": "teacher01",
    "fullName": "Dr. Nguyen Van A",
    "email": "teacher@example.com",
    "phone": "+84123456789",
    "department": "Computer Science",
    "password": "string"
  },
  "response": {
    "success": true,
    "data": {
      "teacher": {
        "id": "string",
        "username": "teacher01",
        "fullName": "Dr. Nguyen Van A",
        "email": "teacher@example.com",
        "department": "Computer Science",
        "status": "active",
        "createdAt": "string"
      }
    },
    "message": "Teacher created successfully"
  }
}
```

### Update Teacher
```json
{
  "endpoint": "/admin/teachers/{teacherId}",
  "method": "PUT",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "fullName": "Dr. Nguyen Van A",
    "email": "teacher@example.com",
    "phone": "+84123456789",
    "department": "Computer Science",
    "status": "active|inactive"
  },
  "response": {
    "success": true,
    "data": {
      "teacher": {
        "id": "string",
        "fullName": "Dr. Nguyen Van A",
        "email": "teacher@example.com",
        "updatedAt": "string"
      }
    },
    "message": "Teacher updated successfully"
  }
}
```

### Delete Teacher
```json
{
  "endpoint": "/admin/teachers/{teacherId}",
  "method": "DELETE",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "response": {
    "success": true,
    "message": "Teacher deleted successfully"
  },
  "errorResponse": {
    "success": false,
    "error": {
      "code": "TEACHER_HAS_CLASSES",
      "message": "Cannot delete teacher who has active classes"
    }
  }
}
```

### Get Students List
```json
{
  "endpoint": "/admin/students",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "queryParams": {
    "status": "active|inactive",
    "class": "string",
    "search": "string",
    "page": "number",
    "limit": "number"
  },
  "response": {
    "success": true,
    "data": {
      "students": [
        {
          "id": "string",
          "username": "student01",
          "fullName": "Nguyen Van A",
          "email": "student@example.com",
          "studentCode": "2021001",
          "class": "IT2021",
          "status": "active|inactive",
          "avatar": "string",
          "enrollDate": "2024-01-15",
          "totalClasses": 4,
          "attendanceRate": 95.5,
          "lastLogin": "2024-10-15T08:30:00Z",
          "hasFaceRegistered": true,
          "createdAt": "string",
          "updatedAt": "string"
        }
      ],
      "stats": {
        "total": 250,
        "active": 240,
        "inactive": 10,
        "withFaceRegistered": 200
      },
      "pagination": {
        "page": 1,
        "limit": 10,
        "total": 250,
        "totalPages": 25
      }
    }
  }
}
```

### Create Student
```json
{
  "endpoint": "/admin/students",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "username": "student01",
    "fullName": "Nguyen Van A",
    "email": "student@example.com",
    "studentCode": "2021001",
    "class": "IT2021",
    "password": "string"
  },
  "response": {
    "success": true,
    "data": {
      "student": {
        "id": "string",
        "username": "student01",
        "fullName": "Nguyen Van A",
        "email": "student@example.com",
        "studentCode": "2021001",
        "class": "IT2021",
        "status": "active",
        "createdAt": "string"
      }
    },
    "message": "Student created successfully"
  }
}
```

### Update Student
```json
{
  "endpoint": "/admin/students/{studentId}",
  "method": "PUT",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "fullName": "Nguyen Van A",
    "email": "student@example.com",
    "studentCode": "2021001",
    "class": "IT2021",
    "status": "active|inactive"
  },
  "response": {
    "success": true,
    "data": {
      "student": {
        "id": "string",
        "fullName": "Nguyen Van A",
        "email": "student@example.com",
        "updatedAt": "string"
      }
    },
    "message": "Student updated successfully"
  }
}
```

### Delete Student
```json
{
  "endpoint": "/admin/students/{studentId}",
  "method": "DELETE",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "response": {
    "success": true,
    "message": "Student deleted successfully"
  }
}
```

### Get AI Modal Status
```json
{
  "endpoint": "/admin/modal-ai/status",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "response": {
    "success": true,
    "data": {
      "aiModel": {
        "status": "active|inactive|training|error",
        "version": "1.2.3",
        "lastUpdate": "2024-10-15T08:30:00Z",
        "accuracy": 95.8,
        "totalFaceRegistered": 200,
        "lastTraining": "2024-10-10T10:00:00Z",
        "performance": {
          "averageProcessingTime": 0.5,
          "successRate": 98.2,
          "falsePositiveRate": 0.1,
          "falseNegativeRate": 1.7
        },
        "configuration": {
          "accuracyThreshold": 85.0,
          "detectionSensitivity": 0.7,
          "autoUpdate": true,
          "retrainInterval": 30
        }
      }
    }
  }
}
```

### Update AI Modal Config
```json
{
  "endpoint": "/admin/modal-ai/config",
  "method": "PUT",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "accuracyThreshold": 85.0,
    "detectionSensitivity": 0.7,
    "autoUpdate": true,
    "retrainInterval": 30
  },
  "response": {
    "success": true,
    "data": {
      "configuration": {
        "accuracyThreshold": 85.0,
        "detectionSensitivity": 0.7,
        "autoUpdate": true,
        "retrainInterval": 30,
        "updatedAt": "string"
      }
    },
    "message": "AI model configuration updated successfully"
  }
}
```

### Retrain AI Modal
```json
{
  "endpoint": "/admin/modal-ai/retrain",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "application/json"
  },
  "body": {
    "includeNewData": true,
    "trainingMode": "full|incremental"
  },
  "response": {
    "success": true,
    "data": {
      "trainingJob": {
        "id": "string",
        "status": "started",
        "estimatedDuration": 1800,
        "startedAt": "string"
      }
    },
    "message": "AI model retraining started"
  }
}
```

---

## 📁 FILE UPLOAD APIs

### Upload File
```json
{
  "endpoint": "/upload",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer {accessToken}",
    "Content-Type": "multipart/form-data"
  },
  "body": {
    "file": "File",
    "type": "attachment|avatar|face_image",
    "category": "leave_request|profile|face_recognition"
  },
  "response": {
    "success": true,
    "data": {
      "file": {
        "id": "string",
        "filename": "document.pdf",
        "originalName": "medical_certificate.pdf",
        "url": "https://example.com/uploads/document.pdf",
        "size": 1024000,
        "mimeType": "application/pdf",
        "type": "attachment",
        "category": "leave_request",
        "uploadedBy": "string",
        "createdAt": "string"
      }
    },
    "message": "File uploaded successfully"
  }
}
```

### Get File Info
```json
{
  "endpoint": "/upload/{fileId}",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "response": {
    "success": true,
    "data": {
      "file": {
        "id": "string",
        "filename": "document.pdf",
        "originalName": "medical_certificate.pdf",
        "url": "https://example.com/uploads/document.pdf",
        "size": 1024000,
        "mimeType": "application/pdf",
        "type": "attachment",
        "uploadedBy": "string",
        "createdAt": "string"
      }
    }
  }
}
```

### Delete File
```json
{
  "endpoint": "/upload/{fileId}",
  "method": "DELETE",
  "headers": {
    "Authorization": "Bearer {accessToken}"
  },
  "response": {
    "success": true,
    "message": "File deleted successfully"
  }
}
```

---

## 🚨 Error Responses

### Common Error Format
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": "Additional error details",
    "field": "fieldName",
    "timestamp": "2024-10-15T08:30:00Z"
  }
}
```

### Common Error Codes
- `UNAUTHORIZED` - 401: Token không hợp lệ hoặc hết hạn
- `FORBIDDEN` - 403: Không có quyền truy cập
- `NOT_FOUND` - 404: Resource không tồn tại
- `VALIDATION_ERROR` - 400: Dữ liệu đầu vào không hợp lệ
- `CONFLICT` - 409: Xung đột dữ liệu (trùng lặp)
- `INTERNAL_SERVER_ERROR` - 500: Lỗi server
- `RATE_LIMIT_EXCEEDED` - 429: Vượt quá giới hạn request

### Authentication Errors
- `INVALID_CREDENTIALS` - Username hoặc password không đúng
- `ACCOUNT_LOCKED` - Tài khoản bị khóa
- `TOKEN_EXPIRED` - Token đã hết hạn
- `INVALID_TOKEN` - Token không hợp lệ

### Business Logic Errors
- `CLASS_NOT_FOUND` - Lớp học không tồn tại
- `ALREADY_JOINED` - Đã tham gia lớp học
- `CLASS_FULL` - Lớp học đã đầy
- `CANNOT_EDIT` - Không thể chỉnh sửa
- `CANNOT_DELETE` - Không thể xóa
- `SESSION_NOT_ACTIVE` - Phiên điểm danh không hoạt động

---

## 📝 Notes

1. **Date Format**: Sử dụng ISO 8601 format (`YYYY-MM-DDTHH:mm:ssZ`)
2. **Pagination**: Tất cả endpoints danh sách đều hỗ trợ pagination
3. **Rate Limiting**: Giới hạn 1000 requests/hour cho mỗi user
4. **File Upload**: Hỗ trợ max 10MB per file
5. **WebSocket**: Real-time updates cho attendance sessions
6. **Caching**: Response được cache 5 phút cho dashboard stats

---

**Version**: 1.0.0  
**Last Updated**: October 15, 2024  
**Contact**: pbl6team@gmail.com