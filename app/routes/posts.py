from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas, crud
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(
    prefix="/api/posts",
    tags=["posts"],
    responses={404: {"description": "Not found"}}
)


@router.get("/user/{username}/grid", response_model=schemas.UserGridResponse)
def get_user_post_grid(
    username: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = crud.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = crud.get_user_profile(db, user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    is_owner = current_user.id == user.id
    is_connected = crud.check_users_connected(db, current_user.id, user.id)

    post_count = crud.count_user_posts(db, user.id)

    if user.account_type == models.AccountType.PRIVATE and not is_owner and not is_connected:
        return schemas.UserGridResponse(
            post_count=post_count,
            posts=[],
            clips=[],
            tags=[],
            message="This account is private. Please connect to access content."
        )

    posts = crud.get_user_posts(db, user.id)
    clips = crud.get_user_clips(db, user.id)
    tags = crud.get_user_tags(db, user.id)

    return schemas.UserGridResponse(
        post_count=post_count,
        posts=posts,
        clips=clips,
        tags=tags
    )

