from app.database import users_collection
from app.utils.serializers import serialize_doc


def find_user_by_uuid(user_uuid: str):
    return serialize_doc(users_collection.find_one({"user_uuid": user_uuid}))


def user_exists(user_uuid: str) -> bool:
    return users_collection.find_one({"user_uuid": user_uuid}, {"_id": 1}) is not None


def get_all_users():
    return list(users_collection.find({}, {"_id": 0}))


def upsert_user(user_uuid: str, user_id: str, nickname: str):
    users_collection.update_one(
        {"user_uuid": user_uuid},
        {
            "$set": {
                "user_uuid": user_uuid,
                "user_id": user_id,
                "nickname": nickname,
            }
        },
        upsert=True,
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