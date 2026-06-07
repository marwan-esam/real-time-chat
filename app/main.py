from fastapi import FastAPI
import asyncio
from contextlib import asynccontextmanager

from app.auth import router as auth_router
from app.chat import router as ws_router
from app.socket_manager import redis_listener, redis_client


# The listener starts when Uvicorn boots up
@asynccontextmanager
async def lifespan(app: FastAPI):
  listener_task = asyncio.create_task(redis_listener())
  yield
  listener_task.cancel()
  await redis_client.close()

app = FastAPI(title="Real-Time Chat Engine", lifespan=lifespan)

app.include_router(auth_router)
app.include_router(ws_router)

@app.get("/")
def health_check():
  return {"status": "The foundation is secure"}


