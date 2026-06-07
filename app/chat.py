from fastapi import Query, Depends, WebSocket, WebSocketDisconnect, APIRouter
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
import jwt
from jwt import InvalidTokenError

from app import models
from app.auth import SECRET_KEY, ALGORITHM
from app.database import get_db
from app.socket_manager import manager, redis_client

router = APIRouter()

# The WebSocket Security Guard
async def get_current_user_ws(token: str = Query(description="Authentication Token"), db: Session = Depends(get_db)):
  is_blacklisted = await redis_client.get(f"blacklist:{token}")
  if is_blacklisted:
    raise WebSocketDisconnect()
   
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

@router.get("/chat")
async def get_client():
  return HTMLResponse(html)

@router.websocket("/ws")
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
      