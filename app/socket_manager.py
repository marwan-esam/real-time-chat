import redis.asyncio as redis
from fastapi import WebSocket

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