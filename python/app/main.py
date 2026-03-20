from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import APP_NAME
from app.database import create_indexes
from app.services.user_service import seed_users
from app.routers import room, messages, files, read, users
from app.websocket import chat_ws

app = FastAPI(title=APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    create_indexes()
    seed_users()


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(room.router)
app.include_router(messages.router)
app.include_router(files.router)
app.include_router(read.router)
app.include_router(chat_ws.router)
app.include_router(users.router)
