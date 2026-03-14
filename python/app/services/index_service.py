from app.database import (
    users_collection,
    rooms_collection,
    messages_collection,
    read_status_collection,
)

def seed_users():
    seed_data = [
        {
            "user_uuid": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": "john_doe",
            "nickname": "John"
        },
        {
            "user_uuid": "660e8400-e29b-41d4-a716-446655440111",
            "user_id": "alice_01",
            "nickname": "Alice"
        },
        {
            "user_uuid": "770e8400-e29b-41d4-a716-446655440222",
            "user_id": "bob_02",
            "nickname": "Bob"
        },
        {
            "user_uuid": "880e8400-e29b-41d4-a716-446655440333",
            "user_id": "charlie_03",
            "nickname": "Charlie"
        }
    ]

    for user in seed_data:
        if not users_collection.find_one({"user_uuid": user["user_uuid"]}):
            users_collection.insert_one(user)

def create_indexes():
    users_collection.create_index("user_uuid", unique=True)
    rooms_collection.create_index("room_id", unique=True)
    rooms_collection.create_index("dm_key")
    messages_collection.create_index("message_id", unique=True)
    messages_collection.create_index([("room_id", 1), ("seq", 1)])
    read_status_collection.create_index([("room_id", 1), ("user_uuid", 1)], unique=True)