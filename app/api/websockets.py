import json
from typing import Dict, List, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        # Maps sheet_id to a set of active websocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Maps user_id to a set of active websocket connections
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        self.admin_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, sheet_id: str):
        await websocket.accept()
        if sheet_id not in self.active_connections:
            self.active_connections[sheet_id] = set()
        self.active_connections[sheet_id].add(websocket)

    def disconnect(self, websocket: WebSocket, sheet_id: str):
        if sheet_id in self.active_connections:
            self.active_connections[sheet_id].remove(websocket)
            if not self.active_connections[sheet_id]:
                del self.active_connections[sheet_id]
                
    async def connect_user(self, websocket: WebSocket, user_id: str, is_admin: bool = False):
        await websocket.accept()
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket)
        if is_admin:
            self.admin_connections.add(websocket)
            
    def disconnect_user(self, websocket: WebSocket, user_id: str, is_admin: bool = False):
        if user_id in self.user_connections and websocket in self.user_connections[user_id]:
            self.user_connections[user_id].remove(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        if is_admin and websocket in self.admin_connections:
            self.admin_connections.remove(websocket)

    async def broadcast_to_sheet(self, message: dict, sheet_id: str, exclude: WebSocket = None):
        if sheet_id in self.active_connections:
            for connection in self.active_connections[sheet_id]:
                if connection != exclude:
                    try:
                        await connection.send_json(message)
                    except:
                        pass
                        
    async def broadcast_to_user(self, message: dict, user_id: str):
        if user_id in self.user_connections:
            for connection in self.user_connections[user_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass

    async def broadcast_to_admins(self, message: dict):
        for connection in self.admin_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@router.websocket("/ws/notifications/{user_id}")
async def notification_websocket_endpoint(websocket: WebSocket, user_id: str, is_admin: bool = True):
    await manager.connect_user(websocket, user_id, is_admin)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_user(websocket, user_id, is_admin)

@router.websocket("/ws/{sheet_id}")
async def websocket_endpoint(websocket: WebSocket, sheet_id: str):
    await manager.connect(websocket, sheet_id)
    try:
        while True:
            data = await websocket.receive_text()
            # We expect { type: 'cell_update', rowId: ..., field: ..., value: ... }
            try:
                payload = json.loads(data)
                # Broadcast the update to everyone else in this sheet
                await manager.broadcast_to_sheet(payload, sheet_id, exclude=websocket)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket, sheet_id)
