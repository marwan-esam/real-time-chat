import asyncio
import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import  FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from app.auth import router as auth_router

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


# TEST WEBSOCKET

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>WebSocket Bare-Metal Test</title>
    </head>
    <body>
        <h1>WebSocket Echo Test</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            // This line initiates the "phone call" to the server
            var ws = new WebSocket("ws://localhost:8000/ws");
            
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages');
                var message = document.createElement('li');
                var content = document.createTextNode(event.data);
                message.appendChild(content);
                messages.appendChild(message);
            };
            
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

@app.get("/echo-client")
async def get_client():
  return HTMLResponse(html)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
  await manager.connect(websocket)

  try:
    while True:

      data = await websocket.receive_text()

      # Publish the message to the Redis channel to triger the listener
      await redis_client.publish("chat_room", f"Broadcast: {data}")

  except WebSocketDisconnect:
      manager.disconnect(websocket)
      