from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..auth import get_current_user
from ..s3 import upload_image_to_s3, delete_image_from_s3
from ..schemas import UserProfilePublicResponse, UserProfileResponse, CountryPhoneData
import uuid
from datetime import datetime, timedelta
import os

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")  # fallback for local dev

router = APIRouter(
    prefix="/api/profile",
    tags=["profile"],
    responses={404: {"description": "Not found"}}
)

@router.get("/by-username/{username}", response_model=UserProfilePublicResponse)
async def get_user_profile_by_username(
    username: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_user = crud.get_user_by_username(db, username)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_profile = crud.get_user_profile(db, db_user.id)
    if not db_profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Compute age
    age = db_user.age

    # Count total connections (user can be in either side)
    connection_count = db.query(models.Connection).filter(
        (models.Connection.user_id1 == db_user.id) |
        (models.Connection.user_id2 == db_user.id)
    ).count()

    # Count posts
    post_count = db.query(models.Post).filter(models.Post.user_id == db_user.id).count()

    # Compose base fields
    base_data = {
        "id": db_profile.id,
        "username": db_profile.username,
        "display_name": db_profile.display_name,
        "profile_image_url": db_profile.profile_image_url,
        "location": db_profile.location,
        "age": age,
        "connection_count": connection_count,
        "post_count": post_count
    }

    if db_user.id == current_user.id or crud.check_users_connected(db, current_user.id, db_user.id):
        return schemas.UserProfileResponse(
            **base_data,
            bio=db_profile.bio,
            user_id=db_profile.user_id,
            created_at=db_profile.created_at,
            updated_at=db_profile.updated_at,
        )

    return schemas.UserProfilePublicResponse(**base_data)

@router.put("/by-username/{username}", response_model=UserProfileResponse)
async def update_user_profile_by_username(
    profile_update: schemas.UserProfileUpdate,
    username: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_user = crud.get_user_by_username(db, username)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if db_user.id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    db_profile = crud.get_user_profile(db, db_user.id)

    if not db_profile:
        if not profile_update.username or not profile_update.display_name:
            raise HTTPException(status_code=400, detail="Username and display name are required")

        # ✅ Auto-fetch location from country code during creation only
        country_data = CountryPhoneData()
        location_name = country_data.get_country_data(str(db_user.country_code)).get("country", None)

        create_data = schemas.UserProfileCreate(
            username=profile_update.username,
            display_name=profile_update.display_name,
            bio=profile_update.bio,
            profile_image_url=profile_update.profile_image_url,
            location=location_name
        )
        return crud.create_user_profile(db, create_data, db_user.id)

    try:
        updated_profile = crud.update_user_profile(db, profile_update, db_user.id)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    return schemas.UserProfileResponse(
        id=updated_profile.id,
        username=updated_profile.username,
        display_name=updated_profile.display_name,
        profile_image_url=updated_profile.profile_image_url,
        age=db_user.age,
        location=updated_profile.location,
        bio=updated_profile.bio,
        user_id=updated_profile.user_id,
        created_at=updated_profile.created_at,
        updated_at=updated_profile.updated_at,
    )

@router.put("/upload-profile-image", response_model=UserProfileResponse, summary="Upload or change profile image")
async def upload_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    profile = crud.get_user_profile(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if profile.profile_image_url:
        try:
            delete_image_from_s3(profile.profile_image_url)
        except Exception:
            pass

    image_url = await upload_image_to_s3(file, folder=f"user-profile/{current_user.id}")
    profile.profile_image_url = image_url
    db.commit()
    db.refresh(profile)

    connection_count = db.query(models.Connection).filter(
        (models.Connection.user_id1 == current_user.id) |
        (models.Connection.user_id2 == current_user.id)
    ).count()
    post_count = db.query(models.Post).filter(models.Post.user_id == current_user.id).count()

    return schemas.UserProfileResponse(
        id=profile.id,
        username=profile.username,
        display_name=profile.display_name,
        profile_image_url=profile.profile_image_url,
        age=current_user.age,
        location=profile.location,
        bio=profile.bio,
        user_id=profile.user_id,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        connection_count=connection_count,
        post_count=post_count,
    )

@router.delete("/by-username/{username}/image", response_model=UserProfileResponse)
async def delete_profile_image_by_username(
    username: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_user = crud.get_user_by_username(db, username)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if db_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete")

    db_profile = crud.get_user_profile(db, db_user.id)
    if not db_profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if not db_profile.profile_image_url:
        raise HTTPException(status_code=400, detail="No profile image to delete")

    delete_image_from_s3(db_profile.profile_image_url)
    updated_profile = crud.update_profile_image_url(db, db_user.id, None)
    return schemas.UserProfileResponse(
        id=updated_profile.id,
        username=updated_profile.username,
        display_name=updated_profile.display_name,
        profile_image_url=updated_profile.profile_image_url,
        age=db_user.age,
        location=updated_profile.location,
        bio=updated_profile.bio,
        user_id=updated_profile.user_id,
        created_at=updated_profile.created_at,
        updated_at=updated_profile.updated_at,
    )

@router.post("/share-profile", response_model=schemas.SharedProfileResponse)
def generate_profile_share_link(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=7)

    share_token = models.SharedProfileToken(
        user_id=current_user.id,
        token=token,
        expires_at=expires_at
    )
    db.add(share_token)
    db.commit()
    db.refresh(share_token)

    share_url = f"{FRONTEND_URL}/view-profile/{token}"
    return {"token": token, "share_url": share_url}

@router.get("/view-profile/{token}", response_model=schemas.UserProfilePublicResponse)
def view_shared_profile(token: str, db: Session = Depends(get_db)):
    share = db.query(models.SharedProfileToken).filter_by(token=token, is_active=True).first()
    if not share or (share.expires_at and share.expires_at < datetime.utcnow()):
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    user = db.query(models.User).filter_by(id=share.user_id).first()
    profile = crud.get_user_profile(db, user.id)
    return schemas.UserProfilePublicResponse(
        id=profile.id,
        username=profile.username,
        display_name=profile.display_name,
        profile_image_url=profile.profile_image_url,
        location=profile.location,
        age=user.age
    )
