import os
from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.config import UPLOAD_DIR
from app.routers.users import router as users_router
from app.routers.room import router as rooms_router
from app.routers.messages import router as messages_router
from app.routers.files import router as files_router
from app.routers.read import router as reads_router
from app.services.index_service import create_indexes, seed_users

app = FastAPI(title="Taskrit Chat Service")

os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.on_event("startup")
def startup_event():
    create_indexes()
    seed_users()

@app.get("/")
def read_index():
    return FileResponse("index.html")

app.include_router(users_router)
app.include_router(rooms_router)
app.include_router(messages_router)
app.include_router(files_router)
app.include_router(reads_router)