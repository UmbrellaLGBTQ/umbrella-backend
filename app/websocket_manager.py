from typing import Dict, Set
from fastapi import WebSocket
from collections import defaultdict
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}  # user_id -> WebSocket
        self.chat_subscribers: Dict[str, Set[int]] = defaultdict(set)  # chat_id -> user_ids
        self.lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.active_connections[user_id] = websocket

    async def disconnect(self, user_id: int):
        async with self.lock:
            if user_id in self.active_connections:
                del self.active_connections[user_id]

    async def send_to_user(self, user_id: int, data: dict):
        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_json(data)

    async def broadcast_to_chat(self, chat_id: str, data: dict):
        subscribers = self.chat_subscribers.get(chat_id, set())
        for user_id in subscribers:
            await self.send_to_user(user_id, data)

    async def join_chat(self, user_id: int, chat_id: str):
        self.chat_subscribers[chat_id].add(user_id)

    async def leave_chat(self, user_id: int, chat_id: str):
        self.chat_subscribers[chat_id].discard(user_id)

    def is_online(self, user_id: int) -> bool:
        return user_id in self.active_connections

class NotificationWebSocketManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        self.active_connections.pop(user_id, None)

    async def send_notification(self, user_id: int, data: dict):
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            await websocket.send_json(data)

    async def broadcast(self, data: dict):
        for ws in self.active_connections.values():
            await ws.send_json(data)