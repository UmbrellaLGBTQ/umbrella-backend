from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import schemas, crud, auth, models
from ..database import get_db

router = APIRouter(
    prefix="/login",
    tags=["login"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=schemas.Token)
def login_user(
    login_request: schemas.LoginRequest,
    db: Session = Depends(get_db)
):
    """Log in using username or phone number"""

    # Normalize phone number if used
    login_id = login_request.login_id.replace(" ", "")

    # Fetch most appropriate user based on logic (most recent if phone is used)
    user = crud.get_user_by_login_id(db, login_id, login_request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.theme:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Theme selection required before login"
        )

    # Determine login type
    login_type = models.LoginType.PHONE if user.phone_number == login_id else models.LoginType.PHONE

    # Update login metadata
    crud.update_user_login(db, user.id, login_type)

    # Generate tokens
    access_token = auth.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth.create_refresh_token(data={"sub": str(user.id)}, db=db)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/token", response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """OAuth2 password login (for Swagger UI login button)"""
    login_id = form_data.username.replace(" ", "")
    user = crud.get_user_by_login_id(db, login_id, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.theme:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Theme selection required before login"
        )

    login_type = models.LoginType.PHONE
    crud.update_user_login(db, user.id, login_type)

    access_token = auth.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth.create_refresh_token(data={"sub": str(user.id)}, db=db)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    """Returns the authenticated user's profile"""
    return current_user
