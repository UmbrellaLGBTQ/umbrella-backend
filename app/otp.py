import random
import string
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

from .models import OTP
from .utils import simulate_otp_delivery

# Load environment variables
load_dotenv()

# OTP configuration
OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "5"))
MAX_OTP_ATTEMPTS = 3
OTP_LENGTH = 6

def generate_otp(length=OTP_LENGTH):
    """Generate a numeric OTP of specified length"""
    return ''.join(random.choices(string.digits, k=length))

def create_otp(
    db: Session, 
    purpose: str, 
    user_id: int = None, 
    phone_number: str = None, 
    # email: str = None
):
    """Create and save an OTP to the database"""
    # Generate OTP code
    otp_code = generate_otp()
    
    # Calculate expiry time
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    
    # Create OTP record
    db_otp = OTP(
        user_id=user_id,
        phone_number=phone_number,
        # email=email,
        code=otp_code,
        purpose=purpose,
        expires_at=expires_at,
        attempts=0
    )
    
    db.add(db_otp)
    db.commit()
    db.refresh(db_otp)
    
    # Simulate sending OTP
    if phone_number:
        simulate_otp_delivery('phone', phone_number, otp_code, purpose)
    # elif email:
    #     simulate_otp_delivery('email', email, otp_code, purpose)
        
    return db_otp

def verify_otp(
    db: Session, 
    code: str, 
    purpose: str, 
    user_id: int = None, 
    phone_number: str = None, 
    # email: str = None
):
    """Verify an OTP code"""
    # Find the most recent active OTP
    query = db.query(OTP).filter(
        OTP.is_verified == False,
        OTP.purpose == purpose,
        OTP.expires_at > datetime.utcnow()
    )
    
    if user_id:
        query = query.filter(OTP.user_id == user_id)
    if phone_number:
        query = query.filter(OTP.phone_number == phone_number)
    # if email:
    #     query = query.filter(OTP.email == email)
        
    db_otp = query.order_by(OTP.created_at.desc()).first()
    
    if not db_otp:
        return {"valid": False, "message": "No active OTP found or OTP expired"}
    
    # Increment attempt counter
    db_otp.attempts += 1
    
    # Check if max attempts reached
    if db_otp.attempts > MAX_OTP_ATTEMPTS:
        db.commit()
        return {"valid": False, "message": "Maximum verification attempts reached"}
    
    # Verify the code
    if db_otp.code != code:
        db.commit()
        return {"valid": False, "message": "Invalid OTP code"}
    
    # Mark as verified if code matches
    db_otp.is_verified = True
    db.commit()
    
    return {"valid": True, "message": "OTP verified successfully"}

def invalidate_previous_otps(
    db: Session, 
    purpose: str, 
    user_id: int = None, 
    phone_number: str = None, 
    # email: str = None
):
    """Invalidate all previous OTPs for the same purpose"""
    query = db.query(OTP).filter(
        OTP.is_verified == False,
        OTP.purpose == purpose
    )
    
    if user_id:
        query = query.filter(OTP.user_id == user_id)
    if phone_number:
        query = query.filter(OTP.phone_number == phone_number)
    # if email:
    #     query = query.filter(OTP.email == email)
        
    # Update all matching OTPs to be expired
    query.update({"expires_at": datetime.utcnow() - timedelta(minutes=1)})
    db.commit()