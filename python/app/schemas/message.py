from pydantic import BaseModel

class SendMessageRequest(BaseModel):
    sender_uuid: str
    text: str

class DeleteMessageRequest(BaseModel):
    requester_uuid: str