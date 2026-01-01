# =============================================
# Pydantic Modelleri - Veri Doğrulama
# =============================================

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

# =============================================
# ENUM'LAR
# =============================================

class VoteType(str, Enum):
    GERCEK = "gercek"
    EFSANE = "efsane"

# =============================================
# KULLANICI MODELLERİ
# =============================================

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    display_name: Optional[str] = Field(None, max_length=100)

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.replace('_', '').isalnum():
            raise ValueError('Kullanıcı adı sadece harf, rakam ve alt çizgi içerebilir')
        return v.lower()

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    display_name: Optional[str]
    avatar_url: Optional[str]
    is_editor: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserProfile(UserResponse):
    total_polls: int = 0
    active_polls: int = 0
    archived_polls: int = 0
    total_votes_received: int = 0
    total_likes_received: int = 0

# =============================================
# KATEGORİ MODELLERİ
# =============================================

class CategoryBase(BaseModel):
    name: str = Field(..., max_length=50)
    icon: Optional[str] = Field(None, max_length=10)
    color: Optional[str] = Field(None, max_length=7)

class CategoryResponse(CategoryBase):
    id: int
    
    class Config:
        from_attributes = True

# =============================================
# ANKET MODELLERİ
# =============================================

class PollBase(BaseModel):
    question: str = Field(..., min_length=10, max_length=500)
    category_id: int

class PollCreate(PollBase):
    pass

class PollResponse(BaseModel):
    id: int
    question: str
    gercek_votes: int
    efsane_votes: int
    likes_count: int
    comments_count: int
    created_at: datetime
    expires_at: datetime
    is_active: bool
    
    # İlişkili veriler
    user_id: int
    username: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    is_editor: bool
    
    category_id: Optional[int]
    category_name: Optional[str]
    category_icon: Optional[str]
    
    # Hesaplanan alanlar
    gercek_percentage: int = 50
    efsane_percentage: int = 50
    total_votes: int = 0
    seconds_left: Optional[float] = None
    is_expired: bool = False
    
    # Kullanıcıya özel (opsiyonel)
    user_vote: Optional[str] = None
    user_liked: bool = False
    
    class Config:
        from_attributes = True
    
    @validator('efsane_percentage', always=True)
    def calculate_efsane_percentage(cls, v, values):
        gercek = values.get('gercek_percentage', 50)
        return 100 - gercek
    
    @validator('total_votes', always=True)
    def calculate_total_votes(cls, v, values):
        return values.get('gercek_votes', 0) + values.get('efsane_votes', 0)
    
    @validator('is_expired', always=True)
    def check_expired(cls, v, values):
        seconds_left = values.get('seconds_left')
        if seconds_left is not None:
            return seconds_left <= 0
        return False

class PollListResponse(BaseModel):
    polls: List[PollResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

# =============================================
# OY MODELLERİ
# =============================================

class VoteCreate(BaseModel):
    poll_id: int
    vote_type: VoteType

class VoteResponse(BaseModel):
    id: int
    user_id: int
    poll_id: int
    vote_type: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# =============================================
# BEĞENİ MODELLERİ
# =============================================

class LikeCreate(BaseModel):
    poll_id: int

class LikeResponse(BaseModel):
    id: int
    user_id: int
    poll_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# =============================================
# YORUM MODELLERİ
# =============================================

class CommentBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)

class CommentCreate(CommentBase):
    poll_id: int

class CommentResponse(BaseModel):
    id: int
    user_id: int
    poll_id: int
    content: str
    created_at: datetime
    
    # Kullanıcı bilgileri
    username: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    is_editor: bool
    
    class Config:
        from_attributes = True

class CommentListResponse(BaseModel):
    comments: List[CommentResponse]
    total: int

# =============================================
# AUTH MODELLERİ
# =============================================

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # saniye cinsinden
    user: UserResponse

class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None

# =============================================
# GENEL RESPONSE MODELLERİ
# =============================================

class MessageResponse(BaseModel):
    message: str
    success: bool = True

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
