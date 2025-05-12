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

def delete_previous_otps(db: Session, country_code: str, phone_number: str, purpose: str):
    """Delete all existing OTPs for the same phone number and purpose"""
    db.query(OTP).filter(
        OTP.country_code == country_code,
        OTP.phone_number == phone_number,
        OTP.purpose == purpose
    ).delete(synchronize_session=False)
    db.commit()

def create_otp(
    db: Session,
    purpose: str,
    user_id: int = None,
    phone_number: str = None,
    country_code: str = None
):
    """Create and save an OTP to the database"""
<<<<<<< HEAD
    
    if phone_number and not country_code:
        raise ValueError("country_code must be provided when phone_number is used.")

    otp_code = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)

    db_otp = OTP(
<<<<<<< HEAD
        user_id=user_id,
        country_code=country_code,
        phone_number=phone_number,
        email=email,
=======
    # Invalidate previous OTPs
    delete_previous_otps(db, country_code, phone_number, purpose)

    # Generate OTP code
    otp_code = generate_otp()

    # Calculate expiry time
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)

    # Create OTP record
    db_otp = OTP(
        user_id=user_id,
        country_code=country_code,
        phone_number=phone_number,
>>>>>>> f6f4ce1c55bf662e7afcd30593fecd4b727d9a52
        code=otp_code,
        purpose=purpose,
        expires_at=expires_at,
        attempts=0
<<<<<<< HEAD
=======
    user_id=user_id,
    country_code=country_code,  # ✅ Save it here
    phone_number=phone_number,
    # email=email,
    code=otp_code,
    purpose=purpose,
    expires_at=expires_at,
    attempts=0
>>>>>>> acd5347a47410be4c9648f82fab708dae09eef5f
=======
>>>>>>> f6f4ce1c55bf662e7afcd30593fecd4b727d9a52
    )

    db.add(db_otp)
    db.commit()
    db.refresh(db_otp)

<<<<<<< HEAD
    if phone_number:
        simulate_otp_delivery('phone', phone_number, otp_code, purpose)
<<<<<<< HEAD
    elif email:
        simulate_otp_delivery('email', email, otp_code, purpose)

=======
    # elif email:
    #     simulate_otp_delivery('email', email, otp_code, purpose)
        
>>>>>>> acd5347a47410be4c9648f82fab708dae09eef5f
=======
    # Simulate sending OTP
    if phone_number:
        simulate_otp_delivery('phone', phone_number, otp_code, purpose)

>>>>>>> f6f4ce1c55bf662e7afcd30593fecd4b727d9a52
    return db_otp


def verify_otp(
    db: Session,
    code: str,
    purpose: str,
    user_id: int = None,
    phone_number: str = None,
    country_code: str = None
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
    if phone_number and country_code:
        query = query.filter(
            OTP.phone_number == phone_number,
            OTP.country_code == country_code
        )

    db_otp = query.order_by(OTP.created_at.desc()).first()

    if not db_otp:
        return {"valid": False, "message": "No active OTP found or OTP expired"}

    # Increment attempt counter
    db_otp.attempts += 1

    if db_otp.attempts > MAX_OTP_ATTEMPTS:
        db.commit()
        return {"valid": False, "message": "Maximum verification attempts reached"}

    if db_otp.code != code:
        db.commit()
        return {"valid": False, "message": "Invalid OTP code"}

    db_otp.is_verified = True

    # Clean up expired OTPs
    db.query(OTP).filter(OTP.expires_at < datetime.utcnow()).delete()
    db.commit()

    return {"valid": True, "message": "OTP verified successfully"}

def invalidate_previous_otps(
    db: Session,
    purpose: str,
    user_id: int = None,
    phone_number: str = None,
    country_code: str = None
):
    """Invalidate all previous OTPs for the same purpose"""
    query = db.query(OTP).filter(
        OTP.is_verified == False,
        OTP.purpose == purpose
    )

    if user_id:
        query = query.filter(OTP.user_id == user_id)
    if phone_number and country_code:
        query = query.filter(
            OTP.phone_number == phone_number,
            OTP.country_code == country_code
        )

    query.update({"expires_at": datetime.utcnow() - timedelta(minutes=1)})
    db.commit()
