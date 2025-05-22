from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func, and_
from datetime import datetime, timedelta, date
from typing import List, Optional

from . import models, schemas, auth
from .models import RefreshToken, UserProfile, PostType
import uuid
from uuid import uuid4, UUID
from .schemas import CountryPhoneData, MessageResponse
from fastapi import HTTPException

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
    # Create the base user
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

    # Construct display name
    display_name = f"{user_data['first_name']} {user_data['last_name']}"

    # 🔍 Derive location using country code
    country_data = CountryPhoneData()
    location = country_data.get_country_data(str(user_data["country_code"])).get("country", None)

    # Create profile with auto-filled location
    db_profile = models.UserProfile(
        user=db_user,
        username=user_data["username"],
        display_name=display_name,
        profile_image_url=user_data.get("profile_picture_url"),
        bio=None,
        location=location
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

    updates = profile_update.dict(exclude_unset=True)

    if "username" in updates and updates["username"] != user.username:
        existing_user = db.query(models.User).filter(
            models.User.username == updates["username"],
            models.User.id != user_id
        ).first()
        if existing_user:
            raise ValueError("Username already taken")
        user.username = updates["username"]
        profile.username = updates["username"]

    if "display_name" in updates and updates["display_name"] != profile.display_name:
        profile.display_name = updates["display_name"]

    if "bio" in updates and updates["bio"] != profile.bio:
        profile.bio = updates["bio"]

    if "profile_image_url" in updates and updates["profile_image_url"] != profile.profile_image_url:
        profile.profile_image_url = updates["profile_image_url"]

    if "account_type" in updates and updates["account_type"] != user.account_type:
        user.account_type = updates["account_type"]

    # Set location if not already set
    if not profile.location:
        country_helper = CountryPhoneData()
        auto_location = country_helper.get_country_data(str(user.country_code)).get("country", None)
        profile.location = auto_location

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

def create_connection_request(db: Session, requester_id: int, requestee_id: int) -> bool:
    # Check if a pending or existing connection request already exists in either direction
    existing = db.query(models.ConnectionRequest).filter(
        models.ConnectionRequest.requester_id == requester_id,
        models.ConnectionRequest.requestee_id == requestee_id,
        models.ConnectionRequest.status == "pending"
    ).first()

    if existing:
        return False  # Indicate request already exists

    request = models.ConnectionRequest(
        requester_id=requester_id,
        requestee_id=requestee_id,
        status="pending"
    )
    db.add(request)
    db.commit()
    return True  # Indicate request created successfully


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

def get_users_by_phone(db: Session, phone_number: str):
    """
    Return all users matching the exact phone number
    (without country code, since that's stored separately).
    """
    normalized = phone_number.strip().replace(" ", "")
    return db.query(models.User).filter(
        models.User.phone_number == normalized
    ).all()

def create_or_get_chat(db: Session, user_id: int, target_user_id: int) -> models.Chat:
    if user_id == target_user_id:
        raise ValueError("Cannot create a chat with yourself")

    chat = db.query(models.Chat).filter(
        or_(
            and_(models.Chat.user1_id == user_id, models.Chat.user2_id == target_user_id),
            and_(models.Chat.user1_id == target_user_id, models.Chat.user2_id == user_id)
        )
    ).first()

    if chat:
        return chat

    # Create new chat
    new_chat = models.Chat(
        user1_id=user_id,
        user2_id=target_user_id,
        is_accepted=True,
        created_at=datetime.utcnow()
    )
    db.add(new_chat)
    db.commit()
    db.refresh(new_chat)
    return new_chat

# ------------------------ Chat Management ------------------------

def handle_chat_request(db: Session, chat_id: UUID, current_user_id: int, action: str):
    chat = db.query(models.Chat).filter_by(id=chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    if current_user_id not in [chat.user1_id, chat.user2_id]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    if action == "accept":
        chat.is_accepted = True
        chat.blocked_by = None
    elif action == "decline":
        db.delete(chat)
        db.commit()
        return {"message": "Chat request declined and removed."}
    elif action == "block":
        chat.blocked_by = current_user_id
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    db.commit()
    db.refresh(chat)
    return chat

def get_user_chats(db: Session, user_id: int):
    return db.query(models.Chat).filter(
        or_(
            models.Chat.user1_id == user_id,
            models.Chat.user2_id == user_id
        ),
        models.Chat.is_accepted == True,
        or_(
            models.Chat.blocked_by == None,
            models.Chat.blocked_by != user_id
        )
    ).order_by(models.Chat.created_at.desc()).all()

def send_message(db: Session, sender_id: int, data: schemas.MessageCreate):
    if data.chat_id:
        chat = db.query(models.Chat).filter_by(id=data.chat_id).first()
        if not chat or sender_id not in [chat.user1_id, chat.user2_id]:
            raise HTTPException(status_code=403, detail="Unauthorized or invalid chat")
        if chat.blocked_by and chat.blocked_by != sender_id:
            raise HTTPException(status_code=403, detail="You are blocked by the other user")

    elif data.group_id:
        member = db.query(models.GroupMember).filter_by(group_id=data.group_id, user_id=sender_id).first()
        if not member:
            raise HTTPException(status_code=403, detail="You are not a member of the group")

    else:
        raise HTTPException(status_code=400, detail="chat_id or group_id is required")

    message = models.Message(
        id=uuid4(),
        chat_id=data.chat_id,
        group_id=data.group_id,
        sender_id=sender_id,
        content=data.content,
        media_url=data.media_url,
        message_type=data.message_type,
        created_at=datetime.utcnow()
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def edit_message(db: Session, message_id: UUID, user_id: int, update_data: schemas.MessageEditRequest):
    message = db.query(models.Message).filter_by(id=message_id).first()
    if not message or message.sender_id != user_id:
        raise HTTPException(status_code=403, detail="Only the sender can edit the message")

    message.content = update_data.new_content
    message.edited_at = datetime.utcnow()
    db.commit()
    db.refresh(message)
    return message


def delete_message(db: Session, message_id: UUID, user_id: int, for_everyone: bool = False):
    message = db.query(models.Message).filter_by(id=message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if for_everyone:
        if message.sender_id != user_id:
            raise HTTPException(status_code=403, detail="Only sender can delete for everyone")
        message.is_deleted_for_all = True
        db.commit()
        return {"message": "Message deleted for everyone."}
    else:
        already_hidden = db.query(models.MessageVisibility).filter_by(message_id=message_id, user_id=user_id).first()
        if not already_hidden:
            db.add(models.MessageVisibility(message_id=message_id, user_id=user_id))
            db.commit()
        return {"message": "Message deleted for you only."}


def unsend_message(db: Session, message_id: UUID, user_id: int):
    message = db.query(models.Message).filter_by(id=message_id).first()
    if not message or message.sender_id != user_id:
        raise HTTPException(status_code=403, detail="Only sender can unsend")

    message.content = "[Message deleted]"
    message.media_url = None
    message.is_deleted_for_all = True
    db.commit()
    return {"message": "Message unsent."}


def react_to_message(db: Session, message_id: UUID, user_id: int, emoji: str):
    existing = db.query(models.Reaction).filter_by(message_id=message_id, user_id=user_id).first()
    if existing:
        existing.emoji = emoji
    else:
        db.add(models.Reaction(message_id=message_id, user_id=user_id, emoji=emoji))
    db.commit()
    return db.query(models.Reaction).filter_by(message_id=message_id, user_id=user_id).first()


def remove_reaction(db: Session, message_id: UUID, user_id: int):
    reaction = db.query(models.Reaction).filter_by(message_id=message_id, user_id=user_id).first()
    if reaction:
        db.delete(reaction)
        db.commit()
    return {"message": "Reaction removed"}


def get_filtered_messages(
    db: Session,
    chat_id: Optional[UUID],
    group_id: Optional[UUID],
    user_id: int,
    search: Optional[str] = None,
    type: Optional[str] = None
) -> List[schemas.MessageResponse]:
    subquery = db.query(models.MessageVisibility).filter(
        models.MessageVisibility.message_id == models.Message.id,
        models.MessageVisibility.user_id == user_id
    )

    if chat_id:
        query = db.query(models.Message).filter(
            models.Message.chat_id == chat_id,
            models.Message.is_deleted_for_all == False,
            ~subquery.exists()
        )
    elif group_id:
        query = db.query(models.Message).filter(
            models.Message.group_id == group_id,
            models.Message.is_deleted_for_all == False
        )
    else:
        raise HTTPException(status_code=400, detail="chat_id or group_id is required")

    if type:
        query = query.filter(models.Message.message_type == type)
    if search:
        query = query.filter(models.Message.content.ilike(f"%{search}%"))

    messages = query.order_by(models.Message.created_at.asc()).all()
    return [schemas.MessageResponse.model_validate(m, from_attributes=True) for m in messages]


def forward_message(
    db: Session,
    original_message_id: UUID,
    sender_id: int,
    target_chat_id: Optional[UUID] = None,
    target_group_id: Optional[UUID] = None
):
    original = db.query(models.Message).filter_by(id=original_message_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Original message not found")

    if target_chat_id:
        message = models.Message(
            chat_id=target_chat_id,
            sender_id=sender_id,
            content=original.content,
            media_url=original.media_url,
            message_type=original.message_type,
            created_at=datetime.utcnow()
        )
    elif target_group_id:
        member = db.query(models.GroupMember).filter_by(group_id=target_group_id, user_id=sender_id).first()
        if not member:
            raise HTTPException(status_code=403, detail="You are not a member of the group")
        message = models.Message(
            group_id=target_group_id,
            sender_id=sender_id,
            content=original.content,
            media_url=original.media_url,
            message_type=original.message_type,
            created_at=datetime.utcnow()
        )
    else:
        raise HTTPException(status_code=400, detail="Target chat or group ID required")

    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def handle_chat_user_action(db: Session, user_id: int, data: schemas.ChatUserActionRequest):
    # Stub logic - can implement mute/block logic here
    return {"message": f"Action '{data.action}' applied successfully"}

# Create Notification
def create_notification(db: Session, data: schemas.NotificationCreate):
    notification = models.Notification(
        id=uuid4(),
        recipient_id=data.recipient_id,
        type=data.type,
        title=data.title,
        message=data.message,
        link=data.link,
        created_at=datetime.utcnow(),
        is_read=False
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification

# Get Notifications for a User
def get_user_notifications(db: Session, user_id: int):
    return db.query(models.Notification).filter_by(recipient_id=user_id).order_by(models.Notification.created_at.desc()).all()

# Mark Notification as Read
def mark_as_read(db: Session, notification_id: UUID, user_id: int):
    notif = db.query(models.Notification).filter_by(id=notification_id, recipient_id=user_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"message": "Notification marked as read"}

# Mark All as Read
def mark_all_as_read(db: Session, user_id: int):
    db.query(models.Notification).filter_by(recipient_id=user_id, is_read=False).update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read"}

# Delete a Notification
def delete_notification(db: Session, notification_id: UUID, user_id: int):
    notif = db.query(models.Notification).filter_by(id=notification_id, recipient_id=user_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.delete(notif)
    db.commit()
    return {"message": "Notification deleted successfully"}
