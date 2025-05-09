from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import httpx
import json
from typing import Optional

from .. import schemas, crud, auth, models
from ..database import get_db

router = APIRouter(
    prefix="/oauth",
    tags=["oauth"],
    responses={404: {"description": "Not found"}},
)

async def verify_google_token(token: str) -> Optional[dict]:
    """Verify Google OAuth token and return user info"""
    try:
        async with httpx.AsyncClient() as client:
            # In production, use tokeninfo endpoint to validate the token
            response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
            )
            
            if response.status_code == 200:
                user_data = response.json()
                return {
                    "provider_id": user_data.get("sub"),
                    "email": user_data.get("email"),
                    "first_name": user_data.get("given_name"),
                    "last_name": user_data.get("family_name")
                }
            return None
    except Exception:
        return None

async def verify_apple_token(token: str) -> Optional[dict]:
    """Verify Apple OAuth token and return user info"""
    # Apple token verification is more complex in production
    # This is a simplified simulation
    try:
        # In a real implementation, you would:
        # 1. Decode the JWT
        # 2. Verify the signature using Apple's public key
        # 3. Validate claims (iss, aud, exp)
        
        # For simulation, we'll assume the token is valid and contains:
        user_data = {
            "provider_id": "apple_user_123",  # In production, extract from token
            "email": "user@example.com",      # In production, extract from token
            "first_name": "Apple",            # May not be provided by Apple
            "last_name": "User"               # May not be provided by Apple
        }
        return user_data
    except Exception:
        return None

@router.post("/login", response_model=schemas.Token)
async def oauth_login(
    oauth_request: schemas.OAuthLoginRequest,
    db: Session = Depends(get_db)
):
    """Login or signup with OAuth provider (Google/Apple)"""
    
    # Verify token with provider
    user_info = None
    if oauth_request.provider.lower() == "google":
        user_info = await verify_google_token(oauth_request.token)
    elif oauth_request.provider.lower() == "apple":
        user_info = await verify_apple_token(oauth_request.token)
    
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OAuth token"
        )
    
    # Check if user exists by provider ID
    user = crud.get_user_by_oauth_id(
        db, 
        oauth_request.provider.lower(), 
        user_info["provider_id"]
    )
    
    # If not found by provider ID, try email
    if not user and user_info.get("email"):
        user = crud.get_user_by_email(db, user_info["email"])
        
        # If found by email, link provider ID
        if user:
            if oauth_request.provider.lower() == "google":
                user.google_id = user_info["provider_id"]
            elif oauth_request.provider.lower() == "apple":
                user.apple_id = user_info["provider_id"]
            db.commit()
    
    # If user still not found, create new account (partial profile)
    if not user and user_info.get("email"):
        user = crud.create_oauth_user(
            db=db,
            email=user_info["email"],
            provider=oauth_request.provider.lower(),
            provider_id=user_info["provider_id"],
            first_name=user_info.get("first_name"),
            last_name=user_info.get("last_name")
        )
        
        # Return token with special flag indicating profile completion needed
        access_token = auth.create_access_token(
            data={"sub": str(user.id), "needs_profile": True}
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "needs_profile_completion": True
        }
    
    # Update last login type
    login_type = models.LoginType.GOOGLE if oauth_request.provider.lower() == "google" else models.LoginType.APPLE
    crud.update_user_login(db, user.id, login_type)
    
    # Create and return token
    access_token = auth.create_access_token(
        data={"sub": str(user.id)}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/complete-profile", response_model=schemas.UserResponse)
def complete_oauth_profile(
    profile_data: schemas.UserCreateRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Complete user profile after OAuth signup"""
    # Check if username is taken (except by current user)
    existing_user = crud.get_user_by_username(db, profile_data.username)
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Update user profile
    user_data = profile_data.dict(exclude={"password", "confirm_password"})
    
    # Hash password if provided
    if profile_data.password:
        hashed_password = auth.get_password_hash(profile_data.password)
        user_data["password_hash"] = hashed_password
    
    # Update profile
    updated_user = crud.update_user_profile(db, current_user.id, user_data)
    
    return updated_user