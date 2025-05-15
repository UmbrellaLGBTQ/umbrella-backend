from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from fastapi.responses import JSONResponse

from .. import crud, models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..schemas import ConnectionRequestResponse, RequesterPreview

router = APIRouter(
    prefix="/api/connections",
    tags=["connections"]
)

@router.post("/request", response_model=schemas.ConnectionRequestResponse)
def send_connection_request(
    request: schemas.ConnectionRequestCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        result = crud.handle_connection_request_logic(db, current_user.username, request.requestee_username)

        if isinstance(result, dict) and "message" in result:
            # Explicitly return JSONResponse for the simple message
            return JSONResponse(content=result)

        # Return full schema for pending connection
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/{request_id}/respond", response_model=schemas.MessageResponse)
def respond_to_connection_request(
    request_id: int,
    update: schemas.ConnectionRequestUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if update.status == "accepted":
        success = crud.accept_connection_request(db, request_id, current_user.id)
        message = "Connection request accepted."
    elif update.status == "declined":
        success = crud.decline_connection_request(db, request_id, current_user.id)
        message = "Connection request declined."
    else:
        raise HTTPException(status_code=400, detail="Invalid status")

    if not success:
        raise HTTPException(status_code=404, detail="No such pending request.")

    return {"message": message}


@router.get("/pending", response_model=List[schemas.ConnectionRequestResponse])
def list_pending_requests(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    requests = crud.get_pending_requests_for_user(db, current_user.id)
    
    return [
        ConnectionRequestResponse(
            id=req.id,
            status=req.status,
            created_at=req.created_at,
            requester=RequesterPreview(
                username=req.requester.username,
                display_name=req.requester.profile.display_name,  # from UserProfile
                profile_image_url=req.requester.profile.profile_image_url
            )
        )
        for req in requests
    ]
    return crud.get_pending_requests_for_user(db, current_user.id)

@router.get("/{username}", response_model=schemas.ConnectionListResponse)
def get_user_connections(
    username: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    user = crud.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    is_owner = current_user.id == user.id
    is_connected = crud.check_users_connected(db, current_user.id, user.id)

    if user.account_type == models.AccountType.PRIVATE and not is_owner and not is_connected:
        raise HTTPException(status_code=403, detail="This user's connections are private.")
    
    connected_users = crud.get_user_connections(db, user.id)
    return schemas.ConnectionListResponse(connections=connected_users)
