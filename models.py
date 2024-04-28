from pydantic import BaseModel

class TrashPostCreate(BaseModel):
    image_url: str
    description: str

class TrashPostPublic(BaseModel):
    id: int
    image_before_url: str
    description: str
    is_cleaned: bool

    class Config:
        orm_mode = True
