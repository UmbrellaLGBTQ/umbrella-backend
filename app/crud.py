from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
from typing import Optional

from . import models, schemas, auth

def get_user_by_id(db: Session, user_id: int):
    """Get user by ID"""
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    """Get user by username"""
    return db.query(models.User).filter(models.User.username == username).first()

# def get_user_by_email(db: Session, email: str):
#     """Get user by email"""
#     if not email:
#         return None
#     return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_phone(db: Session, phone_number: str):
    """Get user by phone number"""
    return db.query(models.User).filter(models.User.phone_number == phone_number).first()

def normalize_phone(phone: str) -> str:
    return phone.replace(" ", "") if phone else phone

def get_user_by_login_id(db: Session, login_id: str, password: str = None):
    from .auth import verify_password
    from datetime import datetime
    import logging

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("login")

    normalized_login = normalize_phone(login_id)

    users = db.query(models.User).filter(
        or_(
            models.User.username == login_id,
            models.User.phone_number.like(f"%{normalized_login[-10:]}")  # last 10 digits match
        )
    ).all()

    logger.debug(f"[LOGIN] Found {len(users)} users for login_id={login_id}")

    # Check for username match first
    for user in users:
        if user.username == login_id:
            if verify_password(password, user.password_hash):
                return user
            return None

    # Match phone with cleaned digits
    matching_users = []
    for user in users:
        if normalize_phone(user.phone_number) == normalized_login and verify_password(password, user.password_hash):
            matching_users.append(user)

    if not matching_users:
        return None

    matching_users.sort(key=lambda u: u.last_login_at or datetime.min, reverse=True)
    return matching_users[0]


def get_user_by_oauth_id(db: Session, provider: str, oauth_id: str):
    """Get user by OAuth provider ID"""
    if provider == "google":
        return db.query(models.User).filter(models.User.google_id == oauth_id).first()
    elif provider == "apple":
        return db.query(models.User).filter(models.User.apple_id == oauth_id).first()
    return None

from sqlalchemy.orm import Session
from . import models

def create_user(db: Session, user_data: dict, hashed_password: str):
    """Create a new user"""
    db_user = models.User(
        username=user_data["username"],
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
        country_code=user_data["country_code"],
        phone_number=user_data["phone_number"].replace(" ", ""),
        password_hash=hashed_password,
        date_of_birth=user_data["date_of_birth"],
        gender=user_data["gender"],
        sexuality=user_data["sexuality"],
        profile_picture_url=user_data.get("profile_picture_url"),
        theme=user_data["theme"],
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def create_oauth_user(
    db: Session, 
    # email: str, 
    provider: str, 
    provider_id: str, 
    first_name: str = None, 
    last_name: str = None
):
    """Create a new user from OAuth login (partial profile)"""
    db_user = models.User(
        # email=email,
        first_name=first_name or "",
        last_name=last_name or "",
        # Set temporary values for required fields
        username=f"{provider}_{provider_id}",  # Will be updated later
        phone_number=f"+00000000000",  # Will be updated later
        password_hash="",  # OAuth users don't need passwords
        date_of_birth=datetime.now().date(),  # Will be updated later
        gender=models.Gender.PREFER_NOT_TO_SAY,  # Will be updated later
        sexuality=models.Sexuality.PREFER_NOT_TO_SAY,  # Will be updated later
        theme=models.Theme.LIGHT,  # Default theme
    )
    
    # Set the appropriate OAuth ID
    if provider == "google":
        db_user.google_id = provider_id
    elif provider == "apple":
        db_user.apple_id = provider_id
        
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_login(db: Session, user_id: int, login_type: models.LoginType):
    """Update user's last login information"""
    db_user = get_user_by_id(db, user_id)
    if db_user:
        db_user.last_login_type = login_type
        db_user.last_login_at = datetime.utcnow()
        db.commit()
        db.refresh(db_user)
    return db_user

def update_user_profile(db: Session, user_id: int, user_data: dict):
    """Update user profile"""
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return None
        
    for key, value in user_data.items():
        setattr(db_user, key, value)
        
    db.commit()
    db.refresh(db_user)
    return db_user

def update_password(db: Session, user_id: int, new_password_hash: str):
    """Update user password"""
    db_user = get_user_by_id(db, user_id)
    if db_user:
        db_user.password_hash = new_password_hash
        db.commit()
        db.refresh(db_user)
    return db_user

def update_user_theme(db: Session, user_id: int, theme: models.Theme):
    """Update user theme preference"""
    db_user = get_user_by_id(db, user_id)
    if db_user:
        db_user.theme = theme
        db.commit()
        db.refresh(db_user)
    return db_user

def check_username_exists(db: Session, username: str) -> bool:
    """Check if username already exists"""
    return db.query(models.User).filter(models.User.username == username).first() is not None

# def check_phone_exists(db: Session, phone_number: str) -> bool:
#     """Check if phone number already exists"""
#     return db.query(models.User).filter(models.User.phone_number == phone_number).first() is not None


from .models import RefreshToken
from datetime import datetime, timedelta

def create_refresh_token(db: Session, user_id: int, token: str, expires_in_minutes: int):
    expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
    db_token = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token

def get_refresh_token(db: Session, token: str):
    return db.query(RefreshToken).filter(RefreshToken.token == token, RefreshToken.is_valid == True).first()

def revoke_refresh_token(db: Session, token: str):
    db_token = db.query(RefreshToken).filter(RefreshToken.token == token).first()
    if db_token:
        db_token.is_valid = False
        db.commit()