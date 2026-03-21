from pydantic import BaseModel


class SendMessageRequest(BaseModel):
    text: str


class EditMessageRequest(BaseModel):
    text: str