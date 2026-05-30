# Platform DB Guide

File nay dung khi can setup hoac migrate `platform_attandance_db`.

## 1. Env can co

Backend chi doc mot file env:

```txt
back-end/.env
```

`.env` nen chia thanh 2 phan: platform/SaaS o tren, app nghiep vu o duoi.

```env
# Platform / SaaS
PLATFORM_DATABASE_URL=postgresql://postgres:Ttd02042004%40@localhost:5432/platform_attandance_db
TENANT_DB_HOST=localhost
TENANT_DB_PORT=5432
SECRET_ENCRYPTION_KEY=your-stable-secret-key

SUPER_ADMIN_EMAIL=superadmin@example.com
SUPER_ADMIN_PASSWORD=ChangeMe123
SUPER_ADMIN_FULL_NAME=Platform Super Admin

# Main app
DATABASE_URL=postgresql://postgres:Ttd02042004%40@localhost:5432/ai_attendance
```

`PLATFORM_DATABASE_URL` nen dung PostgreSQL user co quyen tao database/role vi platform can tao tenant DB.
`TENANT_DB_HOST` la host luu vao tenant moi. Dev thuong la `localhost`; Docker production thuong la `db`.

## 2. Setup platform DB lan dau

Tao database rong mot lan bang pgAdmin, psql hoac createdb:

```sql
CREATE DATABASE platform_attandance_db;
```

Sau do apply schema bang Alembic:

```powershell
cd d:\PBL6\back-end
.\venv311\Scripts\python.exe -m alembic -c alembic_platform.ini upgrade head
```

Neu can tao super admin dau tien thi moi chay seed account:

```powershell
.\venv311\Scripts\python.exe seeds\create_super_admin.py
```

Lenh tren se:

```txt
1. Alembic tao/cap nhat schema platform: tenants, platform_users
2. Seed chi tao super_admin dau tien neu can
```

## 3. Khi doi schema platform

Khong xoa DB. Tao migration moi trong `back-end/alembic_platform/versions`.

Vi du can them cot `plan` vao bang `tenants`:

```powershell
cd d:\PBL6\back-end
.\venv311\Scripts\python.exe -m alembic -c alembic_platform.ini revision -m "add tenant plan"
```

Sua file migration vua tao:

```python
def upgrade() -> None:
    op.add_column("tenants", sa.Column("plan", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "plan")
```

Sau do chay:

```powershell
.\venv311\Scripts\python.exe -m alembic -c alembic_platform.ini upgrade head
```

## 4. Kiem tra migration platform

Xem head hien tai:

```powershell
.\venv311\Scripts\python.exe -m alembic -c alembic_platform.ini heads
```

Xem lich su:

```powershell
.\venv311\Scripts\python.exe -m alembic -c alembic_platform.ini history
```

Xem current revision cua DB:

```powershell
.\venv311\Scripts\python.exe -m alembic -c alembic_platform.ini current
```

## 5. Tao tenant moi tren UI

Vao:

```txt
http://localhost:5173/platform/login
```

Dang nhap bang `SUPER_ADMIN_EMAIL` va `SUPER_ADMIN_PASSWORD`.

Khi tao tenant, chi can nhap:

```txt
School name
School code
DB host
DB port
S3 region
```

Backend tu sinh:

```txt
slug = school_code
db_name = frid_{school_code}_db
db_user = db_user_{school_code}
db_password = random
storage_bucket = bucket-s3-{school_code}
storage_prefix = tenants/{school_code}/
```

`school_code` phai unique.

## 6. Khi tao tenant, backend lam gi

```txt
1. Check school_code/slug chua ton tai
2. Insert tenant vao platform_attandance_db.tenants
3. Tao PostgreSQL role db_user_{school_code}
4. Tao database frid_{school_code}_db
5. Chay Alembic tenant migration vao DB tenant
6. Tra tenant metadata ve frontend
```

Sau khi tao tenant, UI se hoi tao admin dau tien cho tenant.

## 7. Chay migration moi nhat cho tenant da ton tai

Khi co migration moi trong `back-end/alembic/versions`, super_admin co the chay tren UI Platform bang nut `Run migrations`.

API tuong ung:

```txt
POST /api/v1/platform/tenants/{tenant_id}/migrations
POST /api/v1/platform/migrations/tenants
```

Endpoint batch chay tung tenant va tra ket qua rieng cho moi tenant. Mot tenant fail khong chan cac tenant khac.

## 8. Khong nen lam

```txt
- Khong xoa platform_attandance_db de cap nhat schema
- Khong sua truc tiep bang platform bang tay neu co the viet migration
- Khong commit .env
- Khong doi SECRET_ENCRYPTION_KEY sau khi da co encrypted secrets
```

## 9. Files quan trong

```txt
back-end/.env
back-end/alembic_platform.ini
back-end/alembic_platform/
back-end/seeds/create_super_admin.py   # optional, chi tao account dau tien
back-end/app/platform/
```
