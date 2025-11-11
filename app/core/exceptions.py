"""Custom exceptions for the application."""
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status


class ValidationError(HTTPException):
    """
    Custom validation error that returns response in same format as Pydantic validation.
    
    This ensures ALL validation errors (Pydantic + Business Logic) have the same format.
    
    Usage:
        raise ValidationError(
            field="day_of_week",
            message="Class does not have schedule on Monday",
            value="Monday"
        )
    
    Response format (same as Pydantic 422):
        {
            "detail": [
                {
                    "type": "value_error",
                    "loc": ["body", "field_name"],
                    "msg": "Error message",
                    "input": "input_value"
                }
            ]
        }
    """
    
    def __init__(
        self,
        field: str,
        message: str,
        value: Any = None,
        error_type: str = "value_error",
        loc_prefix: str = "body"
    ):
        detail = [
            {
                "type": error_type,
                "loc": [loc_prefix, field],
                "msg": message,
                "input": value
            }
        ]
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail
        )


class NotFoundException(HTTPException):
    """Exception raised when a resource is not found."""
    
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class BadRequestException(HTTPException):
    """Exception raised for bad requests."""
    
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class UnauthorizedException(HTTPException):
    """Exception raised for unauthorized access."""
    
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class ForbiddenException(HTTPException):
    """Exception raised for forbidden access."""
    
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ConflictException(HTTPException):
    """Exception raised for resource conflicts."""
    
    def __init__(self, detail: str = "Resource conflict"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)
