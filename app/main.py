from fastapi import  FastAPI
from app.auth import router as auth_router

app = FastAPI(title="Real-Time Chat Engine")

app.include_router(auth_router)

@app.get("/")
def health_check():
  return {"status": "The foundation is secure"}