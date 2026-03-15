from pydantic import BaseModel


class SimpleMessageResponse(BaseModel):
    message: str