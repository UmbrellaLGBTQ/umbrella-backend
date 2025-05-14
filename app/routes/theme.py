from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import schemas, crud, models, auth
from ..database import get_db

router = APIRouter(
    prefix="/theme",
    tags=["theme"],
    responses={404: {"description": "Not found"}},
)

@router.patch("/", response_model=schemas.MessageResponse)
def update_theme(
    theme_data: schemas.ThemeUpdateRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Update user theme preference"""
    updated_user = crud.update_user_theme(db, current_user.id, theme_data.theme)
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": f"Theme updated to {theme_data.theme.value}"}


# @router.get("/", response_model=schemas.MessageResponse)
# def get_theme(
#     current_user: models.User = Depends(auth.get_current_user)
# ):
#     """Get current user theme preference"""
#     return {"message": current_user.theme.value}