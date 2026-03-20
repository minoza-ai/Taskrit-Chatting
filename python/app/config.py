from dotenv import load_dotenv
import os

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "chat-service")
NODE_ENV = os.getenv("NODE_ENV", "development").lower()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def env_value(local_key: str, prod_key: str, legacy_key: str, default: str) -> str:
	if NODE_ENV == "production":
		return os.getenv(prod_key) or os.getenv(legacy_key) or default
	return os.getenv(local_key) or os.getenv(legacy_key) or default


MONGODB_USER = os.getenv("MONGODB_USER", "")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/taskrit")
MONGODB_DB = os.getenv("MONGODB_DB", "taskrit-chatting")

USER_API_BASE_URL = env_value(
	local_key="USER_API_BASE_URL_LOCAL",
	prod_key="USER_API_BASE_URL_PROD",
	legacy_key="USER_API_BASE_URL",
	default="http://localhost:3000",
)

USER_ME_ENDPOINT = os.getenv("USER_ME_ENDPOINT", "/user/me")