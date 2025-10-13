"""Test database connection."""
from app.core.database import get_db, engine
from sqlalchemy import text

def test_connection():
    """Test if database connection works."""
    try:
        # Test 1: Engine connection
        print("Testing engine connection...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"✅ Engine connection OK: {result.scalar()}")
        
        # Test 2: Session from get_db
        print("\nTesting get_db session...")
        db = next(get_db())
        result = db.execute(text("SELECT version()"))
        version = result.scalar()
        print(f"✅ PostgreSQL version: {version}")
        db.close()
        
        # Test 3: Check tables
        print("\nChecking existing tables...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result]
            if tables:
                print(f"✅ Found tables: {tables}")
            else:
                print("⚠️  No tables found! Need to run migrations.")
        
        print("\n✅ All database tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()