# =============================================
# VOTTIK - Backend API (Railway için düzenlenmiş)
# =============================================

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import Optional
import hashlib
import sqlite3
import jwt
import os

# JWT ayarları
SECRET_KEY = os.getenv("SECRET_KEY", "vottik-super-secret-key-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Database path
DATABASE_PATH = "vottik.db"

# FastAPI app
app = FastAPI(
    title="Vottik API",
    description="Gerçek mi Efsane mi? Anket API",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================
# DATABASE
# =============================================

def get_db():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            avatar_url TEXT,
            is_editor INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Categories
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            icon TEXT,
            color TEXT
        )
    ''')
    
    # Polls
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS polls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category_id INTEGER,
            question TEXT NOT NULL,
            gercek_votes INTEGER DEFAULT 0,
            efsane_votes INTEGER DEFAULT 0,
            likes_count INTEGER DEFAULT 0,
            comments_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    ''')
    
    # Votes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            poll_id INTEGER,
            vote_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, poll_id)
        )
    ''')
    
    # Likes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            poll_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, poll_id)
        )
    ''')
    
    # Comments
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            poll_id INTEGER,
            content TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Default categories
    categories = [
        ('Ekonomi', '💰', '#10b981'),
        ('Teknoloji', '💻', '#6366f1'),
        ('Spor', '⚽', '#f59e0b'),
        ('Siyaset', '🏛️', '#ef4444'),
        ('Eğlence', '🎬', '#ec4899'),
        ('Sağlık', '🏥', '#14b8a6'),
        ('Kripto', '₿', '#f97316'),
        ('Otomotiv', '🚗', '#8b5cf6'),
    ]
    
    for name, icon, color in categories:
        cursor.execute('INSERT OR IGNORE INTO categories (name, icon, color) VALUES (?, ?, ?)', (name, icon, color))
    
    conn.commit()
    conn.close()

# Initialize DB on startup
init_db()

# =============================================
# HELPERS
# =============================================

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("sub"))
    except:
        return None

def get_current_user(authorization: str = None, db = None):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "")
    user_id = decode_token(token)
    if not user_id:
        return None
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone()

# =============================================
# ROUTES
# =============================================

@app.get("/")
async def root():
    return {"message": "Vottik API 🎯", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# AUTH
@app.post("/api/auth/register")
async def register(data: dict, db = Depends(get_db)):
    cursor = db.cursor()
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    
    if not username or not email or not password:
        raise HTTPException(400, "Tüm alanlar gerekli")
    
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        raise HTTPException(400, "Email zaten kullanılıyor")
    
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        raise HTTPException(400, "Kullanıcı adı zaten kullanılıyor")
    
    password_hash = hash_password(password)
    cursor.execute(
        "INSERT INTO users (username, email, password_hash, display_name) VALUES (?, ?, ?, ?)",
        (username, email, password_hash, username)
    )
    db.commit()
    user_id = cursor.lastrowid
    
    return {
        "access_token": create_token(user_id),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_DAYS * 86400,
        "user": {"id": user_id, "username": username, "email": email, "display_name": username, "is_editor": False}
    }

@app.post("/api/auth/login")
async def login(data: dict, db = Depends(get_db)):
    cursor = db.cursor()
    email = data.get("email")
    password = data.get("password")
    
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    
    if not user or user["password_hash"] != hash_password(password):
        raise HTTPException(401, "Geçersiz email veya şifre")
    
    return {
        "access_token": create_token(user["id"]),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_DAYS * 86400,
        "user": {"id": user["id"], "username": user["username"], "email": user["email"], "display_name": user["display_name"], "is_editor": bool(user["is_editor"])}
    }

# CATEGORIES
@app.get("/api/polls/categories")
async def get_categories(db = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM categories")
    return [dict(row) for row in cursor.fetchall()]

# POLLS
@app.get("/api/polls")
async def get_polls(db = Depends(get_db)):
    cursor = db.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        SELECT p.*, u.username, u.display_name, u.is_editor, c.name as category_name, c.icon as category_icon
        FROM polls p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.expires_at > ?
        ORDER BY u.is_editor DESC, p.likes_count DESC
    """, (now,))
    polls = [dict(row) for row in cursor.fetchall()]
    return {"polls": polls, "total": len(polls), "page": 1, "per_page": 20, "has_next": False, "has_prev": False}

@app.post("/api/polls")
async def create_poll(data: dict, authorization: str = None, db = Depends(get_db)):
    cursor = db.cursor()
    
    if not authorization:
        raise HTTPException(401, "Giriş yapmalısınız")
    
    user = get_current_user(authorization, db)
    if not user:
        raise HTTPException(401, "Geçersiz token")
    
    question = data.get("question")
    category_id = data.get("category_id")
    
    if not question:
        raise HTTPException(400, "Soru gerekli")
    
    expires_at = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        "INSERT INTO polls (user_id, category_id, question, expires_at) VALUES (?, ?, ?, ?)",
        (user["id"], category_id, question, expires_at)
    )
    db.commit()
    
    return {"id": cursor.lastrowid, "question": question, "message": "Anket oluşturuldu"}

# VOTES
@app.post("/api/votes")
async def vote(data: dict, authorization: str = None, db = Depends(get_db)):
    cursor = db.cursor()
    
    if not authorization:
        raise HTTPException(401, "Giriş yapmalısınız")
    
    user = get_current_user(authorization, db)
    if not user:
        raise HTTPException(401, "Geçersiz token")
    
    poll_id = data.get("poll_id")
    vote_type = data.get("vote_type")
    
    # Mevcut oy var mı?
    cursor.execute("SELECT * FROM votes WHERE user_id = ? AND poll_id = ?", (user["id"], poll_id))
    existing = cursor.fetchone()
    
    if existing:
        old_type = existing["vote_type"]
        cursor.execute("UPDATE votes SET vote_type = ? WHERE id = ?", (vote_type, existing["id"]))
        if old_type != vote_type:
            if vote_type == "gercek":
                cursor.execute("UPDATE polls SET gercek_votes = gercek_votes + 1, efsane_votes = efsane_votes - 1 WHERE id = ?", (poll_id,))
            else:
                cursor.execute("UPDATE polls SET efsane_votes = efsane_votes + 1, gercek_votes = gercek_votes - 1 WHERE id = ?", (poll_id,))
    else:
        cursor.execute("INSERT INTO votes (user_id, poll_id, vote_type) VALUES (?, ?, ?)", (user["id"], poll_id, vote_type))
        if vote_type == "gercek":
            cursor.execute("UPDATE polls SET gercek_votes = gercek_votes + 1 WHERE id = ?", (poll_id,))
        else:
            cursor.execute("UPDATE polls SET efsane_votes = efsane_votes + 1 WHERE id = ?", (poll_id,))
    
    db.commit()
    return {"poll_id": poll_id, "vote_type": vote_type, "message": "Oy kaydedildi"}

# LIKES
@app.post("/api/users/like/{poll_id}")
async def like_poll(poll_id: int, authorization: str = None, db = Depends(get_db)):
    cursor = db.cursor()
    
    if not authorization:
        raise HTTPException(401, "Giriş yapmalısınız")
    
    user = get_current_user(authorization, db)
    if not user:
        raise HTTPException(401, "Geçersiz token")
    
    cursor.execute("SELECT id FROM likes WHERE user_id = ? AND poll_id = ?", (user["id"], poll_id))
    if cursor.fetchone():
        raise HTTPException(400, "Zaten beğendiniz")
    
    cursor.execute("INSERT INTO likes (user_id, poll_id) VALUES (?, ?)", (user["id"], poll_id))
    cursor.execute("UPDATE polls SET likes_count = likes_count + 1 WHERE id = ?", (poll_id,))
    db.commit()
    
    return {"message": "Beğenildi"}

@app.delete("/api/users/like/{poll_id}")
async def unlike_poll(poll_id: int, authorization: str = None, db = Depends(get_db)):
    cursor = db.cursor()
    
    if not authorization:
        raise HTTPException(401, "Giriş yapmalısınız")
    
    user = get_current_user(authorization, db)
    if not user:
        raise HTTPException(401, "Geçersiz token")
    
    cursor.execute("DELETE FROM likes WHERE user_id = ? AND poll_id = ?", (user["id"], poll_id))
    cursor.execute("UPDATE polls SET likes_count = likes_count - 1 WHERE id = ?", (poll_id,))
    db.commit()
    
    return {"message": "Beğeni kaldırıldı"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
