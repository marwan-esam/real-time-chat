from pydantic import BaseModel, ConfigDict
from datetime import datetime

# Registration Schema
class UserCreate(BaseModel):
  user_name: str
  password: str


# Public User Schema (what the API returns to ensure to never return passwords)
class UserResponse(BaseModel):
  id: int
  username: str
  # Allows Pydantic to read data directly from the database
  model_config = ConfigDict(from_attributes=True)


# JWT Token Schema
class Token(BaseModel):
  access_token: str
  token_type: str


