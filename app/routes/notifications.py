from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app import models, schemas, crud
from app.database import get_db
from app.auth import get_current_user
from app.websocket_manager import NotificationWebSocketManager
from app.auth import get_current_user_id_from_token  # Custom function

router = APIRouter(prefix="/notifications", tags=["notifications"])
ws_manager = NotificationWebSocketManager()

@router.websocket("/ws/notifications")
async def notification_socket(websocket: WebSocket, token: str):
    user_id = get_current_user_id_from_token(token)
    if not user_id:
        await websocket.close(code=1008)
        return

    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)

# Get all notifications for the logged-in user
@router.get("/", response_model=List[schemas.NotificationResponse])
def get_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return crud.get_user_notifications(db, current_user.id)

# Mark a specific notification as read
@router.patch("/{notification_id}/read")
def mark_as_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return crud.mark_notification_as_read(db, notification_id, current_user.id)

# Mark all notifications as read
@router.patch("/mark-all-read")
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return crud.mark_all_notifications_as_read(db, current_user.id)

# Delete a notification
@router.delete("/{notification_id}")
def delete_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return crud.delete_notification(db, notification_id, current_user.id)
