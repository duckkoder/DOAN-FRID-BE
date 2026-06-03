# Tenant Migration Revision Guide

File nay dung de tao Alembic revision cho schema tenant DB.

## 1. Nguyen tac

Tenant migration la file nam trong:

```txt
back-end/alembic/versions/
```

Production khong tao file revision. Production chi chay migration tu file da co trong source/image.

Flow dung:

```txt
Dev sua model
-> Dev tao revision bang DB template
-> Review upgrade()/downgrade()
-> Commit file trong alembic/versions
-> Build/deploy backend image
-> Super admin product bam Migration de upgrade tenant DB
```

## 2. DB template mac dinh

Script `scripts/create_tenant_revision.py` mac dinh dung DB template fix cung trong file:

```txt
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ai_attendance
POSTGRES_USER=postgres
POSTGRES_PASSWORD=Ttd02042004@
# DATABASE_URL is auto-built by script from these constants.
```

`POSTGRES_DB` nen la DB template/sandbox dung de so sanh schema, khong nen la DB production.

Khuyen nghi lau dai:

```txt
POSTGRES_DB=frid_template_db
```

DB template nen:

```txt
- Khong chua du lieu nghiep vu quan trong
- Dang o alembic head truoc khi generate revision
- Co extension can thiet, vi du pgvector
```

## 3. Tao revision mac dinh tu DB template fix cung

```powershell
cd D:\PBL6\back-end

.\venv311\Scripts\python.exe scripts\create_tenant_revision.py `
  --upgrade-head-first `
  -m "add tenant settings"
```

Lenh tren se:

```txt
1. Build template DB URL tu constant trong script
2. Chay alembic upgrade head tren DB template
3. Chay alembic revision --autogenerate
4. Tao file moi trong alembic/versions
```

## 4. Tao revision bang tenant that neu can

Co the dung mot tenant dang co trong platform DB lam template:

```powershell
.\venv311\Scripts\python.exe scripts\create_tenant_revision.py `
  --tenant-code dut `
  --upgrade-head-first `
  -m "add tenant settings"
```

Script se doc `platform_attandance_db.tenants`, giai ma password tenant DB, roi dung DB do de autogenerate.

Chi nen dung cach nay khi tenant do la DB mau/sandbox. Khong nen dung tenant production.

## 5. Tao revision bang URL truyen thang

```powershell
.\venv311\Scripts\python.exe scripts\create_tenant_revision.py `
  --database-url "postgresql://postgres:Ttd02042004%40@localhost:5432/ai_attendance" `
  --upgrade-head-first `
  -m "add tenant settings"
```

Neu password co ky tu dac biet khi viet URL thu cong, can encode. Vi du `@` thanh `%40`.

Voi DB template fix cung trong script, khong can encode password vi script tu build URL bang SQLAlchemy.

## 6. Sau khi script tao file

Mo file moi trong:

```txt
back-end/alembic/versions/
```

Kiem tra ky:

```txt
- upgrade() co dung thay doi mong muon khong
- downgrade() co rollback duoc khong
- Khong drop nham bang/cot dang co du lieu quan trong
- Neu drop table/cot, chac chan product chap nhan mat du lieu do
```

Sau do commit file migration.

## 7. Product co truy cap duoc file migration khong?

Co, neu file migration da duoc commit va build vao backend image.

Vi du Dockerfile copy source backend vao image thi cac file nay se co trong container:

```txt
back-end/alembic/
back-end/alembic.ini
back-end/alembic/versions/*.py
```

Khi super admin bam `Migration`, backend product chay:

```txt
alembic upgrade head
```

Alembic se doc file trong `alembic/versions` cua image hien tai va cap nhat bang `alembic_version` trong DB tenant.

Khong nen tao revision tren production container vi:

```txt
- File sinh ra khong duoc commit
- Deploy lai co the mat file
- Nhieu instance backend co the lech file
- Khong co buoc review code migration
```

## 8. Lenh huu ich

Xem DB template dang revision nao:

```powershell
$env:ALEMBIC_DATABASE_URL="postgresql://postgres:Ttd02042004%40@localhost:5432/ai_attendance"
.\venv311\Scripts\python.exe -m alembic current
```

Upgrade DB template len head:

```powershell
$env:ALEMBIC_DATABASE_URL="postgresql://postgres:Ttd02042004%40@localhost:5432/ai_attendance"
.\venv311\Scripts\python.exe -m alembic upgrade head
```

Xem history:

```powershell
.\venv311\Scripts\python.exe -m alembic history
```
