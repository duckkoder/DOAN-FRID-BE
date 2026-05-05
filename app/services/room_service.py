from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.room import Room
from app.schemas.room_schema import RoomCreate, RoomUpdate

class RoomService:
    @staticmethod
    def get_rooms(db: Session, active_only: bool = False):
        query = db.query(Room)
        if active_only:
            query = query.filter(Room.status == "active")
        return query.order_by(Room.name.asc()).all()

    @staticmethod
    def create_room(db: Session, payload: RoomCreate) -> Room:
        existing_room = db.query(Room).filter(Room.name == payload.name).first()
        if existing_room:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Room name '{payload.name}' already exists"
            )
        
        new_room = Room(**payload.model_dump())
        db.add(new_room)
        db.commit()
        db.refresh(new_room)
        return new_room

    @staticmethod
    def update_room(db: Session, room_id: int, payload: RoomUpdate) -> Room:
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
        
        if payload.name and payload.name != room.name:
            existing_room = db.query(Room).filter(Room.name == payload.name).first()
            if existing_room:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail=f"Room name '{payload.name}' already exists"
                )
        
        update_data = payload.model_dump(exclude_unset=True)
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
