from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app import schemas, crud
from app.database import get_db
from app.models import User
from app.auth import get_current_user

router = APIRouter()


@router.post("/api/block", status_code=204)
def block_user(req: schemas.BlockRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    blocked = db.query(User).filter_by(username=req.blocked_username).first()
    if not blocked:
        raise HTTPException(status_code=404, detail="User not found")
    if blocked.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")
    crud.block_user(db, current_user.id, blocked)
    return

@router.post("/api/unblock", status_code=204)
def unblock_user(req: schemas.BlockRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    blocked = db.query(User).filter_by(username=req.blocked_username).first()
    if not blocked:
        raise HTTPException(status_code=404, detail="User not found")
    crud.unblock_user(db, current_user.id, blocked)
    return

@router.get("/api/block/list", response_model=list[schemas.BlockedUserOut])
def get_blocked_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    users = crud.get_blocked_users(db, current_user.id)
    return users
