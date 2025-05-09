from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import date, datetime
import re
from .models import Gender, Sexuality, Theme, LoginType

# ---- Base Models ---- #
class OTPBase(BaseModel):
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    
    @validator('phone_number')
    def validate_phone(cls, v):
        if v is None:
            return v
        # Basic phone validation (E.164 format recommended)
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in E.164 format (e.g., +1234567890)')
        return v

class UserBase(BaseModel):
    username: str
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone_number: str
    date_of_birth: date
    gender: Gender
    sexuality: Sexuality
    theme: Theme
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username must contain only letters, numbers, and underscores')
        if len(v) < 3 or len(v) > 20:
            raise ValueError('Username must be between 3 and 20 characters')
        return v
    
    @validator('date_of_birth')
    def validate_age(cls, v):
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 13:
            raise ValueError('User must be at least 13 years old')
        return v

# ---- Request Models ---- #
class PhoneVerificationRequest(BaseModel):
    phone_number: str
    
    @validator('phone_number')
    def validate_phone(cls, v):
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in E.164 format (e.g., +1234567890)')
        return v

class OTPVerificationRequest(BaseModel):
    phone_number: str
    otp_code: str
    
    @validator('otp_code')
    def validate_otp(cls, v):
        if not re.match(r'^\d{6}$', v):
            raise ValueError('OTP must be a 6-digit number')
        return v

class UserCreateRequest(UserBase):
    password: str
    confirm_password: str
    profile_picture_url: Optional[str] = None
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v

class LoginRequest(BaseModel):
    login_id: str  # Can be phone, email, or username
    password: str

class OAuthLoginRequest(BaseModel):
    token: str
    provider: str  # "google" or "apple"

class ForgotPasswordRequest(BaseModel):
    login_id: str  # Can be phone, email, or username

class ResetPasswordRequest(BaseModel):
    login_id: str
    otp_code: str
    new_password: str
    confirm_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('confirm_password')
    def passwords_match(cls, v, values, **kwargs):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

class ThemeUpdateRequest(BaseModel):
    theme: Theme

# ---- Response Models ---- #
class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone_number: str
    date_of_birth: date
    gender: Gender
    sexuality: Sexuality
    theme: Theme
    profile_picture_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        orm_mode = True

class OTPResponse(BaseModel):
    message: str
    expires_at: datetime

class MessageResponse(BaseModel):
    message: str