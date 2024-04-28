import os
import shutil
from fastapi import FastAPI, Depends, HTTPException, UploadFile, status, File
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uvicorn
from datetime import datetime, timedelta
from jose import jwt
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from passlib.context import CryptContext
from propelauth_fastapi import init_auth, User as PropelUser

DATABASE_URL = "postgresql://sgpostgres:dZTP$ICg5EZ2FsMA@SG-serene-couch-9596-5311-pgsql-master.servers.mongodirector.com/hackdavisfinal"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "lksajdflkjasdlkfjalksdjslkdfjalskdfjjfl"
ALGORITHM = "HS256"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    posts = relationship("TrashPost", back_populates="owner")

class TrashPost(Base):
    __tablename__ = "trash_posts"
    id = Column(Integer, primary_key=True, index=True)
    image_before_url = Column(String)
    image_after_url = Column(String, nullable=True)
    description = Column(String)
    is_cleaned = Column(Boolean, default=False)
    user_id = Column(String, ForeignKey("users.id"))
    owner = relationship("User", back_populates="posts")

Base.metadata.create_all(bind=engine)

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
class UserCreate(BaseModel):
    username: str
    password: str

class TrashPostCreate(BaseModel):
    image_url: str
    description: str

class TokenData(BaseModel):
    username: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TrashPostPublic(BaseModel):
    id: int
    image_before_url: str
    image_after_url: str
    description: str
    is_cleaned: bool
    user_id: int

    class Config:
        orm_mode = True

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(username: str, password: str, db: Session):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except jwt.JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

@app.get("/api/whoami")
async def root(current_user: PropelUser = Depends(get_current_user)):
    return {"user_id": f"{current_user.user_id}"}

@app.post("/users/", response_model=int)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    hashed_password = get_password_hash(user.password)
    db_user = User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user.id

@app.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    print(access_token)
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/trash-posts/", response_model=int)
def create_trash_post(image: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    file_path = f"public/{datetime.utcnow().isoformat()}_{image.filename}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    db_post = TrashPost(image_before_url=file_path, description="Hello World!!", owner=current_user)
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post.id

@app.put("/trash-posts/{post_id}/clean", response_model=bool)
def update_trash_post(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_post = db.query(TrashPost).filter(TrashPost.id == post_id).first()
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    db_post.is_cleaned = True
    db.commit()
    return True

@app.get("/trash-posts/", response_model=list[TrashPostPublic])
def read_trash_posts(is_cleaned: bool = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if is_cleaned is None:
        posts = db.query(TrashPost).all()
    else:
        posts = db.query(TrashPost).filter(TrashPost.is_cleaned == is_cleaned).all()
    return posts

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
