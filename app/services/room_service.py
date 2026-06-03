from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from app.models.room import Room
from app.schemas.room_schema import RoomCreate, RoomUpdate

class RoomService:
    @staticmethod
    def _normalize_room_name(name: str) -> str:
        return " ".join(name.strip().split())

    @staticmethod
    def _find_by_name(db: Session, name: str, exclude_id: int | None = None) -> Room | None:
        normalized = RoomService._normalize_room_name(name)
        query = db.query(Room).filter(func.lower(Room.name) == normalized.lower())
        if exclude_id is not None:
            query = query.filter(Room.id != exclude_id)
        return query.first()

    @staticmethod
    def get_rooms(db: Session, active_only: bool = False):
        query = db.query(Room)
        if active_only:
            query = query.filter(Room.status == "active")
        return query.order_by(Room.name.asc()).all()

    @staticmethod
    def create_room(db: Session, payload: RoomCreate) -> Room:
        room_name = RoomService._normalize_room_name(payload.name)
        if not room_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room name is required")

        existing_room = RoomService._find_by_name(db, room_name)
        if existing_room:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Room name '{room_name}' already exists"
            )
        
        room_data = payload.model_dump()
        room_data["name"] = room_name
        new_room = Room(**room_data)
        db.add(new_room)
        db.commit()
        db.refresh(new_room)
        return new_room

    @staticmethod
    def update_room(db: Session, room_id: int, payload: RoomUpdate) -> Room:
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
        
        update_data = payload.model_dump(exclude_unset=True)
        if update_data.get("name") is not None:
            update_data["name"] = RoomService._normalize_room_name(update_data["name"])
            if not update_data["name"]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room name is required")

        if update_data.get("name") and update_data["name"].lower() != room.name.lower():
            existing_room = RoomService._find_by_name(db, update_data["name"], exclude_id=room_id)
            if existing_room:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"Room name '{update_data['name']}' already exists"
                )
        
        for key, value in update_data.items():
            setattr(room, key, value)
            
        db.commit()
        db.refresh(room)
        return room

    @staticmethod
    def delete_room(db: Session, room_id: int):
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
        
        room.status = "inactive"
        db.commit()
        return {"success": True, "message": "Room deactivated successfully"}
