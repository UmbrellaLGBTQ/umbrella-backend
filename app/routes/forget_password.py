from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from .. import schemas, crud, auth, otp, models
from ..database import get_db

router = APIRouter(
    prefix="/password",
    tags=["password"],
    responses={404: {"description": "Not found"}},
)

@router.post("/forgot", response_model=schemas.OTPResponse)
def forgot_password(request: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    login_id = request.login_id.strip()

    if login_id.isdigit():
        users = crud.get_users_by_phone(db, login_id)
        if not users:
            raise HTTPException(status_code=404, detail="No users linked to this phone number")

        # ✅ Just use the first user's country code (assume consistent)
        first_user = users[0]
        otp.invalidate_previous_otps(db, "password_reset", phone_number=login_id, country_code=first_user.country_code)
        new_otp = otp.create_otp(
            db=db,
            purpose="password_reset",
            phone_number=login_id,
            country_code=first_user.country_code
        )

        return {
            "message": "OTP sent",
            "expires_at": new_otp.expires_at
        }

    else:
        user = crud.get_user_by_username(db, login_id)
        if not user:
            raise HTTPException(status_code=404, detail="Username not found")

        otp.invalidate_previous_otps(db, "password_reset", user_id=user.id)
        new_otp = otp.create_otp(
            db=db,
            purpose="password_reset",
            phone_number=user.phone_number,
            user_id=user.id,
            country_code=user.country_code
        )

        return {
            "message": "OTP sent",
            "expires_at": new_otp.expires_at
        }


@router.post("/verify-otp-and-list-users", response_model=schemas.UsernameListResponse)
def verify_otp_and_list_users(
    request: schemas.PasswordOTPVerificationRequest, 
    db: Session = Depends(get_db)
):
    # Get the latest verified OTP that hasn't expired
    latest_otp = db.query(models.OTP).filter(
        models.OTP.purpose == "password_reset",
        models.OTP.expires_at > datetime.utcnow()
    ).order_by(models.OTP.created_at.desc()).first()

    if not latest_otp:
        raise HTTPException(status_code=404, detail="No OTP found")

    verification = otp.verify_otp(
        db=db,
        code=request.otp_code,
        purpose="password_reset",
        phone_number=latest_otp.phone_number,
        user_id=latest_otp.user_id  # if available
    )

    if not verification["valid"]:
        raise HTTPException(status_code=400, detail=verification["message"])

    # Get users associated with this phone number
    users = crud.get_users_by_phone(db, latest_otp.phone_number)
    if not users:
        raise HTTPException(status_code=404, detail="No user found")

    db.query(models.OTP).filter(
        models.OTP.phone_number == latest_otp.phone_number,
        models.OTP.purpose == "password_reset",
        models.OTP.expires_at > datetime.utcnow()
    ).update({models.OTP.is_verified: True}, synchronize_session=False)
    db.commit()


    return {"usernames": [u.username for u in users]}


@router.post("/reset", response_model=schemas.MessageResponse)
def reset_password(request: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, request.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp_verified = db.query(models.OTP).filter(
        models.OTP.phone_number == user.phone_number,
        models.OTP.purpose == "password_reset",
        models.OTP.is_verified == True,
        models.OTP.expires_at > datetime.utcnow()
    ).first()

    if not otp_verified:
        raise HTTPException(status_code=400, detail="OTP not verified for this user")

    # Optional: invalidate OTP after use
    db.delete(otp_verified)
    db.commit()

    hashed_pw = auth.get_password_hash(request.new_password)
    crud.update_password(db, user.id, hashed_pw)

    return {"message": "Password reset successful"}
