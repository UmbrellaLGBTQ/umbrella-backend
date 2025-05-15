from sqlalchemy.orm import Session
from sqlalchemy import or_, func, and_
from datetime import datetime, timedelta, date
from typing import List, Optional

from . import models, schemas, auth
from .models import RefreshToken, UserProfile

# -------------------- USER GETTERS --------------------

def get_user_by_id(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_phone(db: Session, phone_number: str):
    return db.query(models.User).filter(models.User.phone_number == phone_number).first()

def normalize_phone(phone: str) -> str:
    return phone.replace(" ", "") if phone else phone

def get_user_by_login_id(db: Session, login_id: str, password: str = None):
    from .auth import verify_password
    import logging

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("login")

    normalized_login = normalize_phone(login_id)

    users = db.query(models.User).filter(
        or_(
            models.User.username == login_id,
            models.User.phone_number.like(f"%{normalized_login[-10:]}")
        )
    ).all()

    logger.debug(f"[LOGIN] Found {len(users)} users for login_id={login_id}")

    for user in users:
        if user.username == login_id and verify_password(password, user.password_hash):
            return user

    matching_users = [
        user for user in users
        if normalize_phone(user.phone_number) == normalized_login and verify_password(password, user.password_hash)
    ]

    if not matching_users:
        return None

    matching_users.sort(key=lambda u: u.last_login_at or datetime.min, reverse=True)
    return matching_users[0]

def get_user_by_oauth_id(db: Session, provider: str, oauth_id: str):
    if provider == "google":
        return db.query(models.User).filter(models.User.google_id == oauth_id).first()
    elif provider == "apple":
        return db.query(models.User).filter(models.User.apple_id == oauth_id).first()
    return None

def get_user_profile(db: Session, user_id: int):
    return db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

def get_user_profile_by_username(db: Session, username: str):
    return db.query(UserProfile).filter(UserProfile.username == username).first()

# -------------------- USER CREATION --------------------

def create_user(db: Session, user_data: dict, hashed_password: str):
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

    display_name = f"{user_data['first_name']} {user_data['last_name']}"

    db_profile = UserProfile(
        user=db_user,
        username=user_data["username"],
        display_name=display_name,
        profile_image_url=user_data.get("profile_picture_url"),
        bio=None,
        location=user_data.get("location")  # <-- added support for location
    )

    db.add(db_user)
    db.add(db_profile)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_oauth_user(db: Session, provider: str, provider_id: str, first_name: str = None, last_name: str = None):
    db_user = models.User(
        first_name=first_name or "",
        last_name=last_name or "",
        username=f"{provider}_{provider_id}",
        phone_number=f"+00000000000",
        password_hash="",
        date_of_birth=datetime.now().date(),
        gender=models.Gender.PREFER_NOT_TO_SAY,
        sexuality=models.Sexuality.PREFER_NOT_TO_SAY,
        theme=models.Theme.VIOLET,
    )

    if provider == "google":
        db_user.google_id = provider_id
    elif provider == "apple":
        db_user.apple_id = provider_id

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# -------------------- USER UPDATES --------------------

def update_user_login(db: Session, user_id: int, login_type: models.LoginType):
    db_user = get_user_by_id(db, user_id)
    if db_user:
        db_user.last_login_type = login_type
        db_user.last_login_at = datetime.utcnow()
        db.commit()
        db.refresh(db_user)
    return db_user

def update_password(db: Session, user_id: int, new_password_hash: str):
    db_user = get_user_by_id(db, user_id)
    if db_user:
        db_user.password_hash = new_password_hash
        db.commit()
        db.refresh(db_user)
    return db_user

def update_user_theme(db: Session, user_id: int, theme: models.Theme):
    db_user = get_user_by_id(db, user_id)
    if db_user:
        db_user.theme = theme
        db.commit()
        db.refresh(db_user)
    return db_user

def update_user_profile(db: Session, profile_update: schemas.UserProfileUpdate, user_id: int):
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        return None

    for field, value in profile_update.dict(exclude_unset=True).items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile

def check_username_exists(db: Session, username: str) -> bool:
    return db.query(models.User).filter(models.User.username == username).first() is not None

# -------------------- CONNECTION CHECK --------------------

def check_users_connected(db: Session, user_id_1: int, user_id_2: int) -> bool:
    return db.query(models.Connection).filter(
        or_(
            and_(models.Connection.user_id1 == user_id_1, models.Connection.user_id2 == user_id_2),
            and_(models.Connection.user_id1 == user_id_2, models.Connection.user_id2 == user_id_1)
        )
    ).first() is not None

# -------------------- REFRESH TOKEN --------------------

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

def get_users_by_phone(db: Session, phone_number: str):
    """
    Return all users matching the exact phone number
    (without country code, since that's stored separately).
    """
    normalized = phone_number.strip().replace(" ", "")
    return db.query(models.User).filter(
        models.User.phone_number == normalized
    ).all()

