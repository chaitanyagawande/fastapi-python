import os
import shutil
from fastapi import FastAPI, Depends, HTTPException, UploadFile, status, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
from propelauth_fastapi import init_auth, User as PropelUser
from typing import List
from dotenv import load_dotenv
import uvicorn
from models import TrashPostPublic, TrashPostCreate
from gemini import GeminiAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "lksajdflkjasdlkfjalksdjslkdfjalskdfjjfl"
ALGORITHM = "HS256"

class TrashPost(Base):
    __tablename__ = "trash_posts"
    id = Column(Integer, primary_key=True, index=True)
    image_before_url = Column(String)
    image_after_url = Column(String, nullable=True)
    description = Column(String)
    is_cleaned = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

auth_url, api_key = os.getenv("AUTH_URL"), os.getenv("API_KEY")

auth = init_auth(auth_url, api_key)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/trash-posts/", response_model=int)
def create_trash_post(image: UploadFile = File(...), db: Session = Depends(get_db), current_user: PropelUser = Depends(auth.require_user)):
    file_path = f"public/{datetime.utcnow().isoformat()}_{image.filename}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    gemini_api = GeminiAPI(file_path)
    print("content:: ", gemini_api.generate_content())

    db_post = TrashPost(image_before_url=file_path, description="Hello World!!")
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post.id

@app.put("/trash-posts/{post_id}/clean", response_model=bool)
def update_trash_post(post_id: int, db: Session = Depends(get_db), current_user: PropelUser = Depends(auth.require_user)):
    db_post = db.query(TrashPost).filter(TrashPost.id == post_id).first()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    db_post.is_cleaned = True
    db.commit()
    return True

@app.get("/trash-posts/", response_model=List[TrashPostPublic])
def read_trash_posts(is_cleaned: bool = None, db: Session = Depends(get_db), current_user: PropelUser = Depends(auth.require_user)):
    if is_cleaned is None:
        posts = db.query(TrashPost).all()
    else:
        posts = db.query(TrashPost).filter(TrashPost.is_cleaned == is_cleaned).all()
    return posts 

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
