from pymongo import MongoClient
from pymongo.collection import Collection
from app.config import MONGODB_URI, MONGODB_DB

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]

users_collection: Collection = db["users"]
rooms_collection: Collection = db["rooms"]
messages_collection: Collection = db["messages"]
read_status_collection: Collection = db["read_status"]


def create_indexes():
    users_collection.create_index("user_uuid", unique=True)
    rooms_collection.create_index("room_id", unique=True)
    rooms_collection.create_index("dm_key")
    messages_collection.create_index("message_id", unique=True)
    messages_collection.create_index([("room_id", 1), ("seq", 1)])
    read_status_collection.create_index([("room_id", 1), ("user_uuid", 1)], unique=True)