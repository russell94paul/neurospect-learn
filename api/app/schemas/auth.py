from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    discord_id: str
    discord_username: str | None = None
    discord_avatar_url: str | None = None
