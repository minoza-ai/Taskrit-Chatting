from app.database import users_collection
from app.utils.serializers import serialize_doc

def find_user_by_uuid(user_uuid: str):
    return serialize_doc(users_collection.find_one({"user_uuid": user_uuid}))

def user_exists(user_uuid: str) -> bool:
    return users_collection.find_one({"user_uuid": user_uuid}, {"_id": 1}) is not None

def get_all_users():
    return list(users_collection.find({}, {"_id": 0}))