from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas
from app.models import User
from app.auth import get_current_user

router = APIRouter(
    prefix="/api/Search",
    tags=["search"],
    responses={404: {"description": "Not found"}}
)

@router.get("/api/search/users", response_model=list[schemas.UserProfileOut])
def search_users(
    query: str = Query(..., min_length=1),
    limit: int = Query(10),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) 
):
    return crud.search_profiles_by_name_or_username(db, query, limit, offset, current_user.id)
