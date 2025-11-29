from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class ApplicationCreate(BaseModel):
    name: str

class ApplicationResponse(BaseModel):
    id: UUID
    name: str
    api_key: str
    created_at: datetime

    class Config:
        from_attributes = True
