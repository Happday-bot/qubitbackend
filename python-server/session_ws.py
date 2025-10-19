from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Dict, List

router = APIRouter()
active_connections: Dict[int, List[WebSocket]] = {}

@router.websocket("/ws/session/{user_id}")
async def websocket_session(websocket: WebSocket, user_id: int):
    await websocket.accept()
    if user_id not in active_connections:
        active_connections[user_id] = []
    active_connections[user_id].append(websocket)

    try:
        while True:
            await websocket.receive_text()  # keep-alive
    except WebSocketDisconnect:
        active_connections[user_id].remove(websocket)
        if not active_connections[user_id]:
            del active_connections[user_id]

async def notify_force_logout(user_id: int):
    if user_id in active_connections:
        for ws in active_connections[user_id]:
            try:
                await ws.send_json({"type": "FORCE_LOGOUT"})
            except:
                pass
        active_connections[user_id] = []
