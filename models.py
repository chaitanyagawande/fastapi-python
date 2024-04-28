from typing import Optional
from pydantic import BaseModel

class TrashPostCreate(BaseModel):
    image_url: str
    description: str

class TrashPostPublic(BaseModel):
    id: int
    image_before_url: str
    is_cleaned: bool
    details: dict
    user_id: str
    reward_points: int

    class Config:
        orm_mode = True

class TrashPostDetails(BaseModel):
    id: int
    image_before_url: str
    is_cleaned: bool
    details: dict
    class Config:
        orm_mode = True

class PostCreationResponse(BaseModel):
    post_id: int
    gemini_response: dict  # Assuming gemini_response is a dictionary

