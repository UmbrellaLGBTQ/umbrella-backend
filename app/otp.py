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

def create_otp(db: Session, purpose: str, user_id: int = None, phone_number: str = None, country_code: str = None):
    """Create a new OTP and invalidate only existing OTPs of same user & purpose"""
    # Invalidate old OTPs for this user/purpose
    db.query(OTP).filter(
        OTP.user_id == user_id if user_id else OTP.phone_number == phone_number,
        OTP.purpose == purpose
    ).delete(synchronize_session=False)
    db.commit()

    otp_code = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)

    db_otp = OTP(
        user_id=user_id,
        phone_number=phone_number,
        country_code=country_code,
        code=otp_code,
        purpose=purpose,
        expires_at=expires_at,
        attempts=0,
        is_verified=False
    )

    db.add(db_otp)
    db.commit()
    db.refresh(db_otp)

    if phone_number:
        simulate_otp_delivery('phone', f"+{country_code}{phone_number}", otp_code, purpose)

    return db_otp

def verify_otp(db: Session, code: str, purpose: str, user_id: int = None, phone_number: str = None):
    """Verify OTP by user or phone"""
    query = db.query(OTP).filter(
        OTP.purpose == purpose,
        OTP.expires_at > datetime.utcnow(),
        OTP.is_verified == False
    )

    if user_id:
        query = query.filter(OTP.user_id == user_id)
    elif phone_number:
        query = query.filter(OTP.phone_number == phone_number)

    db_otp = query.order_by(OTP.created_at.desc()).first()

    if not db_otp:
        return {"valid": False, "message": "No valid OTP found"}

    db_otp.attempts += 1

    if db_otp.attempts > MAX_OTP_ATTEMPTS:
        db.commit()
        return {"valid": False, "message": "Maximum OTP attempts exceeded"}

    if db_otp.code != code:
        db.commit()
        return {"valid": False, "message": "Incorrect OTP"}

    db_otp.is_verified = True
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
            OTP.phone_number == phone_number
        )

    query.update({"expires_at": datetime.utcnow() - timedelta(minutes=1)})
    db.commit()