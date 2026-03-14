from pymongo import MongoClient
from pymongo.collection import Collection
from app.config import MONGODB_URI, MONGODB_DB

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]

users_collection: Collection = db["users"]
rooms_collection: Collection = db["rooms"]
messages_collection: Collection = db["messages"]
read_status_collection: Collection = db["read_status"]