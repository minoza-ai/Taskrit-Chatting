from pydantic import BaseModel


class SendMessageRequest(BaseModel):
    text: str