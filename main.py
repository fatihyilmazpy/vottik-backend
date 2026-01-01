# =============================================
# GERÇEK Mİ? - Backend API
# FastAPI ile geliştirilmiştir
# =============================================

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import uvicorn

# Routers
from routers import auth, polls, votes, comments, users

# Database
from database.connection import create_tables, get_db

# Lifespan event handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Tabloları oluştur
    print("🚀 Uygulama başlatılıyor...")
    create_tables()
    print("✅ Veritabanı tabloları hazır")
    yield
    # Shutdown
    print("👋 Uygulama kapatılıyor...")

# FastAPI uygulaması
app = FastAPI(
    title="Gerçek mi? API",
    description="Anket uygulaması backend API'si",
    version="1.0.0",
    lifespan=lifespan
)

# CORS ayarları (Frontend'in erişimi için)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da spesifik domain yazılmalı
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları ekle
app.include_router(auth.router, prefix="/api/auth", tags=["Kimlik Doğrulama"])
app.include_router(polls.router, prefix="/api/polls", tags=["Anketler"])
app.include_router(votes.router, prefix="/api/votes", tags=["Oylar"])
app.include_router(comments.router, prefix="/api/comments", tags=["Yorumlar"])
app.include_router(users.router, prefix="/api/users", tags=["Kullanıcılar"])

# Ana endpoint
@app.get("/")
async def root():
    return {
        "message": "Gerçek mi? API'sine hoş geldiniz! 🎯",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "auth": "/api/auth",
            "polls": "/api/polls",
            "votes": "/api/votes",
            "comments": "/api/comments",
            "users": "/api/users"
        }
    }

# Sağlık kontrolü
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

# Uygulama istatistikleri
@app.get("/api/stats")
async def get_stats(db = Depends(get_db)):
    cursor = db.cursor()
    
    # Toplam kullanıcı sayısı
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
    total_users = cursor.fetchone()[0]
    
    # Toplam anket sayısı
    cursor.execute("SELECT COUNT(*) FROM polls")
    total_polls = cursor.fetchone()[0]
    
    # Aktif anket sayısı
    cursor.execute("SELECT COUNT(*) FROM polls WHERE is_active = TRUE AND expires_at > NOW()")
    active_polls = cursor.fetchone()[0]
    
    # Toplam oy sayısı
    cursor.execute("SELECT COUNT(*) FROM votes")
    total_votes = cursor.fetchone()[0]
    
    # Bugünkü anket sayısı
    cursor.execute("SELECT COUNT(*) FROM polls WHERE DATE(created_at) = CURRENT_DATE")
    today_polls = cursor.fetchone()[0]
    
    return {
        "total_users": total_users,
        "total_polls": total_polls,
        "active_polls": active_polls,
        "archived_polls": total_polls - active_polls,
        "total_votes": total_votes,
        "today_polls": today_polls
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
