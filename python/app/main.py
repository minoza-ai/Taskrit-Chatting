from fastapi import FastAPI
from app.config import APP_NAME
from app.database import create_indexes
from app.services.user_service import seed_users
from app.routers import users, rooms, messages, files, reads

app = FastAPI(title=APP_NAME)


@app.on_event("startup")
def startup_event():
    create_indexes()
    seed_users()


app.include_router(users.router)
app.include_router(rooms.router)
app.include_router(messages.router)
app.include_router(files.router)
app.include_router(reads.router)