from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import schemas, crud, auth, otp
from ..database import get_db

router = APIRouter(
    prefix="/password",
    tags=["password"],
    responses={404: {"description": "Not found"}},
)

@router.post("/forgot", response_model=schemas.OTPResponse)
def forgot_password(
    request: schemas.ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """Initiate password reset by sending OTP"""
    user = crud.get_user_by_login_id(db, request.login_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    otp.invalidate_previous_otps(db, "password_reset", user_id=user.id)

    contact_method = None
    contact_value = None

    if user.phone_number:
        contact_method = "phone_number"
        contact_value = user.phone_number
    elif user.email:
        contact_method = "email"
        contact_value = user.email
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No contact method available for password reset"
        )

    # ✅ Now include country_code only if phone is used
    otp_kwargs = {
        "db": db,
        "purpose": "password_reset",
        "user_id": user.id,
        contact_method: contact_value
    }

    if contact_method == "phone_number":
        otp_kwargs["country_code"] = request.country_code

    new_otp = otp.create_otp(**otp_kwargs)

    return {
        "message": f"OTP sent to your {contact_method.replace('_', ' ')}",
        "expires_at": new_otp.expires_at
    }

@router.post("/reset", response_model=schemas.MessageResponse)
def reset_password(
    request: schemas.ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset password using OTP"""
    # Find the user by login ID
    user = crud.get_user_by_login_id(db, request.login_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify OTP
    verification = otp.verify_otp(
        db=db,
        code=request.otp_code,
        purpose="password_reset",
        user_id=user.id
    )
    
    if not verification["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=verification["message"]
        )
    
    # Hash the new password
    hashed_password = auth.get_password_hash(request.new_password)
    
    # Update the password
    crud.update_password(db, user.id, hashed_password)
    
    return {"message": "Password reset successful"}