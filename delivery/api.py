from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json

app = FastAPI(title="Crypto Signal Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_signals = []
connected_clients = set()

class WebhookPayload(BaseModel):
    message: str

@app.get("/api/signals")
async def get_signals():
    """REST endpoint to fetch recent signals."""
    return {"status": "success", "data": active_signals[-50:]}

@app.post("/api/webhook")
async def receive_tradingview_webhook(payload: dict):
    """If using TV alerts to trigger logic instead of custom python bot."""
    return {"status": "received"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        # Send existing signals on connect
        for sig in active_signals[-10:]:
            await websocket.send_json(sig)
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except Exception:
        connected_clients.remove(websocket)

async def broadcast_signal(signal_data: dict):
    """Called by the main loop to broadcast a newly generated signal."""
    active_signals.append(signal_data)
    
    # Prune old signals
    if len(active_signals) > 100:
        active_signals.pop(0)
        
    # Broadcast to connected WebSockets
    dead_clients = set()
    for client in connected_clients:
        try:
            await client.send_json(signal_data)
        except Exception:
            dead_clients.add(client)
            
    for client in dead_clients:
        connected_clients.remove(client)

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    with open("delivery/dashboard.html", "r") as f:
        html = f.read()
    return html

def start_api():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
