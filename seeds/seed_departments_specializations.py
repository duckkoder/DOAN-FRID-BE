"""
Script to seed initial departments and specializations data.

Usage:
    python seed_departments_specializations.py
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.department import Department
from app.models.specialization import Specialization


def seed_data():
    """Seed departments and specializations data."""
    db: Session = SessionLocal()
    
    try:
        # Check if data already exists
        existing_depts = db.query(Department).count()
        if existing_depts > 0:
            print(f"⚠️  Data already exists ({existing_depts} departments found). Skipping seed.")
            return
        
        print("🌱 Seeding departments and specializations...")
        
        # Sample data structure
        departments_data = [
            {
                "name": "Khoa Công nghệ Thông tin",
                "code": "CNTT",
                "description": "Khoa đào tạo các ngành liên quan đến công nghệ thông tin",
                "specializations": [
                    {
                        "name": "Công nghệ Phần mềm",
                        "code": "SE",
                        "description": "Chuyên ngành đào tạo kỹ sư phần mềm"
                    },
                    {
                        "name": "Khoa học Máy tính",
                        "code": "CS",
                        "description": "Chuyên ngành khoa học máy tính cơ bản"
                    },
                    {
                        "name": "Hệ thống Thông tin",
                        "code": "IS",
                        "description": "Chuyên ngành hệ thống thông tin quản lý"
                    },
                    {
                        "name": "AI & Machine Learning",
                        "code": "AI-ML",
                        "description": "Chuyên ngành trí tuệ nhân tạo và học máy"
                    }
                ]
            },
            {
                "name": "Khoa Điện - Điện tử",
                "code": "EE",
                "description": "Khoa đào tạo các ngành điện, điện tử, tự động hóa",
                "specializations": [
                    {
                        "name": "Kỹ thuật Điện",
                        "code": "EE-POWER",
                        "description": "Chuyên ngành kỹ thuật điện"
                    },
                    {
                        "name": "Điện tử - Viễn thông",
                        "code": "EE-TELECOM",
                        "description": "Chuyên ngành điện tử và viễn thông"
                    },
                    {
                        "name": "Tự động hóa",
                        "code": "AUTOMATION",
                        "description": "Chuyên ngành tự động hóa công nghiệp"
                    }
                ]
            },
            {
                "name": "Khoa Cơ khí",
                "code": "ME",
                "description": "Khoa đào tạo kỹ sư cơ khí",
                "specializations": [
                    {
                        "name": "Cơ khí Chế tạo máy",
                        "code": "ME-MANUF",
                        "description": "Chuyên ngành thiết kế và chế tạo máy"
                    },
                    {
                        "name": "Cơ khí Động lực",
                        "code": "ME-POWER",
                        "description": "Chuyên ngành động lực học và năng lượng"
                    },
                    {
                        "name": "Cơ điện tử",
                        "code": "MECHATRONICS",
                        "description": "Chuyên ngành cơ điện tử"
                    }
                ]
            },
            {
                "name": "Khoa Kinh tế",
                "code": "ECON",
                "description": "Khoa đào tạo các ngành kinh tế, quản trị",
                "specializations": [
                    {
                        "name": "Quản trị Kinh doanh",
                        "code": "BBA",
                        "description": "Chuyên ngành quản trị kinh doanh"
                    },
                    {
                        "name": "Kinh tế",
                        "code": "ECONOMICS",
                        "description": "Chuyên ngành kinh tế học"
                    },
                    {
                        "name": "Kế toán",
                        "code": "ACCOUNTING",
                        "description": "Chuyên ngành kế toán"
                    }
                ]
            },
            {
                "name": "Khoa Ngoại ngữ",
                "code": "LANG",
                "description": "Khoa đào tạo ngoại ngữ",
                "specializations": [
                    {
                        "name": "Tiếng Anh",
                        "code": "ENGLISH",
                        "description": "Chuyên ngành tiếng Anh"
                    },
                    {
                        "name": "Tiếng Nhật",
                        "code": "JAPANESE",
                        "description": "Chuyên ngành tiếng Nhật"
                    },
                    {
                        "name": "Tiếng Trung",
                        "code": "CHINESE",
                        "description": "Chuyên ngành tiếng Trung"
                    }
                ]
            }
        ]
        
        # Insert data
        total_depts = 0
        total_specs = 0
        
        for dept_data in departments_data:
            # Create department
            specializations_list = dept_data.pop("specializations")
            department = Department(**dept_data)
            db.add(department)
            db.flush()  # Get department ID
            
            total_depts += 1
            print(f"  ✅ Created department: {department.name} ({department.code})")
            
            # Create specializations
            for spec_data in specializations_list:
                spec_data["department_id"] = department.id
                specialization = Specialization(**spec_data)
                db.add(specialization)
                total_specs += 1
                print(f"     ↳ Added specialization: {specialization.name} ({specialization.code})")
        
        # Commit transaction
        db.commit()
        
        print(f"\n✅ Successfully seeded {total_depts} departments and {total_specs} specializations!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
