from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os
import secrets

from .database import get_db
from .models import User
from .schemas import Token
from . import crud

# Load environment variables
load_dotenv()

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "1440"))

# Refresh token configuration
# Auto-generating refresh secret key if not provided
def get_refresh_secret_key():
    """Generate or retrieve refresh token secret key"""
    refresh_secret = os.getenv("JWT_REFRESH_SECRET")
    
    if not refresh_secret:
        # Generate a secure random key (32 bytes = 256 bits)
        refresh_secret = secrets.token_urlsafe(32)
        print("WARNING: JWT_REFRESH_SECRET not found in environment variables. "
              "A random secret has been generated for this session.")
        print("For production, set JWT_REFRESH_SECRET in your environment variables.")
    
    return refresh_secret

REFRESH_SECRET_KEY = get_refresh_secret_key()
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_EXPIRATION_DAYS", "7"))

# Set up password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login/token")

def verify_password(plain_password, hashed_password):
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Generate password hash"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a new JWT token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt

def create_refresh_token(data: dict, db: Session):
    """Create and store a refresh token in the database"""
    expires = timedelta(days=7)
    expire_time = datetime.utcnow() + expires
    
    to_encode = data.copy()
    to_encode.update({
        "exp": expire_time,
        "token_type": "refresh"
    })
    
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    # Save to DB using your CRUD method
    crud.create_refresh_token(
        db=db,
        user_id=int(data["sub"]),
        token=token,
        expires_in_minutes=60 * 24 * 7  # 7 days in minutes
    )
    
    return token


def verify_refresh_token(token: str):
    """Verify a refresh token and return the user ID"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the JWT token
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        
        # Check if it's actually a refresh token
        token_type = payload.get("token_type")
        if token_type != "refresh":
            raise credentials_exception
            
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
            
        return user_id
    except JWTError:
        raise credentials_exception

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Get the current user from a JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Get the user from the database
    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )
    
    return user

# Optional function for routes that need an authenticated user
def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
):
    """Get the current user if authenticated, return None otherwise"""
    if not token:
        return None
    
    try:
        # Decode the JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            return None
            
        # Get the user from the database
        user = db.query(User).filter(User.id == user_id).first()
        
        if user is None or not user.is_active:
            return None
            
        return user
    except JWTError:
        return None