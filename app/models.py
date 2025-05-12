from sqlalchemy import (
    Column, Integer, String, ForeignKey, 
    Boolean, DateTime, Date, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .database import Base
from datetime import datetime
from sqlalchemy.orm import backref


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

class Theme(enum.Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"
    HIGH_CONTRAST = "high_contrast"

class LoginType(enum.Enum):
    PHONE = "phone"
    EMAIL = "email"
    GOOGLE = "google"
    APPLE = "apple"

class User(Base):
    """User account information"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    # email = Column(String, unique=True, nullable=True)
    country_code = Column(String, nullable=False)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String)
    date_of_birth = Column(Date)
    gender = Column(Enum(Gender))
    sexuality = Column(Enum(Sexuality))
    profile_picture_url = Column(String, nullable=True)
    theme = Column(Enum(Theme), nullable=False)
    google_id = Column(String, unique=True, nullable=True)
    apple_id = Column(String, unique=True, nullable=True)
    last_login_type = Column(Enum(LoginType), nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    otps = relationship("OTP", back_populates="user")
    
class OTP(Base):
    """One-time passwords for verification"""
    __tablename__ = "otps"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    country_code = Column(String, nullable=False)
    phone_number = Column(String, index=True, nullable=False)
    # email = Column(String, nullable=True)
    code = Column(String, nullable=False)
    purpose = Column(String, nullable=False)  # signup, login, password_reset
    is_verified = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="otps")
    
class RefreshToken(Base):
    """Refresh token storage"""
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    token = Column(String, unique=True, nullable=False)
    is_valid = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    # Relationship with backref instead of back_populates
    user = relationship("User", backref=backref("refresh_tokens", lazy="dynamic"))
