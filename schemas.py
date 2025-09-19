from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    username: str
    is_admin: bool = False

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class AWSKeyBase(BaseModel):
    name: str
    access_key: str
    secret_key: str

class AWSKeyCreate(AWSKeyBase):
    user_id: Optional[int] = None

class AWSKeyResponse(AWSKeyBase):
    id: int
    user_id: Optional[int]
    status: str
    last_checked: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
