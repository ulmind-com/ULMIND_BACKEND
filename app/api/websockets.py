import json
from typing import Dict, List, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        # Maps sheet_id to a set of active websocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}

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

    async def broadcast_to_sheet(self, message: dict, sheet_id: str, exclude: WebSocket = None):
        if sheet_id in self.active_connections:
            for connection in self.active_connections[sheet_id]:
                if connection != exclude:
                    try:
                        await connection.send_json(message)
                    except:
                        pass

manager = ConnectionManager()

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
