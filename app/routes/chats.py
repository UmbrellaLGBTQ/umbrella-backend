from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Dict
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app import models, schemas
from app.auth import get_current_user
from app.websocket_manager import ConnectionManager

router = APIRouter(prefix="/chat", tags=["Chat"])
ws_manager = ConnectionManager()

# Create a new chat (1-on-1 or group)
@router.post("/create", response_model=schemas.ChatResponse)
def create_chat(chat_data: schemas.ChatCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    new_chat = models.Chat(
        is_group=chat_data.is_group,
        name=chat_data.name,
        image=chat_data.image,
        creator_id=current_user.id,
        created_at=datetime.utcnow()
    )
    db.add(new_chat)
    db.commit()
    db.refresh(new_chat)

    member_ids = chat_data.participant_ids + [current_user.id]
    for uid in set(member_ids):
        db.add(models.ChatMember(
            chat_id=new_chat.id,
            user_id=uid,
            is_admin=(uid == current_user.id),
            joined_at=datetime.utcnow()
        ))
    db.commit()
    return new_chat

# Get all chats for the current user
@router.get("/list", response_model=List[schemas.ChatResponse])
def get_user_chats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    chats = db.query(models.Chat).join(models.ChatMember).filter(models.ChatMember.user_id == current_user.id).all()
    return chats

# Send a message to a chat
@router.post("/{chat_id}/message", response_model=schemas.MessageResponse)
async def send_message(chat_id: UUID, message: schemas.MessageCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not db.query(models.ChatMember).filter_by(chat_id=chat_id, user_id=current_user.id).first():
        raise HTTPException(status_code=403, detail="You are not a member of this chat")

    new_message = models.Message(
        chat_id=chat_id,
        sender_id=current_user.id,
        content=message.content,
        message_type=message.message_type,
        reply_to_id=message.reply_to_id,
        created_at=datetime.utcnow()
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)

    # Notify chat participants via WebSocket
    await ws_manager.broadcast_to_chat(chat_id, {"event": "new_message", "data": schemas.MessageResponse.from_orm(new_message).dict()})
    return new_message

# Get messages from a chat
@router.get("/{chat_id}/messages", response_model=List[schemas.MessageResponse])
def get_chat_messages(chat_id: UUID, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not db.query(models.ChatMember).filter_by(chat_id=chat_id, user_id=current_user.id).first():
        raise HTTPException(status_code=403, detail="Access denied")

    return db.query(models.Message).filter_by(chat_id=chat_id).order_by(models.Message.created_at).all()

# React to a message
@router.post("/message/{message_id}/react", response_model=schemas.ReactionResponse)
async def react_to_message(message_id: UUID, reaction: schemas.ReactionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    existing = db.query(models.Reaction).filter_by(message_id=message_id, user_id=current_user.id).first()
    if existing:
        db.delete(existing)
    new_reaction = models.Reaction(
        message_id=message_id,
        user_id=current_user.id,
        emoji=reaction.emoji
    )
    db.add(new_reaction)
    db.commit()
    db.refresh(new_reaction)

    # Notify via WebSocket
    await ws_manager.broadcast_to_chat(models.Message.message_id, {"event": "reaction", "data": schemas.ReactionResponse.from_orm(new_reaction).dict()})
    return new_reaction

# Delete a message
@router.delete("/message/{message_id}", response_model=schemas.MessageResponse)
def delete_message(message_id: UUID, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    message = db.query(models.Message).filter_by(id=message_id, sender_id=current_user.id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found or unauthorized")
    db.delete(message)
    db.commit()
    return message

# WebSocket for real-time messaging
@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await ws_manager.route_event(user_id, data)
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)

# Start a call
@router.post("/call/start", response_model=schemas.CallResponse)
def start_call(call_data: schemas.CallStartRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if not db.query(models.ChatMember).filter_by(chat_id=call_data.chat_id, user_id=current_user.id).first():
        raise HTTPException(status_code=403, detail="You are not part of this chat")

    new_call = models.Call(
        initiator_id=current_user.id,
        chat_id=call_data.chat_id,
        type=call_data.type,
        started_at=datetime.utcnow()
    )
    db.add(new_call)
    db.commit()
    db.refresh(new_call)
    return new_call

# Join call participant
@router.post("/call/{call_id}/join", response_model=schemas.CallParticipantResponse)
def join_call(call_id: UUID, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    participant = models.CallParticipant(
        call_id=call_id,
        user_id=current_user.id,
        joined_at=datetime.utcnow()
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant

# Leave call
@router.post("/call/{call_id}/leave", response_model=schemas.CallParticipantResponse)
def leave_call(call_id: UUID, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    participant = db.query(models.CallParticipant).filter_by(call_id=call_id, user_id=current_user.id).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    participant.left_at = datetime.utcnow()
    db.commit()
    return participant

# Call history
@router.get("/call/history", response_model=List[schemas.CallResponse])
def call_history(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Call).filter(
        (models.Call.initiator_id == current_user.id) |
        (models.Call.id.in_(db.query(models.CallParticipant.call_id).filter_by(user_id=current_user.id)))
    ).order_by(models.Call.started_at.desc()).all()
