from sqlalchemy import (
    Column, Integer, String, ForeignKey,
    Boolean, DateTime, Date, Enum, UniqueConstraint, Text
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
import enum
from datetime import datetime, timedelta, date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .database import Base
import uuid
from uuid import uuid4

# -------------------- ENUM DEFINITIONS --------------------

class Gender(enum.Enum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"

class Sexuality(enum.Enum):
    STRAIGHT = "straight"
    GAY = "gay"
    LESBIAN = "lesbian"
    BISEXUAL = "bisexual"
    PANSEXUAL = "pansexual"
    ASEXUAL = "asexual"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"

class Theme(str, enum.Enum):
    VIOLET = "violet"
    INDIGO = "indigo"
    BLUE = "blue"
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"

class LoginType(enum.Enum):
    PHONE = "phone"
    EMAIL = "email"
    GOOGLE = "google"
    APPLE = "apple"

class AccountType(str, enum.Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    ANONYMOUS = "anonymous"

class ConnectionStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class ReportCategory(str, enum.Enum):
    HARASSMENT = "harassment"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    SPAM = "spam"
    FAKE_ACCOUNT = "fake_account"
    OTHER = "other"

class PostType(str, enum.Enum):
    POST = "post"
    CLIP = "clip"
    TAG = "tag"
    
# -------------------- USER MODEL --------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    country_code = Column(String, nullable=False)
    phone_number = Column(String, index=True, nullable=False)
    password_hash = Column(String)
    date_of_birth = Column(Date)
    gender = Column(Enum(Gender))
    sexuality = Column(Enum(Sexuality))
    profile_picture_url = Column(String, nullable=True)

    theme = Column(
        SQLEnum(
            Theme,
            name="theme_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            native_enum=True,
            create_constraint=False,
            validate_strings=True
        ),
        nullable=False
    )

    google_id = Column(String, unique=True, nullable=True)
    apple_id = Column(String, unique=True, nullable=True)
    last_login_type = Column(Enum(LoginType), nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    account_type = Column(Enum(AccountType), default=AccountType.PUBLIC)

    otps = relationship("OTP", back_populates="user")
    profile = relationship("UserProfile", back_populates="user", uselist=False)

    sent_requests = relationship("ConnectionRequest", foreign_keys="ConnectionRequest.requester_id", back_populates="requester")
    received_requests = relationship("ConnectionRequest", foreign_keys="ConnectionRequest.requestee_id", back_populates="requestee")

    posts = relationship("Post", back_populates="user")

    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


# -------------------- OTP MODEL --------------------

class OTP(Base):
    __tablename__ = "otps"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    country_code = Column(String, nullable=False)
    phone_number = Column(String, index=True, nullable=False)
    code = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="otps")

# -------------------- REFRESH TOKEN MODEL --------------------

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token = Column(String, unique=True, nullable=False)
    is_valid = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", backref=backref("refresh_tokens", lazy="dynamic"))

# -------------------- FORGOT PASSWORD MODEL --------------------

class PasswordResetSession(Base):
    __tablename__ = "password_reset_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    identifier = Column(String, nullable=False)
    otp = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(minutes=10))

# -------------------- USER PROFILE MODEL --------------------

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    username = Column(String, unique=True, index=True)
    display_name = Column(String(50), nullable=False)
    bio = Column(String(250), nullable=True)
    profile_image_url = Column(String, nullable=True)
    location = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="profile")

# -------------------- CONNECTION REQUEST MODEL --------------------

class ConnectionRequest(Base):
    __tablename__ = "connection_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    requester_id = Column(Integer, ForeignKey("users.id"))
    requestee_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    requester = relationship("User", foreign_keys=[requester_id], back_populates="sent_requests")
    requestee = relationship("User", foreign_keys=[requestee_id], back_populates="received_requests")

    __table_args__ = (
        UniqueConstraint('requester_id', 'requestee_id', name='unique_connection_request'),
    )

# -------------------- CONNECTION MODEL --------------------

class Connection(Base):
    __tablename__ = "connections"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id1 = Column(Integer, ForeignKey("users.id"))
    user_id2 = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id1', 'user_id2', name='unique_connection'),
    )

# -------------------- POST MODEL --------------------

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    caption = Column(String, nullable=True)
    media_url = Column(String, nullable=False)
    type = Column(Enum(PostType), nullable=False)  # post, clip, tag
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="posts")

# -------------------- SHARED PROFILE MODEL --------------------

class SharedProfileToken(Base):
    __tablename__ = "shared_profile_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)  # Optional: for expiration
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

# -------------------- CHAT MODELS --------------------

class Chat(Base):
    __tablename__ = "chats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user1_id = Column(Integer, ForeignKey("users.id"))
    user2_id = Column(Integer, ForeignKey("users.id"))
    is_accepted = Column(Boolean, default=True)
    blocked_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user1 = relationship("User", foreign_keys=[user1_id])
    user2 = relationship("User", foreign_keys=[user2_id])
    
    # ✅ Proper backref
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")


class MessageTypeEnum(str, enum.Enum):
    text = "text"
    emoji = "emoji"
    image = "image"
    audio = "audio"


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid4)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id"))
    sender_id = Column(Integer, ForeignKey("users.id"))
    content = Column(String, nullable=True)
    media_url = Column(String, nullable=True)

    message_type = Column(
        SQLEnum(
            MessageTypeEnum,
            name="message_type_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls]
        ),
        default=MessageTypeEnum.text,
        nullable=False
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)
    is_deleted_for_all = Column(Boolean, default=False)

    # ✅ Relationship fix
    chat = relationship("Chat", back_populates="messages")
    reactions = relationship("Reaction", back_populates="message", cascade="all, delete-orphan")
    visibilities = relationship("MessageVisibility", back_populates="message", cascade="all, delete-orphan")


class Reaction(Base):
    __tablename__ = "reactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    emoji = Column(String, nullable=False)

    message = relationship("Message", back_populates="reactions")
    user = relationship("User")


class MessageVisibility(Base):
    __tablename__ = "message_visibility"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"))
    user_id = Column(Integer, ForeignKey("users.id"))

    message = relationship("Message", back_populates="visibilities")
    user = relationship("User")

