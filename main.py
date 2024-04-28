import os
import shutil
from fastapi import FastAPI, Depends, Form, HTTPException, UploadFile, status, File
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
from models import TrashPostPublic, TrashPostDetails, RewardDetails, PostCreationResponse
from gemini import GeminiAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.dialects.postgresql import JSON
import re
from fastapi.staticfiles import StaticFiles

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
    is_cleaned = Column(Boolean, default=False)
    details = Column(JSON)
    user_id = Column(String, nullable=False)
    reward_points = Column(Integer, default=0)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

class Rewards(Base):
    __tablename__ = "rewards"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False)
    username = Column(String, nullable=False)
    points = Column(Integer, default=0)

Base.metadata.create_all(bind=engine)

auth_url, api_key = os.getenv("AUTH_URL"), os.getenv("API_KEY")

auth = init_auth(auth_url, api_key)

app = FastAPI()

app.mount("/public", StaticFiles(directory="public"), name="public")


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

@app.post("/trash-posts/", response_model=PostCreationResponse)
def create_trash_post(latitude: float = Form(...), longitude: float = Form(...), image: UploadFile = File(...), db: Session = Depends(get_db), current_user: PropelUser = Depends(auth.require_user)):
    file_directory = "public"
    os.makedirs(file_directory, exist_ok=True)
    file_path = f"{file_directory}/{datetime.utcnow().isoformat()}_{image.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    gemini_api = GeminiAPI(file_path, latitude, longitude)
    gemini_response = gemini_api.generate_content()
    print("content:: ", gemini_response)

    db_post = TrashPost(image_before_url=file_path, user_id=current_user.user_id, details=gemini_response, latitude=latitude, longitude=longitude)
    result = update_or_create_user_points(current_user, gemini_response["reward"], db)
    print("Result: ", result)

    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return PostCreationResponse(post_id=db_post.id, gemini_response=gemini_response)

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
    print("Posts: ", posts, len(posts))
    # print("Current User: ", current_user.user_id, posts[0].id, posts[0].description, posts[0].details, posts[0].image_before_url, posts[0].is_cleaned, posts[0].reward_points)
    return posts 

def update_or_create_user_points(user: PropelUser, points_to_add, db):
    user_reward = db.query(Rewards).filter(Rewards.user_id == user.user_id).first()
    if user_reward:
        user_reward.points += points_to_add
    else:
        user_reward = Rewards(user_id=user.user_id, points=points_to_add, username=remove_email_extension(user.email))
        db.add(user_reward)
    db.commit()
    return "Points updated or user created with points"

def remove_email_extension(email):
    print("Email ", email)
    pattern = r"@\S+"
    cleaned_email = re.sub(pattern, "", email)
    return cleaned_email

@app.get("/trash-posts/{post_id}", response_model=TrashPostDetails)
def get_trash_post(post_id: int, db: Session = Depends(get_db), current_user: PropelUser = Depends(auth.require_user)):
    db_post = db.query(TrashPost).filter(TrashPost.id == post_id).first()
    print("current user: ", current_user.email)
    if db_post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return db_post

@app.get("/rewards/", response_model=List[RewardDetails])
def get_rewards(db: Session = Depends(get_db), current_user: PropelUser = Depends(auth.require_user)):
    rewards = db.query(Rewards).order_by(Rewards.points.desc()).all()
    return rewards

@app.get("/locations/", response_model=list)
def get_rewards(db: Session = Depends(get_db), current_user: PropelUser = Depends(auth.require_user)):
    coordinates = db.query(
        TrashPost.latitude, TrashPost.longitude
    ).distinct().all()
    return [{"latitude": lat, "longitude": lng} for lat, lng in coordinates]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
