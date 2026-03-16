from pydantic import BaseModel


class ReadMessageRequest(BaseModel):
    last_read_message_id: str