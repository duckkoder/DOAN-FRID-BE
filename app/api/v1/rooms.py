from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.room_schema import RoomCreate, RoomUpdate, RoomResponse
from app.services.room_service import RoomService

router = APIRouter(prefix="/admin/rooms", tags=["Room Management"])

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to check if user is admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin role required."
        )
    return current_user

@router.get("", response_model=List[RoomResponse])
def get_rooms(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of rooms. Teachers can only see active rooms if active_only=True."""
    return RoomService.get_rooms(db, active_only)

@router.post("", response_model=RoomResponse)
def create_room(
    payload: RoomCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Create a new room (Admin only)."""
    return RoomService.create_room(db, payload)

@router.put("/{room_id}", response_model=RoomResponse)
def update_room(
    room_id: int,
    payload: RoomUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update a room (Admin only)."""
    return RoomService.update_room(db, room_id, payload)

@router.delete("/{room_id}")
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete a room (Admin only). Soft delete by setting status to inactive."""
    return RoomService.delete_room(db, room_id)
