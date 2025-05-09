from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from .. import schemas, crud, auth, models
from ..database import get_db

router = APIRouter(
    prefix="/login",
    tags=["login"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=schemas.Token)
def login_user(
    login_request: schemas.LoginRequest,
    db: Session = Depends(get_db)
):
    """Log in using username, email, or phone number"""
    # Find user by login ID (username, email, or phone)
    user = crud.get_user_by_login_id(db, login_request.login_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user has theme selected
    if not user.theme:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Theme selection required before login"
        )
    
    # Verify password
    if not auth.verify_password(login_request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Determine login type
    login_type = None
    if login_request.login_id == user.phone_number:
        login_type = models.LoginType.PHONE
    elif user.email and login_request.login_id == user.email:
        login_type = models.LoginType.EMAIL
    else:
        login_type = models.LoginType.PHONE  # Default to phone
    
    # Update last login info
    crud.update_user_login(db, user.id, login_type)
    
    # Create access token
    access_token = auth.create_access_token(
        data={"sub": str(user.id)}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/token", response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """OAuth2 compatible token login, get an access token for future requests"""
    # The username field from OAuth2PasswordRequestForm can contain username, email, or phone
    user = crud.get_user_by_login_id(db, form_data.username)
    
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user has theme selected
    if not user.theme:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Theme selection required before login"
        )
    
    # Determine login type and update
    login_type = models.LoginType.PHONE  # Default
    crud.update_user_login(db, user.id, login_type)
    
    # Create access token
    access_token = auth.create_access_token(
        data={"sub": str(user.id)}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.get("/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    """Get current authenticated user profile"""
    return current_user