from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from .. import schemas, crud, auth, otp, models
from ..database import get_db

router = APIRouter(
    prefix="/signup",
    tags=["signup"],
    responses={404: {"description": "Not found"}},
)

@router.post("/request-otp", response_model=schemas.OTPResponse)
def request_signup_otp(
    request: schemas.PhoneVerificationRequest,
    db: Session = Depends(get_db)
):
    """Request OTP for signup verification"""
    # Check if phone number is already registered
    # if crud.check_phone_exists(db, request.phone_number):
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Phone number is already registered"
    #     )
    
    # Invalidate any previous OTPs
    otp.invalidate_previous_otps(db, "signup", phone_number=request.phone_number)
    
    # Create new OTP
    new_otp = otp.create_otp(
    db=db,
    purpose="signup",
    phone_number=request.phone_number,
    country_code=request.country_code
    )
    
    return {
        "message": "OTP sent successfully",
        "expires_at": new_otp.expires_at
    }

@router.post("/verify-otp", response_model=schemas.MessageResponse)
def verify_signup_otp(
    request: schemas.OTPVerificationRequest,
    db: Session = Depends(get_db)
):
    """Verify OTP for signup process"""
    # Verify the OTP
    verification = otp.verify_otp(
        db=db,
        code=request.otp_code,
        purpose="signup",
        phone_number=request.phone_number
    )
    
    if not verification["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=verification["message"]
        )
    
    return {"message": "OTP verified successfully. Please complete your profile."}

@router.post("/complete-profile", response_model=schemas.UserResponse)
def complete_signup(
    user_data: schemas.UserCreateRequest,
    db: Session = Depends(get_db)
):
    """Complete user profile after OTP verification"""
    # Check if username is taken
    if crud.check_username_exists(db, user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Updated query: fetch only the latest verified OTP
    query = db.query(models.OTP).filter(
        models.OTP.phone_number == user_data.phone_number,
        models.OTP.purpose == "signup",
        models.OTP.is_verified == True,
        models.OTP.expires_at > datetime.utcnow()
    ).order_by(models.OTP.created_at.desc())

    verified_otp = query.first()

    if not verified_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone verification required before profile completion"
        )

    # ✅ Invalidate this OTP after use
    db.delete(verified_otp)
    db.commit()

    
    # Hash the password
    hashed_password = auth.get_password_hash(user_data.password)
    
    # Create user
    user = crud.create_user(db, user_data, hashed_password)
    
    # ✅ Invalidate OTPs after successful signup
    otp.invalidate_previous_otps(db, purpose="signup", phone_number=user_data.phone_number)

    return user