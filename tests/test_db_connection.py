from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text

load_dotenv()  # load .env từ cwd (d:\PBL6\back-end)

def test_postgres_connection():
    db_url = os.getenv("DATABASE_URL")
    assert db_url, "DATABASE_URL chưa được đặt trong .env"

    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1