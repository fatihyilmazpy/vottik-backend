# =============================================
# Auth Router - Kimlik Doğrulama (SQLite Uyumlu)
# =============================================

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from typing import Optional
import hashlib
import secrets
import jwt
import os

from database.connection import get_db

router = APIRouter()
security = HTTPBearer(auto_error=False)

# JWT ayarları
SECRET_KEY = os.getenv("SECRET_KEY", "gercekmi-super-secret-key-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# =============================================
# YARDIMCI FONKSİYONLAR
# =============================================

def hash_password(password: str) -> str:
    """Şifreyi hashle (basit SHA256)"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Şifreyi doğrula"""
    return hash_password(plain_password) == hashed_password

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWT token oluştur"""
    to_encode = data.copy()
    # user_id'yi string'e çevir
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Optional[dict]:
    """JWT token çöz"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # sub'ı integer'a çevir
        if "sub" in payload:
            payload["sub"] = int(payload["sub"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except Exception:
        return None

# =============================================
# DEPENDENCY'LER
# =============================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db = Depends(get_db)
) -> dict:
    """Mevcut kullanıcıyı getir (zorunlu)"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama gerekli",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya süresi dolmuş token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token",
        )
    
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, username, email, display_name, avatar_url, is_editor, is_active, created_at FROM users WHERE id = ?",
        (user_id,)
    )
    user = cursor.fetchone()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı",
        )
    
    if not user[6]:  # is_active
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap devre dışı",
        )
    
    return {
        "id": user[0],
        "username": user[1],
        "email": user[2],
        "display_name": user[3],
        "avatar_url": user[4],
        "is_editor": bool(user[5]),
        "is_active": bool(user[6]),
        "created_at": user[7]
    }

async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db = Depends(get_db)
) -> Optional[dict]:
    """Mevcut kullanıcıyı getir (opsiyonel)"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None

# =============================================
# API ENDPOINTS
# =============================================

@router.post("/register")
async def register(user_data: dict, db = Depends(get_db)):
    """
    Yeni kullanıcı kaydı
    """
    cursor = db.cursor()
    
    username = user_data.get("username")
    email = user_data.get("email")
    password = user_data.get("password")
    
    if not username or not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kullanıcı adı, e-posta ve şifre gerekli"
        )
    
    # Email kontrolü
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu e-posta adresi zaten kullanılıyor"
        )
    
    # Username kontrolü
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu kullanıcı adı zaten kullanılıyor"
        )
    
    # Şifreyi hashle
    password_hash = hash_password(password)
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Kullanıcıyı oluştur
    cursor.execute(
        """
        INSERT INTO users (username, email, password_hash, display_name, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (username, email, password_hash, username, created_at, created_at)
    )
    
    user_id = cursor.lastrowid
    db.commit()
    
    # Token oluştur
    access_token = create_access_token(data={"sub": user_id})
    expires_in = ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # saniye cinsinden
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": {
            "id": user_id,
            "username": username,
            "email": email,
            "display_name": username,
            "avatar_url": None,
            "is_editor": False,
            "created_at": created_at
        }
    }

@router.post("/login")
async def login(credentials: dict, db = Depends(get_db)):
    """
    Kullanıcı girişi
    """
    cursor = db.cursor()
    
    email = credentials.get("email")
    password = credentials.get("password")
    
    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-posta ve şifre gerekli"
        )
    
    # Kullanıcıyı bul
    cursor.execute(
        "SELECT id, username, email, password_hash, display_name, avatar_url, is_editor, is_active, created_at FROM users WHERE email = ?",
        (email,)
    )
    user = cursor.fetchone()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya şifre hatalı"
        )
    
    # Şifre kontrolü
    if not verify_password(password, user[3]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya şifre hatalı"
        )
    
    # Hesap aktif mi?
    if not user[7]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesap devre dışı"
        )
    
    # Token oluştur
    access_token = create_access_token(data={"sub": user[0]})
    expires_in = ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": {
            "id": user[0],
            "username": user[1],
            "email": user[2],
            "display_name": user[4],
            "avatar_url": user[5],
            "is_editor": bool(user[6]),
            "created_at": user[8]
        }
    }

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Mevcut kullanıcı bilgilerini getir
    """
    return current_user

@router.post("/refresh")
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """
    Token yenile
    """
    access_token = create_access_token(data={"sub": current_user["id"]})
    expires_in = ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": current_user
    }