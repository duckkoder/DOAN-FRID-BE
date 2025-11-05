"""Service for CSV import functionality."""
import csv
import io
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException, status

from app.schemas.csv_import import (
    StudentCSVRow,
    TeacherCSVRow,
    StudentCSVPreviewResponse,
    TeacherCSVPreviewResponse,
    CSVImportResult
)
from app.models.department import Department
from app.models.specialization import Specialization
from app.services.student_service import StudentService
from app.services.teacher_service import TeacherService


class CSVImportService:
    """Service for handling CSV imports."""
    
    @staticmethod
    async def parse_student_csv(file: UploadFile, db: Session) -> StudentCSVPreviewResponse:
        """
        Parse and validate student CSV file.
        
        Expected CSV format:
        full_name,mssv,password,phone,department_name,academic_year,date_of_birth
        
        Returns preview with validation results.
        """
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File phải có định dạng CSV"
            )
        
        content = await file.read()
        try:
            decoded = content.decode('utf-8-sig')  # Handle BOM
        except UnicodeDecodeError:
            try:
                decoded = content.decode('utf-8')
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File CSV không đúng encoding. Vui lòng sử dụng UTF-8"
                )
        
        # Get valid departments for validation
        departments = {d.name: d.id for d in db.query(Department).all()}
        
        csv_reader = csv.DictReader(io.StringIO(decoded))
        rows: List[StudentCSVRow] = []
        row_number = 1  # Start from 1 (header is row 0)
        
        for row_data in csv_reader:
            row_number += 1
            errors = []
            is_valid = True
            
            try:
                # Clean and validate data
                row = StudentCSVRow(
                    row_number=row_number,
                    full_name=row_data.get('full_name', '').strip(),
                    mssv=row_data.get('mssv', '').strip(),
                    password=row_data.get('password', '').strip(),
                    phone=row_data.get('phone', '').strip() or None,
                    department_name=row_data.get('department_name', '').strip() or None,
                    academic_year=row_data.get('academic_year', '').strip() or None,
                    date_of_birth=row_data.get('date_of_birth', '').strip() or None,
                )
                
                # Validate department exists
                if row.department_name and row.department_name not in departments:
                    is_valid = False
                    errors.append(f"Khoa '{row.department_name}' không tồn tại trong hệ thống")
                    row.is_valid = False
                    row.errors = errors
                    
            except Exception as e:
                # Validation failed - parse error messages
                is_valid = False
                error_msg = str(e)
                errors = []
                
                # Extract validation errors from Pydantic ValidationError
                if 'validation error' in error_msg.lower():
                    # Parse pydantic errors
                    import re
                    # Split by lines and process each error
                    lines = error_msg.split('\n')
                    
                    for i, line in enumerate(lines):
                        line = line.strip()
                        
                        # Extract "Value error, <message>"
                        if line.startswith('Value error,'):
                            message = re.sub(r'Value error,\s*', '', line)
                            message = re.sub(r'\s*\[type=.*$', '', message)
                            errors.append(message.strip())
                        
                        # Extract "String should have at least X characters"
                        elif line.startswith('String should have at least'):
                            match = re.search(r'String should have at least (\d+) characters', line)
                            if match:
                                errors.append(f"Mật khẩu phải có ít nhất {match.group(1)} ký tự")
                        
                        # Extract "Field required"
                        elif line.startswith('Field required'):
                            # Previous line should be the field name
                            if i > 0:
                                field_name = lines[i - 1].strip()
                                field_map = {
                                    'mssv': 'MSSV',
                                    'password': 'Mật khẩu',
                                    'full_name': 'Họ tên',
                                    'phone': 'Số điện thoại'
                                }
                                errors.append(f"{field_map.get(field_name, field_name)} không được để trống")
                
                # If no errors parsed, use raw message
                if not errors:
                    errors = [error_msg]
                
                # Create row with raw data (bypass validation)
                row = StudentCSVRow.model_construct(
                    row_number=row_number,
                    full_name=row_data.get('full_name', '').strip() or 'N/A',
                    mssv=row_data.get('mssv', '').strip() or 'N/A',
                    password='***',  # Don't show password
                    phone=row_data.get('phone', '').strip() or None,
                    department_name=row_data.get('department_name', '').strip() or None,
                    academic_year=row_data.get('academic_year', '').strip() or None,
                    date_of_birth=row_data.get('date_of_birth', '').strip() or None,
                    is_valid=False,
                    errors=errors
                )
            
            rows.append(row)
        
        valid_rows = sum(1 for r in rows if r.is_valid)
        invalid_rows = len(rows) - valid_rows
        
        return StudentCSVPreviewResponse(
            total_rows=len(rows),
            valid_rows=valid_rows,
            invalid_rows=invalid_rows,
            rows=rows,
            can_import=valid_rows > 0  # Allow import if at least 1 valid row
        )
    
    @staticmethod
    async def parse_teacher_csv(file: UploadFile, db: Session) -> TeacherCSVPreviewResponse:
        """
        Parse and validate teacher CSV file.
        
        Expected CSV format:
        full_name,email,password,teacher_code,phone,department_name,specialization_name
        """
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File phải có định dạng CSV"
            )
        
        content = await file.read()
        try:
            decoded = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                decoded = content.decode('utf-8')
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File CSV không đúng encoding. Vui lòng sử dụng UTF-8"
                )
        
        # Get valid departments and specializations for validation
        departments = {d.name: d.id for d in db.query(Department).all()}
        specializations = {s.name: s.id for s in db.query(Specialization).all()}
        
        csv_reader = csv.DictReader(io.StringIO(decoded))
        rows: List[TeacherCSVRow] = []
        row_number = 1
        
        for row_data in csv_reader:
            row_number += 1
            errors = []
            is_valid = True
            
            try:
                row = TeacherCSVRow(
                    row_number=row_number,
                    full_name=row_data.get('full_name', '').strip(),
                    email=row_data.get('email', '').strip(),
                    password=row_data.get('password', '').strip(),
                    teacher_code=row_data.get('teacher_code', '').strip(),
                    phone=row_data.get('phone', '').strip() or None,
                    department_name=row_data.get('department_name', '').strip() or None,
                    specialization_name=row_data.get('specialization_name', '').strip() or None,
                )
                
                # Validate department exists
                if row.department_name and row.department_name not in departments:
                    is_valid = False
                    errors.append(f"Khoa '{row.department_name}' không tồn tại trong hệ thống")
                
                # Validate specialization exists
                if row.specialization_name and row.specialization_name not in specializations:
                    is_valid = False
                    errors.append(f"Chuyên ngành '{row.specialization_name}' không tồn tại trong hệ thống")
                    
            except ValueError as e:
                is_valid = False
                error_msg = str(e)
                errors = []
                
                # Parse Pydantic validation errors if present
                import re
                if 'validation error' in error_msg.lower():
                    # Split by lines and process each error
                    lines = error_msg.split('\n')
                    
                    for i, line in enumerate(lines):
                        line = line.strip()
                        
                        # Extract "Value error, <message>"
                        if line.startswith('Value error,'):
                            message = re.sub(r'Value error,\s*', '', line)
                            message = re.sub(r'\s*\[type=.*$', '', message)
                            errors.append(message.strip())
                        
                        # Extract "String should have at least X characters"
                        elif line.startswith('String should have at least'):
                            match = re.search(r'String should have at least (\d+) characters', line)
                            if match:
                                errors.append(f"Mật khẩu phải có ít nhất {match.group(1)} ký tự")
                        
                        # Extract "Field required"
                        elif line.startswith('Field required'):
                            # Previous line should be the field name
                            if i > 0:
                                field_name = lines[i - 1].strip()
                                field_map = {
                                    'email': 'Email',
                                    'password': 'Mật khẩu',
                                    'teacher_code': 'Mã giáo viên',
                                    'full_name': 'Họ tên'
                                }
                                errors.append(f"{field_map.get(field_name, field_name)} không được để trống")
                
                # If no errors parsed or not a ValidationError, use the raw message
                if not errors:
                    errors = [error_msg]
                
                # Use model_construct to bypass validation
                row = TeacherCSVRow.model_construct(
                    row_number=row_number,
                    full_name=row_data.get('full_name', '').strip() or 'N/A',
                    email=row_data.get('email', '').strip() or 'N/A',
                    password='***',
                    teacher_code=row_data.get('teacher_code', '').strip() or 'N/A',
                    phone=row_data.get('phone', '').strip() or None,
                    department_name=row_data.get('department_name', '').strip() or None,
                    specialization_name=row_data.get('specialization_name', '').strip() or None,
                    is_valid=False,
                    errors=errors
                )
            except Exception as e:
                is_valid = False
                error_msg = str(e)
                errors = []
                
                # Parse Pydantic validation errors if present
                import re
                if 'validation error' in error_msg.lower():
                    # Split by lines and process each error
                    lines = error_msg.split('\n')
                    
                    for i, line in enumerate(lines):
                        line = line.strip()
                        
                        # Extract "Value error, <message>"
                        if line.startswith('Value error,'):
                            message = re.sub(r'Value error,\s*', '', line)
                            message = re.sub(r'\s*\[type=.*$', '', message)
                            errors.append(message.strip())
                        
                        # Extract "String should have at least X characters"
                        elif line.startswith('String should have at least'):
                            match = re.search(r'String should have at least (\d+) characters', line)
                            if match:
                                errors.append(f"Mật khẩu phải có ít nhất {match.group(1)} ký tự")
                        
                        # Extract "Field required"
                        elif line.startswith('Field required'):
                            # Previous line should be the field name
                            if i > 0:
                                field_name = lines[i - 1].strip()
                                field_map = {
                                    'email': 'Email',
                                    'password': 'Mật khẩu',
                                    'teacher_code': 'Mã giáo viên',
                                    'full_name': 'Họ tên'
                                }
                                errors.append(f"{field_map.get(field_name, field_name)} không được để trống")
                
                if not errors:
                    errors = [f"Lỗi không xác định: {error_msg}"]
                
                # Use model_construct to bypass validation
                row = TeacherCSVRow.model_construct(
                    row_number=row_number,
                    full_name=row_data.get('full_name', '').strip() or 'N/A',
                    email=row_data.get('email', '').strip() or 'N/A',
                    password='***',
                    teacher_code=row_data.get('teacher_code', '').strip() or 'N/A',
                    phone=row_data.get('phone', '').strip() or None,
                    department_name=row_data.get('department_name', '').strip() or None,
                    specialization_name=row_data.get('specialization_name', '').strip() or None,
                    is_valid=False,
                    errors=errors
                )
            
            row.is_valid = is_valid
            row.errors = errors
            rows.append(row)
        
        valid_rows = sum(1 for r in rows if r.is_valid)
        invalid_rows = len(rows) - valid_rows
        
        return TeacherCSVPreviewResponse(
            total_rows=len(rows),
            valid_rows=valid_rows,
            invalid_rows=invalid_rows,
            rows=rows,
            can_import=valid_rows > 0  # Allow import if at least 1 valid row
        )
    
    @staticmethod
    async def import_students(db: Session, rows: List[Dict[str, Any]]) -> CSVImportResult:
        """Import validated student rows into database."""
        successful = 0
        failed = 0
        errors = []
        
        # Get department mapping
        departments = {d.name: d.id for d in db.query(Department).all()}
        
        for idx, row in enumerate(rows):
            try:
                # Construct full email from MSSV
                mssv = row['mssv']  # 9 digits
                full_email = f"{mssv}@sv1.dut.udn.vn"
                student_code = mssv
                
                # Get department ID
                department_id = None
                if row.get('department_name'):
                    department_id = departments.get(row['department_name'])
                    if department_id is None and row['department_name']:
                        raise ValueError(f"Khoa '{row['department_name']}' không tồn tại")
                
                # Parse date of birth
                date_of_birth = None
                if row.get('date_of_birth'):
                    try:
                        # Try YYYY-MM-DD format
                        date_of_birth = datetime.strptime(row['date_of_birth'], '%Y-%m-%d').date()
                    except ValueError:
                        try:
                            # Try DD/MM/YYYY format
                            date_of_birth = datetime.strptime(row['date_of_birth'], '%d/%m/%Y').date()
                        except ValueError:
                            raise ValueError(f"Ngày sinh '{row['date_of_birth']}' không đúng định dạng (YYYY-MM-DD hoặc DD/MM/YYYY)")
                
                # Create student
                from app.schemas.auth import RegisterRequest
                register_data = RegisterRequest(
                    full_name=row['full_name'],
                    email=full_email,
                    password=row['password'],
                    role='student',
                    phone=row.get('phone'),
                    student_code=student_code,
                    department_id=department_id,
                    academic_year=row.get('academic_year'),
                    date_of_birth=date_of_birth
                )
                
                from app.services.auth_service import AuthService
                await AuthService.register(db, register_data)
                successful += 1
                
            except HTTPException as e:
                failed += 1
                errors.append({
                    "row": idx + 1,
                    "email": row.get('mssv', 'N/A'),
                    "error": e.detail
                })
            except Exception as e:
                failed += 1
                error_msg = str(e)
                
                # Parse Pydantic validation errors
                import re
                if 'validation error' in error_msg.lower():
                    parsed_errors = []
                    lines = error_msg.split('\n')
                    i = 0
                    while i < len(lines):
                        line = lines[i].strip()
                        
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            
                            # Extract "Value error, <message>"
                            if next_line.startswith('Value error,'):
                                message = re.sub(r'Value error,\s*', '', next_line)
                                message = re.sub(r'\s*\[type=.*?\].*$', '', message)
                                parsed_errors.append(message.strip())
                                i += 1
                            # Extract "String should have at least X characters"
                            elif 'String should have at least' in next_line:
                                match = re.search(r'String should have at least (\d+) characters', next_line)
                                if match:
                                    parsed_errors.append(f"Mật khẩu phải có ít nhất {match.group(1)} ký tự")
                                i += 1
                            # Extract "Field required"
                            elif next_line.startswith('Field required'):
                                field_name = line
                                field_map = {
                                    'mssv': 'MSSV',
                                    'password': 'Mật khẩu',
                                    'full_name': 'Họ tên',
                                    'phone': 'Số điện thoại'
                                }
                                parsed_errors.append(f"{field_map.get(field_name, field_name)} không được để trống")
                                i += 1
                        i += 1
                    
                    if parsed_errors:
                        error_msg = '; '.join(parsed_errors)
                # Extract meaningful error from exception
                elif "already registered" in error_msg.lower():
                    error_msg = f"MSSV {row.get('mssv')} đã được đăng ký"
                elif "already exists" in error_msg.lower():
                    error_msg = f"MSSV {row.get('mssv')} đã tồn tại trong hệ thống"
                
                errors.append({
                    "row": idx + 1,
                    "email": row.get('mssv', 'N/A'),
                    "error": error_msg
                })
        
        return CSVImportResult(
            success=failed == 0,
            total_attempted=len(rows),
            successful=successful,
            failed=failed,
            errors=errors,
            message=f"Thành công: {successful}/{len(rows)}. Thất bại: {failed}"
        )
    
    @staticmethod
    async def import_teachers(db: Session, rows: List[Dict[str, Any]]) -> CSVImportResult:
        """Import validated teacher rows into database."""
        successful = 0
        failed = 0
        errors = []
        
        # Get mappings
        departments = {d.name: d.id for d in db.query(Department).all()}
        specializations = {s.name: s.id for s in db.query(Specialization).all()}
        
        for idx, row in enumerate(rows):
            try:
                # Construct full email
                full_email = f"{row['email']}@dut.udn.vn"
                
                # Get department and specialization IDs
                department_id = None
                if row.get('department_name'):
                    department_id = departments.get(row['department_name'])
                    if department_id is None and row['department_name']:
                        raise ValueError(f"Khoa '{row['department_name']}' không tồn tại")
                
                specialization_id = None
                if row.get('specialization_name'):
                    specialization_id = specializations.get(row['specialization_name'])
                    if specialization_id is None and row['specialization_name']:
                        raise ValueError(f"Chuyên ngành '{row['specialization_name']}' không tồn tại")
                
                # Create teacher
                from app.schemas.auth import RegisterRequest
                register_data = RegisterRequest(
                    full_name=row['full_name'],
                    email=full_email,
                    password=row['password'],
                    role='teacher',
                    phone=row.get('phone'),
                    teacher_code=row['teacher_code'],
                    department_id=department_id,
                    specialization_id=specialization_id
                )
                
                from app.services.auth_service import AuthService
                await AuthService.register(db, register_data)
                successful += 1
                
            except HTTPException as e:
                failed += 1
                errors.append({
                    "row": idx + 1,
                    "email": row.get('email', 'N/A'),
                    "error": e.detail
                })
            except Exception as e:
                failed += 1
                error_msg = str(e)
                
                # Parse Pydantic validation errors
                import re
                if 'validation error' in error_msg.lower():
                    parsed_errors = []
                    lines = error_msg.split('\n')
                    i = 0
                    while i < len(lines):
                        line = lines[i].strip()
                        
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            
                            # Extract "Value error, <message>"
                            if next_line.startswith('Value error,'):
                                message = re.sub(r'Value error,\s*', '', next_line)
                                message = re.sub(r'\s*\[type=.*?\].*$', '', message)
                                parsed_errors.append(message.strip())
                                i += 1
                            # Extract "String should have at least X characters"
                            elif 'String should have at least' in next_line:
                                match = re.search(r'String should have at least (\d+) characters', next_line)
                                if match:
                                    parsed_errors.append(f"Mật khẩu phải có ít nhất {match.group(1)} ký tự")
                                i += 1
                            # Extract "Field required"
                            elif next_line.startswith('Field required'):
                                field_name = line
                                field_map = {
                                    'email': 'Email',
                                    'password': 'Mật khẩu',
                                    'full_name': 'Họ tên',
                                    'teacher_code': 'Mã giáo viên'
                                }
                                parsed_errors.append(f"{field_map.get(field_name, field_name)} không được để trống")
                                i += 1
                        i += 1
                    
                    if parsed_errors:
                        error_msg = '; '.join(parsed_errors)
                # Extract meaningful error from exception
                elif "already registered" in error_msg.lower():
                    error_msg = f"Email {row.get('email')} đã được đăng ký"
                elif "already exists" in error_msg.lower():
                    if "teacher code" in error_msg.lower():
                        error_msg = f"Mã giáo viên {row.get('teacher_code')} đã tồn tại"
                    else:
                        error_msg = f"Email {row.get('email')} đã tồn tại trong hệ thống"
                
                errors.append({
                    "row": idx + 1,
                    "email": row.get('email', 'N/A'),
                    "error": error_msg
                })
        
        return CSVImportResult(
            success=failed == 0,
            total_attempted=len(rows),
            successful=successful,
            failed=failed,
            errors=errors,
            message=f"Thành công: {successful}/{len(rows)}. Thất bại: {failed}"
        )
