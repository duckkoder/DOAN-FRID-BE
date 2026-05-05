from typing import List, Optional
from pydantic import BaseModel, Field

class ClassDocumentItemResponse(BaseModel):
    """Schema for a single document item in a class."""
    document_id: str = Field(..., description="UUID of the document")
    title: str = Field(..., description="Title or original filename")
    file_url: Optional[str] = Field(None, description="URL to access or download the document")
    created_at: str = Field(..., description="ISO timestamp of when it was uploaded")
    is_private: bool = Field(..., description="True if document belongs exclusively to this class, False if it belongs to the whole course")

class ClassDocumentListResponse(BaseModel):
    """Schema for a list of class documents."""
    success: bool = True
    data: List[ClassDocumentItemResponse]
    message: str = "Documents retrieved successfully"
