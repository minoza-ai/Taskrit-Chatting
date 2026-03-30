from app.database import users_collection
from app.utils.serializers import serialize_doc


def find_user_by_uuid(user_uuid: str):
    return serialize_doc(users_collection.find_one({"user_uuid": user_uuid}))


def find_user_by_user_id(user_id: str):
    return serialize_doc(users_collection.find_one({"user_id": user_id}))


def user_exists(user_uuid: str) -> bool:
    return users_collection.find_one({"user_uuid": user_uuid}, {"_id": 1}) is not None


def resolve_user_uuid(identifier: str | None) -> str | None:
    if not identifier:
        return None

    user_by_uuid = users_collection.find_one({"user_uuid": identifier}, {"_id": 0, "user_uuid": 1})
    if user_by_uuid:
        return user_by_uuid["user_uuid"]

    user_by_user_id = users_collection.find_one({"user_id": identifier}, {"_id": 0, "user_uuid": 1})
    if user_by_user_id:
        return user_by_user_id["user_uuid"]

    return None


def get_user_identifiers_by_uuid(user_uuid: str) -> list[str]:
    user = users_collection.find_one({"user_uuid": user_uuid}, {"_id": 0, "user_uuid": 1, "user_id": 1})
    if not user:
        return [user_uuid]

    identifiers = [user_uuid]
    user_id = user.get("user_id")
    if user_id:
        identifiers.append(user_id)
    return identifiers


def get_all_users():
    return list(users_collection.find({}, {"_id": 0}))


def upsert_user(user_uuid: str, user_id: str, nickname: str, wallet_address: str = None, profile_image_url: str = None):
    update_data = {
        "user_uuid": user_uuid,
        "user_id": user_id,
        "nickname": nickname,
    }
    if wallet_address:
        update_data["wallet_address"] = wallet_address
    
    if profile_image_url:
         update_data["profile_image_url"] = profile_image_url

    users_collection.update_one(
        {"user_uuid": user_uuid},
        {"$set": update_data},
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