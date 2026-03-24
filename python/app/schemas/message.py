from typing import Optional
from pydantic import BaseModel


class SendMessageRequest(BaseModel):
    text: str
    parent_id: Optional[str] = None


class EditMessageRequest(BaseModel):
    text: str