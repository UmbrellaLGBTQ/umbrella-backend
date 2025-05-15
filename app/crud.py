from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func, and_
from datetime import datetime, timedelta, date
from typing import List, Optional

from . import models, schemas, auth
from .models import RefreshToken, UserProfile, PostType

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

# -------------------- POST GETTERS --------------------

def get_user_posts(db: Session, user_id: int):
    return db.query(models.Post).filter(models.Post.user_id == user_id).order_by(models.Post.created_at.desc()).all()

def get_user_clips(db: Session, user_id: int):
    return db.query(models.Post).filter(
        models.Post.user_id == user_id,
        models.Post.type == PostType.CLIP
    ).order_by(models.Post.created_at.desc()).all()
    
def get_user_tags(db: Session, user_id: int):
    return db.query(models.Post).filter(
        models.Post.user_id == user_id,
        models.Post.type == PostType.TAG
    ).order_by(models.Post.created_at.desc()).all()

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
        location=user_data.get("location")
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
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == user_id).first()
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not profile or not user:
        return None
    
    if profile_update.username is not None:
        # Check if username already exists
        existing_user = db.query(models.User).filter(
            models.User.username == profile_update.username,
            models.User.id != user_id  # Exclude current user
        ).first()
        if existing_user:
            raise ValueError("Username already taken")

        user.username = profile_update.username
        profile.username = profile_update.username

    if profile_update.display_name is not None:
        profile.display_name = profile_update.display_name

    if profile_update.bio is not None:
        profile.bio = profile_update.bio

    if profile_update.profile_image_url is not None:
        profile.profile_image_url = profile_update.profile_image_url

    if profile_update.location is not None:
        profile.location = profile_update.location

    if profile_update.account_type is not None:
        user.account_type = profile_update.account_type  # ✅ Set on User model

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

# -------------------- POSTS --------------------

def get_posts_by_user_id(db: Session, user_id: int) -> List[models.Post]:
    return db.query(models.Post).filter(models.Post.user_id == user_id).order_by(models.Post.created_at.desc()).all()

def get_post_by_id(db: Session, post_id: int) -> Optional[models.Post]:
    return db.query(models.Post).filter(models.Post.id == post_id).first()

def create_post(db: Session, user_id: int, content: str, media_url: Optional[str] = None) -> models.Post:
    new_post = models.Post(
        user_id=user_id,
        content=content,
        media_url=media_url
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post

def delete_post(db: Session, post_id: int) -> bool:
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if post:
        db.delete(post)
        db.commit()
        return True
    return False

def count_user_posts(db: Session, user_id: int) -> int:
    return db.query(func.count(models.Post.id)).filter(models.Post.user_id == user_id).scalar()


def create_or_get_active_share_token(db: Session, user_id: int):
    existing = db.query(models.SharedProfileLink).filter(
        models.SharedProfileLink.user_id == user_id,
        models.SharedProfileLink.is_active == True
    ).first()

    if existing:
        return existing

    new_link = models.SharedProfileLink(user_id=user_id)
    db.add(new_link)
    db.commit()
    db.refresh(new_link)
    return new_link

def get_valid_shared_token(db: Session, token: str):
    return db.query(models.SharedProfileLink).filter(
        models.SharedProfileLink.token == token,
        models.SharedProfileLink.is_active == True
    ).first()

def create_connection_request(db: Session, requester_id: int, requestee_id: int) -> models.ConnectionRequest:
    existing = db.query(models.ConnectionRequest).filter(
        models.ConnectionRequest.requester_id == requester_id,
        models.ConnectionRequest.requestee_id == requestee_id
    ).first()

    if existing:
        return existing

    request = models.ConnectionRequest(
        requester_id=requester_id,
        requestee_id=requestee_id,
        status="pending"
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request

def accept_connection_request(db: Session, request_id: int, current_user_id: int):
    request = db.query(models.ConnectionRequest).filter_by(id=request_id).first()

    if not request or request.requestee_id != current_user_id:
        return False

    # Update status
    request.status = schemas.ConnectionStatus.ACCEPTED
    request.updated_at = datetime.utcnow()

    # Create reciprocal connection
    new_connection = models.Connection(
        user_id1=request.requester_id,
        user_id2=request.requestee_id
    )
    db.add(new_connection)
    db.commit()
    return True


def decline_connection_request(db: Session, request_id: int) -> bool:
    request = db.query(models.ConnectionRequest).filter(
        models.ConnectionRequest.id == request_id
    ).first()

    if request:
        request.status = "decline"
        request.updated_at = datetime.utcnow()
        db.commit()
        return True
    return False

def get_pending_requests_for_user(db: Session, user_id: int):
    return (
        db.query(models.ConnectionRequest)
        .options(joinedload(models.ConnectionRequest.requester).joinedload(models.User.profile))
        .filter(models.ConnectionRequest.requestee_id == user_id, models.ConnectionRequest.status == "pending")
        .all()
    )

def get_user_connections(db: Session, user_id: int) -> List[schemas.ConnectionUserPreviewResponse]:
    # Fetch all connections where the current user is involved
    connections = db.query(models.Connection).filter(
        or_(
            models.Connection.user_id1 == user_id,
            models.Connection.user_id2 == user_id
        )
    ).all()

    # Get the other user's ID from each connection
    connected_ids = [
        conn.user_id2 if conn.user_id1 == user_id else conn.user_id1
        for conn in connections
    ]

    # Join User and UserProfile to get the necessary preview fields
    users = db.query(
        models.User.username,
        models.UserProfile.display_name,
        models.UserProfile.profile_image_url
    ).join(models.UserProfile, models.User.id == models.UserProfile.user_id)\
     .filter(models.User.id.in_(connected_ids))\
     .all()

    # Convert results into the expected response schema
    return [
        schemas.ConnectionUserPreviewResponse(
            username=user.username,
            display_name=user.display_name,
            profile_image_url=user.profile_image_url
        )
        for user in users
    ]
    
def handle_connection_request_logic(db: Session, requester_username: str, requestee_username: str):
    from .models import ConnectionRequest, Connection, User, AccountType
    from datetime import datetime

    requester = db.query(User).filter(User.username == requester_username).first()
    requestee = db.query(User).filter(User.username == requestee_username).first()

    if not requester or not requestee:
        raise ValueError("Invalid requester or requestee username")

    # Check for existing connection
    existing = db.query(Connection).filter(
        ((Connection.user_id1 == requester.id) & (Connection.user_id2 == requestee.id)) |
        ((Connection.user_id1 == requestee.id) & (Connection.user_id2 == requester.id))
    ).first()

    if existing:
        raise ValueError("Users are already connected")

    # Check for pending request
    existing_request = db.query(ConnectionRequest).filter(
        ConnectionRequest.requester_id == requester.id,
        ConnectionRequest.requestee_id == requestee.id,
        ConnectionRequest.status == "pending"
    ).first()

    if existing_request:
        raise ValueError("Connection request already pending")

    # If requestee is public, create direct connection
    if requestee.account_type == AccountType.PUBLIC:
        new_connection = Connection(user_id1=requester.id, user_id2=requestee.id)
        db.add(new_connection)
        db.commit()
        return {"message": "Connected instantly (public profile)"}

    # Otherwise, send request
    new_request = ConnectionRequest(
        requester_id=requester.id,
        requestee_id=requestee.id,
        status="pending",
        created_at=datetime.utcnow()
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return new_request
