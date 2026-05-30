"""Create the first platform super admin.

Usage:
    python seeds/create_super_admin.py
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.core.security import get_password_hash  # noqa: E402
from app.platform.database import PlatformSessionLocal  # noqa: E402
from app.platform.models.platform_user import PlatformUser  # noqa: E402


def main() -> None:
    email = os.getenv("SUPER_ADMIN_EMAIL")
    password = os.getenv("SUPER_ADMIN_PASSWORD")
    full_name = os.getenv("SUPER_ADMIN_FULL_NAME", "Platform Super Admin")

    if not email or not password:
        raise SystemExit("Set SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD before running this seed.")

    db = PlatformSessionLocal()
    try:
        existing = db.query(PlatformUser).filter(PlatformUser.email == email).first()
        if existing:
            print(f"Super admin already exists: {email}")
            return

        user = PlatformUser(
            full_name=full_name,
            email=email,
            password_hash=get_password_hash(password),
            role="super_admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Created super admin: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
