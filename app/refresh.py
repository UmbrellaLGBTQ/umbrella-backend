from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from .database import get_db
from .models import User
from .auth import verify_refresh_token, create_access_token, create_refresh_token

router = APIRouter()

class RefreshRequest(BaseModel):
    """Schema for refresh token request"""
    refresh_token: str

class TokenResponse(BaseModel):
    """Schema for token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(refresh: schemas.RefreshRequest, db: Session = Depends(get_db)):
    db_token = crud.get_refresh_token(db, refresh.refresh_token)
    if not db_token or db_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Revoke old token (optional)
    crud.revoke_refresh_token(db, refresh.refresh_token)
    
    access_token = create_access_token({"sub": str(db_token.user_id)})
    new_refresh_token = create_refresh_token({"sub": str(db_token.user_id)}, db=db)
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }