from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..auth import get_current_user
from ..s3 import upload_image_to_s3, delete_image_from_s3
from ..schemas import UserProfilePublicResponse, UserProfileResponse

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
    """
    Get user profile by username.
    Shows full profile only if user is self or connected.
    """
    db_user = crud.get_user_by_username(db, username)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_profile = crud.get_user_profile(db, db_user.id)
    if not db_profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    base_data = {
        "id": db_profile.id,
        "username": db_profile.username,
        "display_name": db_profile.display_name,
        "profile_image_url": db_profile.profile_image_url,
        "age": db_user.age or 0,
    }

    # Return full profile if self or connected
    if db_user.id == current_user.id or crud.check_users_connected(db, current_user.id, db_user.id):
        return UserProfileResponse(
            **base_data,
            bio=db_profile.bio,
            user_id=db_profile.user_id,
            created_at=db_profile.created_at,
            updated_at=db_profile.updated_at
        )

    # Else return public profile
    return UserProfilePublicResponse(**base_data)


@router.put("/by-username/{username}", response_model=UserProfileResponse)
async def update_user_profile_by_username(
    profile_update: schemas.UserProfileUpdate,
    username: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user profile by username.
    Only the profile owner can update.
    """
    db_user = crud.get_user_by_username(db, username)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if db_user.id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    db_profile = crud.get_user_profile(db, db_user.id)

    if not db_profile:
        if not profile_update.username or not profile_update.display_name:
            raise HTTPException(status_code=400, detail="Username and display name are required")
        create_data = schemas.UserProfileCreate(
            username=profile_update.username,
            display_name=profile_update.display_name,
            bio=profile_update.bio,
            profile_image_url=profile_update.profile_image_url
        )
        return crud.create_user_profile(db, create_data, db_user.id)

    return crud.update_user_profile(db, profile_update, db_user.id)


@router.post("/by-username/{username}/image", response_model=UserProfileResponse)
async def upload_profile_image_by_username(
    username: str,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload profile image by username.
    Only the profile owner can upload.
    """
    db_user = crud.get_user_by_username(db, username)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if db_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to upload")

    db_profile = crud.get_user_profile(db, db_user.id)
    if not db_profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if db_profile.profile_image_url:
        try:
            delete_image_from_s3(db_profile.profile_image_url)
        except Exception:
            pass  # Log if needed

    image_url = await upload_image_to_s3(file, db_user.id)
    return crud.update_profile_image_url(db, db_user.id, image_url)


@router.delete("/by-username/{username}/image", response_model=UserProfileResponse)
async def delete_profile_image_by_username(
    username: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete profile image by username.
    Only the profile owner can delete.
    """
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
    return crud.update_profile_image_url(db, db_user.id, None)
