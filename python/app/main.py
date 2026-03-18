from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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


@app.get("/")
def serve_index():
    return FileResponse("index.html")


@app.get("/test")
def serve_test_dashboard():
    return FileResponse("test_dashboard.html")


@app.get("/demo")
def serve_chat_demo():
    return FileResponse("chat_demo.html")


app.include_router(room.router)
app.include_router(messages.router)
app.include_router(files.router)
app.include_router(read.router)
app.include_router(chat_ws.router)
app.include_router(users.router)
