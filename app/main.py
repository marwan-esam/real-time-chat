import asyncio
import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import  FastAPI, Query, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
import jwt
from jwt import InvalidTokenError
from app.auth import router as auth_router, SECRET_KEY, ALGORITHM
from app.database import get_db
from app import models

# REDIS PUB/SUB INTEGRATION

# Connect to the redis container on port 6379
redis_client = redis.Redis(host="redis", port=6379, decode_responses=True)

# Connection Manager that tracks websockets connected to a certain worker
class ConnectionManager:
  def __init__(self):
    self.active_connections: list[WebSocket] = []
  
  async def connect(self, websocket: WebSocket):
    await websocket.accept()
    self.active_connections.append(websocket)

  def disconnect(self, websocket: WebSocket):
    self.active_connections.remove(websocket)

  async def broadcast(self, message: str):
    for connection in self.active_connections:
      await connection.send_text(message)


manager = ConnectionManager()

# The Background Listener
async def redis_listener():
  pubsub = redis_client.pubsub()
  await pubsub.subscribe("chat_room")
  # This loop runs forever in the background listening for Redis broadcasts
  async for message in pubsub.listen():
    if message["type"] == "message":
    # When a message hits Redis, broadcast it to all local websockets
      await manager.broadcast(message["data"])


# The listener starts when Uvicorn boots up
@asynccontextmanager
async def lifespan(app: FastAPI):
  listener_task = asyncio.create_task(redis_listener())
  yield
  listener_task.cancel()
  await redis_client.close()

app = FastAPI(title="Real-Time Chat Engine", lifespan=lifespan)

app.include_router(auth_router)

@app.get("/")
def health_check():
  return {"status": "The foundation is secure"}


# The WebSocket Security Guard
def get_current_user_ws(token: str = Query(description="Authentication Token"), db: Session = Depends(get_db)):
  try:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    username: str = payload.get("sub")
    if username is None:
      raise WebSocketDisconnect()
  
  except InvalidTokenError:
    raise WebSocketDisconnect()
  
  stmt = select(models.User).where(models.User.username == username)
  user = db.execute(stmt).scalar_one_or_none()

  if user is None:
    raise WebSocketDisconnect()
  
  return user


# TEST WEBSOCKET

html = """
<!DOCTYPE html>
<html>
    <head><title>Secure Chat Engine</title></head>
    <body>
        <h1>Secure Global Chat</h1>
        <form action="" onsubmit="connectWS(event)">
            <input type="text" id="tokenInput" placeholder="Paste your JWT here" autocomplete="off" style="width: 300px;"/>
            <button>Connect</button>
        </form>
        <hr>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off" disabled placeholder="Connect first..."/>
            <button id="sendBtn" disabled>Send</button>
        </form>
        <ul id='messages'></ul>
        <script>
            var ws;
            function connectWS(event) {
                event.preventDefault();
                var token = document.getElementById("tokenInput").value;
                ws = new WebSocket("ws://localhost:8000/ws?token=" + token);
                
                ws.onmessage = function(event) {
                    var messages = document.getElementById('messages');
                    var message = document.createElement('li');
                    var content = document.createTextNode(event.data);
                    message.appendChild(content);
                    messages.appendChild(message);
                };
                
                ws.onopen = function() {
                    document.getElementById("messageText").disabled = false;
                    document.getElementById("sendBtn").disabled = false;
                    document.getElementById("messageText").placeholder = "Type a message...";
                }
            }

            function sendMessage(event) {
                var input = document.getElementById("messageText");
                ws.send(input.value);
                input.value = '';
                event.preventDefault();
            }
        </script>
    </body>
</html>
"""

@app.get("/chat")
async def get_client():
  return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(
  websocket: WebSocket,
  current_user: models.User = Depends(get_current_user_ws),
  db: Session = Depends(get_db)
):
  await manager.connect(websocket)

  # LOAD HISTORY: Fetch the last 20 messages form PostgreSQL and push them to the user
  stmt = select(models.Message).order_by(models.Message.created_at.desc()).limit(20)
  recent_messages = db.execute(stmt).scalars().all()

  for message in reversed(recent_messages):
    await websocket.send_text(f"[History]: {message.sender.username}: {message.content}")

  try:
    while True:

      data = await websocket.receive_text()

      # Save the new message to PostgreSQL
      new_message = models.Message(content=data, sender_id=current_user.id)
      db.add(new_message)
      db.commit()

      # Publish the message to the Redis channel to triger the listener
      await redis_client.publish("chat_room", f"{current_user.username}: {data}")

  except WebSocketDisconnect:
      manager.disconnect(websocket)
      