from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from .. import models, schemas, crud
from ..database import get_db
from ..auth import get_current_user
from ..websocket_manager import ConnectionManager

router = APIRouter(prefix="/chat", tags=["chat"])

ws_manager = ConnectionManager()

# ------------------------ WebSocket ------------------------
@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("event")
            if event == "typing":
                await ws_manager.broadcast_to_chat(data["chat_id"], {
                    "event": "typing",
                    "user_id": user_id
                })
            elif event == "seen":
                await ws_manager.broadcast_to_chat(data["chat_id"], {
                    "event": "seen",
                    "message_id": data["message_id"],
                    "user_id": user_id
                })
            elif event == "join":
                await ws_manager.join_chat(user_id, data["chat_id"])
            elif event == "leave":
                await ws_manager.leave_chat(user_id, data["chat_id"])
    except WebSocketDisconnect:
        await ws_manager.disconnect(user_id)


# ------------------------ Chat Management ------------------------
@router.post("/create", response_model=schemas.ChatResponse)
def create_chat(request: schemas.ChatCreateRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return crud.create_or_get_chat(db, current_user.id, request.target_user_id)


@router.get("/list", response_model=List[schemas.ChatResponse])
def get_user_chats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return crud.get_user_chats(db, current_user.id)


@router.patch("/{chat_id}/settings")
def update_chat_settings(chat_id: UUID, settings: schemas.ChatSettingsUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return crud.update_chat_settings(db, chat_id, current_user.id, settings)


# ------------------------ Unified Message Handler ------------------------
@router.post("/{chat_id}/message")
def message_handler(
    chat_id: UUID,
    action: str = Query("send", enum=["send", "edit", "delete", "delete_for_everyone", "unsend", "hide", "react", "remove_reaction"]),
    message_id: Optional[UUID] = None,
    emoji: Optional[str] = None,
    message_data: Optional[schemas.MessageSendRequest] = None,
    edit_data: Optional[schemas.MessageEditRequest] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if action == "send":
        return crud.send_message(db, chat_id, current_user.id, message_data)
    elif action == "edit":
        return crud.edit_message(db, message_id, current_user.id, edit_data)
    elif action == "delete":
        return crud.delete_message(db, message_id, current_user.id, for_everyone=False)
    elif action == "delete_for_everyone":
        return crud.delete_message(db, message_id, current_user.id, for_everyone=True)
    elif action == "unsend":
        return crud.unsend_message(db, message_id, current_user.id)
    elif action == "hide":
        return crud.hide_message_for_user(db, message_id, current_user.id)
    elif action == "react":
        return crud.react_to_message(db, message_id, current_user.id, emoji)
    elif action == "remove_reaction":
        return crud.remove_reaction(db, message_id, current_user.id)
    raise HTTPException(status_code=400, detail="Unsupported action")


@router.get("/{chat_id}/messages", response_model=List[schemas.MessageResponse])
def get_chat_messages(
    chat_id: UUID,
    search: Optional[str] = None,
    type: Optional[str] = None,  # e.g., "media"
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return crud.get_filtered_messages(db, chat_id, current_user.id, search=search, type=type)


# ------------------------ Chat User Actions ------------------------
@router.post("/user-action")
def user_action(
    action_data: schemas.ChatUserActionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return crud.handle_chat_user_action(db, current_user.id, action_data)
