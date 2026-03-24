# 🗄️ Database Migration Guide

Backend sử dụng **Alembic** để quản lý database migration.

---

## ⚙️ Cài đặt ban đầu

```bash
cd d:/PBL6/back-end

# Kích hoạt virtual environment
venv311\Scripts\activate        # Windows
# source venv311/bin/activate   # Linux/Mac

# Cài dependencies (nếu chưa cài)
pip install -r requirements.txt
```

---

## 🔧 Cấu hình Database

Tạo file `.env` từ `.env.example` và điền thông tin DB:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=attendance_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

> ⚠️ `alembic.ini` đọc connection string từ `.env` thông qua `env.py` — **không cần sửa `alembic.ini`** trực tiếp.

---

## 🚀 Chạy Migration

### Áp dụng tất cả migrations (lên version mới nhất)
```bash
alembic upgrade head
```

### Xem trạng thái migration hiện tại
```bash
alembic current
```

### Xem lịch sử migration
```bash
alembic history --verbose
```

---

## ✍️ Tạo Migration Mới

### Tự động generate từ model thay đổi
```bash
alembic revision --autogenerate -m "mô_tả_thay_đổi"
```

### Tạo migration rỗng (viết tay)
```bash
alembic revision -m "mô_tả_thay_đổi"
```

> 📁 File migration được tạo tại `alembic/versions/`

---

## ⏪ Rollback

### Quay về 1 bước trước
```bash
alembic downgrade -1
```

### Quay về một revision cụ thể
```bash
alembic downgrade <revision_id>
```

### Rollback toàn bộ (về trạng thái ban đầu)
```bash
alembic downgrade base
```

---

## 🌱 Seed Data (Tùy chọn)

Sau khi chạy migration, có thể seed dữ liệu mẫu:

```bash
python seeds/seed_departments_specializations.py
```

---

## 📋 Danh sách Migrations hiện có

| Thứ tự | Mô tả |
|--------|-------|
| 1 | Initial migration |
| 2 | Create all tables from DBML design |
| 3 | Create auth tables |
| ... | *(xem `alembic/versions/` để biết đầy đủ)* |
| 28 | Add spoof detections table |

---

## ❗ Lưu ý

- Luôn chạy `alembic upgrade head` sau khi `git pull` nếu có migration mới
- Không xóa file trong `alembic/versions/` thủ công
- Nếu dùng **pgvector**, đảm bảo extension đã được enable trên PostgreSQL: `CREATE EXTENSION IF NOT EXISTS vector;`
