from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from pwdlib import PasswordHash
import jwt
from jwt.exceptions import InvalidTokenError
from datetime import datetime, timedelta, timezone
from dotenv import dotenv_values

from app import models, schemas
from app.database import get_db

config = dotenv_values(".env")

router = APIRouter()

# Security Configurations
password_hash = PasswordHash.recommended()
SECRET_KEY = config["SECRET_KEY"]
ALGORITHM = "HS256"

oauth2_theme = OAuth2PasswordBearer(tokenUrl="token")


def get_password_hash(password):
  return password_hash.hash(password)


def verify_password(plain_password, hashed_password):
  return password_hash.verify(plain_password, hashed_password)


def get_current_user(token: str = Depends(oauth2_theme), db: Session = Depends(get_db)):
  credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate", "Bearer"},
  )

  try:
    # Decoded token
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    username: str = payload.get("sub")
    if not username:
      raise credentials_exception
  except InvalidTokenError:
    raise credentials_exception
  
  # Check if user still exists in the database
  stmt = select(models.User).where(models.User.username == username)
  user = db.execute(stmt).scalar_one_or_none()

  if not user:
    raise credentials_exception
  
  return user


# Route 1: Register a new user
@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
  stmt = select(models.User).where(models.User.username == user.user_name)
  db_user = db.execute(stmt).scalar_one_or_none()

  if db_user:
    raise HTTPException(status_code=400, detail="Username already registered")
  
  hashed_password = get_password_hash(user.password)
  new_user = models.User(username=user.user_name, hashed_password=hashed_password)

  db.add(new_user)
  db.commit()
  db.refresh(new_user)
  return new_user


# Route 2: Login and get JWT
@router.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
  stmt = select(models.User).where(models.User.username == form_data.username)
  user = db.execute(stmt).scalar_one_or_none()

  if not user or not verify_password(form_data.password, user.hashed_password):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Incorrect username or password",
      headers={"WWW-Authenticate": "Bearer"},
    )
  
  # Generate the JWT
  expire = datetime.now(timezone.utc) + timedelta(minutes=30)
  to_encode = {"sub": user.username, "exp": expire}
  encoded_jwt = jwt.encode(payload=to_encode, key=SECRET_KEY, algorithm=ALGORITHM)

  return {"access_token": encoded_jwt, "token_type": "bearer"}
  

# Route 3: Protected Route Test
@router.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
  return current_user
