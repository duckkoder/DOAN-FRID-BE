from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text

load_dotenv()


def test_platform_postgres_connection():
    db_url = os.getenv("PLATFORM_DATABASE_URL")
    assert db_url, "PLATFORM_DATABASE_URL chưa được đặt trong .env"

    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
