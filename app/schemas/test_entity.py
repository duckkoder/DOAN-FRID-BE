from pydantic import BaseModel

class TestEntityCreate(BaseModel):
    name: str
    description: str | None = None

class TestEntityResponse(BaseModel):
    id: int
    name: str
    description: str | None = None

    class Config:
        orm_mode = True