from pydantic import BaseModel

class ReadMessageRequest(BaseModel):
    user_uuid: str
    last_read_message_id: str