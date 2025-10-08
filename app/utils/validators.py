"""Custom validators for data validation."""
import re
from typing import Optional


def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email string to validate
        
    Returns:
        True if valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
    """
    Validate password strength.
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    return True, None


def validate_phone_number(phone: str) -> bool:
    """
    Validate phone number format (basic validation).
    
    Args:
        phone: Phone number to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Basic validation: 10-15 digits, may start with +
    pattern = r'^\+?[0-9]{10,15}$'
    return re.match(pattern, phone.replace(' ', '').replace('-', '')) is not None


def validate_student_code(code: str) -> bool:
    """
    Validate student code format.
    
    Args:
        code: Student code to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Example: Student code should be alphanumeric, 6-20 characters
    pattern = r'^[A-Za-z0-9]{6,20}$'
    return re.match(pattern, code) is not None
