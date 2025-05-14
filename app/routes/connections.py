from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session
from typing import List

from .. import crud, models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(
    prefix="/api/connections",
    tags=["connections"],
    responses={404: {"description": "Not found"}}
)


@router.post("/requests", response_model=schemas.ConnectionRequestResponse)
async def create_connection_request(
    request_data: schemas.ConnectionRequestCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new connection request.
    Only the current user can send connection requests from their account.
    """
    # Ensure the requester is the current user
    if request_data.requester_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create connection requests for other users"
        )
    
    return crud.create_connection_request(db, request_data.requester_id, request_data.requestee_id)


@router.get("/requests/received", response_model=List[schemas.ConnectionRequestResponse])
async def get_received_connection_requests(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all connection requests received by the current user"""
    return current_user.received_requests


@router.get("/requests/sent", response_model=List[schemas.ConnectionRequestResponse])
async def get_sent_connection_requests(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all connection requests sent by the current user"""
    return current_user.sent_requests


@router.put("/requests/{request_id}", response_model=schemas.ConnectionRequestResponse)
async def update_connection_request(
    status_update: schemas.ConnectionRequestUpdate,
    request_id: int = Path(..., title="The ID of the connection request"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a connection request status (accept/reject).
    Only the requestee can update the connection request.
    """
    return crud.update_connection_request_status(db, request_id, status_update, current_user.id)


@router.get("/", response_model=List[schemas.ConnectionResponse])
async def get_user_connections(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all connections for the current user"""
    return crud.get_user_connections(db, current_user.id)


@router.get("/check/{user_id}", response_model=bool)
async def check_connection_status(
    user_id: int = Path(..., title="The ID of the user to check connection with"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if the current user is connected with another user"""
    return crud.check_users_connected(db, current_user.id, user_id)