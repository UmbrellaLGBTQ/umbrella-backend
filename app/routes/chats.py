from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from uuid import UUID, uuid4
from datetime import datetime

from app import models, schemas, crud
from app.database import get_db
from app.auth import get_current_user
from app.websocket_manager import ConnectionManager
from app.models import GroupRole, AccountType
from app.schemas import ChatAction
from sqlalchemy import and_, or_

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
                    "event": "typing", "user_id": user_id
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

# ------------------------ Group Chat Management ------------------------
@router.post("/group/create", response_model=schemas.GroupResponse)
def create_group(
    data: schemas.GroupCreateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if db.query(models.Group).filter(models.Group.name == data.name).first():
        raise HTTPException(status_code=400, detail="Group name already exists.")

     # ✅ Check limit: 1 (creator) + len(members)
    if len(data.members_usernames) > 249:
        raise HTTPException(status_code=400, detail="A group can have up to 250 members including the creator.")

    group = models.Group(id=uuid4(), name=data.name, creator_id=current_user.id)
    db.add(group)
    db.commit()
    db.refresh(group)

    db.add(models.GroupMember(group_id=group.id, user_id=current_user.id, role=GroupRole.ADMIN, joined_at=datetime.utcnow()))
    for username in data.members_usernames:
        user = db.query(models.User).filter_by(username=username).first()
        if user and user.id != current_user.id:
            db.add(models.GroupMember(group_id=group.id, user_id=user.id, role=GroupRole.MEMBER, joined_at=datetime.utcnow()))
    db.commit()

    return group

# ------------------------ Private Chat Management ------------------------
@router.post("/create", response_model=Union[schemas.ChatResponse, schemas.GenericMessage])
def create_or_request_chat(
    request: schemas.ChatCreateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if request.target_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot chat with yourself.")

    existing = db.query(models.Chat).filter(
        or_(
            and_(models.Chat.user1_id == current_user.id, models.Chat.user2_id == request.target_user_id),
            and_(models.Chat.user1_id == request.target_user_id, models.Chat.user2_id == current_user.id)
        )
    ).first()
    if existing:
        return existing

    target = db.query(models.User).filter(models.User.id == request.target_user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    if target.account_type == AccountType.PRIVATE:
        if not db.query(models.ChatRequest).filter_by(sender_id=current_user.id, recipient_id=target.id, status="pending").first():
            db.add(models.ChatRequest(sender_id=current_user.id, recipient_id=target.id))
            db.commit()
        return {"message": f"Chat request sent to @{target.username}."}

    new_chat = models.Chat(user1_id=current_user.id, user2_id=target.id)
    db.add(new_chat)
    db.commit()
    db.refresh(new_chat)
    return new_chat

@router.post("/chat-request/{request_id}/action")
def handle_chat_request_action(
    request_id: int,
    action_data: schemas.ChatRequestAction,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    req = db.query(models.ChatRequest).filter_by(id=request_id).first()
    if not req or req.recipient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Invalid or unauthorized request.")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="Request already handled.")

    if action_data.action == "accept":
        req.status = "accepted"
        chat = models.Chat(user1_id=req.sender_id, user2_id=req.recipient_id)
        db.add(chat)
        db.commit()
        db.refresh(chat)
        return chat
    elif action_data.action == "decline":
        req.status = "declined"
        db.commit()
        return {"message": "Chat request declined."}

# ------------------------ Unified Message Handler ------------------------
@router.post("/messages/action")
def message_handler(
    chat_id: Optional[UUID] = None,
    group_id: Optional[UUID] = None,
    action: ChatAction = Query(..., description="Specify the action to perform."),
    message_id: Optional[UUID] = None,
    emoji: Optional[str] = None,
    forward_chat_id: Optional[UUID] = None,
    forward_group_id: Optional[UUID] = None,
    message_data: Optional[schemas.MessageSendRequest] = None,
    edit_data: Optional[schemas.MessageEditRequest] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if action == ChatAction.send:
        if not message_data:
            raise HTTPException(status_code=422, detail="message_data is required for send")
        return crud.send_message(db, current_user.id, schemas.MessageCreate(
            chat_id=chat_id,
            group_id=group_id,
            content=message_data.content,
            media_url=message_data.media_url,
            message_type=message_data.message_type
        ))

    if not message_id:
        raise HTTPException(status_code=422, detail="message_id is required for this action")

    if action == ChatAction.edit:
        return crud.edit_message(db, message_id, current_user.id, edit_data)

    elif action == ChatAction.delete:
        return crud.delete_message(db, message_id, current_user.id, for_everyone=False)

    elif action == ChatAction.delete_for_everyone:
        return crud.delete_message(db, message_id, current_user.id, for_everyone=True)

    elif action == ChatAction.unsend:
        return crud.unsend_message(db, message_id, current_user.id)

    elif action == ChatAction.react:
        if not emoji:
            raise HTTPException(status_code=422, detail="emoji is required for react")
        return crud.react_to_message(db, message_id, current_user.id, emoji)

    elif action == ChatAction.remove_reaction:
        return crud.remove_reaction(db, message_id, current_user.id)

    elif action == ChatAction.forward:
        return crud.forward_message(
            db=db,
            original_message_id=message_id,
            sender_id=current_user.id,
            target_chat_id=forward_chat_id,
            target_group_id=forward_group_id
        )

    elif action == ChatAction.copy:
        return crud.copy_message_to_clipboard(message_id, current_user.id, db)

    raise HTTPException(status_code=400, detail="Unsupported action")


# ------------------------ Get Messages ------------------------
@router.get("/group/{group_id}/messages", response_model=List[schemas.MessageResponse])
def get_group_messages(
    group_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not db.query(models.GroupMember).filter_by(group_id=group_id, user_id=current_user.id).first():
        raise HTTPException(status_code=403, detail="Not in group.")
    return db.query(models.Message).filter_by(group_id=group_id).order_by(models.Message.created_at).all()

@router.get("/chat/{chat_id}/messages", response_model=List[schemas.MessageResponse])
def get_chat_messages(
    chat_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    chat = db.query(models.Chat).filter_by(id=chat_id).first()
    if not chat or current_user.id not in [chat.user1_id, chat.user2_id]:
        raise HTTPException(status_code=403, detail="Unauthorized.")
    return db.query(models.Message).filter_by(chat_id=chat_id).order_by(models.Message.created_at).all()

# ------------------------ Get User Chats and Groups ------------------------
@router.get("/list", response_model=List[schemas.ChatResponse])
def get_user_chats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return crud.get_user_chats(db, current_user.id)

@router.get("/groups", response_model=List[schemas.GroupResponse])
def get_user_groups(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    groups = db.query(models.Group).join(models.GroupMember).filter(
        models.GroupMember.user_id == current_user.id
    ).all()
    if not groups:
        raise HTTPException(status_code=404, detail="No groups found.")
    return groups

@router.get("/group/{group_id}/members", response_model=List[schemas.GroupMemberResponse])
def get_group_members(
    group_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not db.query(models.GroupMember).filter_by(group_id=group_id, user_id=current_user.id).first():
        raise HTTPException(status_code=403, detail="Not in group.")
    members = db.query(models.GroupMember).filter_by(group_id=group_id).all()
    return members

# ------------------------ Manage Group Members ------------------------
@router.put("/group/{group_id}/members", response_model=schemas.GenericMessageResponse)
def manage_group_member(
    group_id: UUID,
    action_data: schemas.MemberActionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    admin = db.query(models.GroupMember).filter_by(group_id=group_id, user_id=current_user.id, role=GroupRole.ADMIN).first()
    if not admin:
        raise HTTPException(status_code=403, detail="Only admins can manage members.")

    target = db.query(models.User).filter_by(username=action_data.username).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    member = db.query(models.GroupMember).filter_by(group_id=group_id, user_id=target.id).first()
    action = action_data.action

    if action == "add":
        if member:
            raise HTTPException(status_code=400, detail="User already a member.")
        member_count = db.query(models.GroupMember).filter_by(group_id=group_id).count()
        if member_count >= 250:
            raise HTTPException(status_code=400, detail="Group member limit (250) reached.")
        db.add(models.GroupMember(group_id=group_id, user_id=target.id, role=GroupRole.MEMBER, joined_at=datetime.utcnow()))
    elif action == "remove":
        if not member or member.role == GroupRole.ADMIN:
            raise HTTPException(status_code=400, detail="Cannot remove.")
        db.delete(member)
    elif action == "promote":
        member.role = GroupRole.ADMIN
    elif action == "demote":
        if member.user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot demote self.")
        member.role = GroupRole.MEMBER
    else:
        raise HTTPException(status_code=400, detail="Invalid action.")

    db.commit()
    return {"message": f"{action.title()} successful."}

# ------------------------ Leave Group ------------------------
@router.post("/group/{group_id}/leave", response_model=schemas.LeaveGroupResponse)
def leave_group(
    group_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    member = db.query(models.GroupMember).filter_by(group_id=group_id, user_id=current_user.id).first()
    if not member:
        raise HTTPException(status_code=400, detail="Not a group member.")
    db.delete(member)
    db.commit()
    return {"message": "You have left the group."}