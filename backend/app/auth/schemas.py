from pydantic import BaseModel
from typing import Optional


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    persona_text: Optional[str] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
