from fastapi import WebSocket
from typing import Dict, List
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        print(f"✅ User {user_id} connected. Total connections: {len(self.active_connections[user_id])}")

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"❌ User {user_id} disconnected.")

    async def send_personal_message(self, user_id: int, data: dict):
        connections = self.active_connections.get(user_id, [])
        for connection in connections:
            await connection.send_json(data)

    async def broadcast_to_chat(self, chat_id: str, data: dict):
        # This would typically use a mapping from chat_id to user_ids
        # For now, we broadcast to all active users for demo purposes
        for user_id, connections in self.active_connections.items():
            for connection in connections:
                await connection.send_json(data)

    async def route_event(self, user_id: int, data: dict):
        event = data.get("event")
        payload = data.get("data")

        # Example: handle typing indicators or presence here
        if event == "typing":
            print(f"✍️  User {user_id} is typing in chat {payload.get('chat_id')}")
        elif event == "ping":
            await self.send_personal_message(user_id, {"event": "pong"})
        else:
            print(f"📦 Unhandled event from {user_id}: {event}")
