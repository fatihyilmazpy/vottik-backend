# =============================================
# Polls Router - Anket İşlemleri (SQLite Uyumlu)
# =============================================

from fastapi import APIRouter, HTTPException, Depends, status, Query
from datetime import datetime, timedelta
from typing import Optional, List

from models.schemas import (
    PollCreate, PollResponse, PollListResponse, MessageResponse
)
from database.connection import get_db
from routers.auth import get_current_user, get_current_user_optional

router = APIRouter()

# Anket süresi (7 gün)
POLL_DURATION_DAYS = 7
# Günlük anket limiti
DAILY_POLL_LIMIT = 2

# =============================================
# YARDIMCI FONKSİYONLAR
# =============================================

def format_poll_response(poll_row, user_vote: str = None, user_liked: bool = False) -> dict:
    """Veritabanı satırını PollResponse formatına çevir"""
    # SQLite Row objesini dict gibi kullan
    if hasattr(poll_row, 'keys'):
        return {
            "id": poll_row["id"],
            "question": poll_row["question"],
            "gercek_votes": poll_row["gercek_votes"],
            "efsane_votes": poll_row["efsane_votes"],
            "likes_count": poll_row["likes_count"],
            "comments_count": poll_row["comments_count"],
            "created_at": poll_row["created_at"],
            "expires_at": poll_row["expires_at"],
            "is_active": bool(poll_row["is_active"]),
            "user_id": poll_row["user_id"],
            "username": poll_row["username"],
            "display_name": poll_row["display_name"],
            "avatar_url": poll_row["avatar_url"],
            "is_editor": bool(poll_row["is_editor"]),
            "category_id": poll_row["category_id"],
            "category_name": poll_row["category_name"],
            "category_icon": poll_row["category_icon"],
            "gercek_percentage": poll_row["gercek_percentage"] if poll_row["gercek_percentage"] else 50,
            "seconds_left": poll_row["seconds_left"],
            "user_vote": user_vote,
            "user_liked": user_liked
        }
    else:
        return {
            "id": poll_row[0],
            "question": poll_row[1],
            "gercek_votes": poll_row[2],
            "efsane_votes": poll_row[3],
            "likes_count": poll_row[4],
            "comments_count": poll_row[5],
            "created_at": poll_row[6],
            "expires_at": poll_row[7],
            "is_active": bool(poll_row[8]),
            "user_id": poll_row[9],
            "username": poll_row[10],
            "display_name": poll_row[11],
            "avatar_url": poll_row[12],
            "is_editor": bool(poll_row[13]),
            "category_id": poll_row[14],
            "category_name": poll_row[15],
            "category_icon": poll_row[16],
            "gercek_percentage": poll_row[17] if poll_row[17] else 50,
            "seconds_left": poll_row[18],
            "user_vote": user_vote,
            "user_liked": user_liked
        }

def check_daily_limit(cursor, user_id: int) -> int:
    """Kullanıcının günlük anket limitini kontrol et, kalan hakkı döndür"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute(
        "SELECT poll_count FROM daily_poll_limits WHERE user_id = ? AND poll_date = ?",
        (user_id, today)
    )
    result = cursor.fetchone()
    
    if result:
        return max(0, DAILY_POLL_LIMIT - result[0])
    return DAILY_POLL_LIMIT

def increment_daily_count(cursor, user_id: int):
    """Günlük anket sayısını artır"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute(
        """
        INSERT INTO daily_poll_limits (user_id, poll_date, poll_count)
        VALUES (?, ?, 1)
        ON CONFLICT (user_id, poll_date) 
        DO UPDATE SET poll_count = poll_count + 1
        """,
        (user_id, today)
    )

# =============================================
# API ENDPOINTS
# =============================================

@router.get("", response_model=PollListResponse)
async def get_polls(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = None,
    include_archived: bool = False,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db = Depends(get_db)
):
    """
    Anketleri listele
    """
    cursor = db.cursor()
    offset = (page - 1) * per_page
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Base query - SQLite uyumlu
    base_query = """
        SELECT 
            p.id, p.question, p.gercek_votes, p.efsane_votes,
            p.likes_count, p.comments_count, p.created_at, p.expires_at, p.is_active,
            u.id as user_id, u.username, u.display_name, u.avatar_url, u.is_editor,
            c.id as category_id, c.name as category_name, c.icon as category_icon,
            CASE 
                WHEN (p.gercek_votes + p.efsane_votes) > 0 
                THEN ROUND((CAST(p.gercek_votes AS FLOAT) / (p.gercek_votes + p.efsane_votes)) * 100)
                ELSE 50 
            END AS gercek_percentage,
            (julianday(p.expires_at) - julianday(?)) * 86400 AS seconds_left
        FROM polls p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE 1=1
    """
    
    params = [now]
    
    # Arşiv filtresi
    if not include_archived:
        base_query += " AND p.expires_at > ?"
        params.append(now)
    
    # Kategori filtresi
    if category_id:
        base_query += " AND p.category_id = ?"
        params.append(category_id)
    
    # Toplam sayı
    count_query = f"SELECT COUNT(*) FROM ({base_query})"
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]
    
    # Sıralama ve pagination
    base_query += """
        ORDER BY u.is_editor DESC, p.likes_count DESC, p.created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([per_page, offset])
    
    cursor.execute(base_query, params)
    polls_raw = cursor.fetchall()
    
    # Kullanıcı oyları ve beğenileri
    user_votes = {}
    user_likes = set()
    
    if current_user and polls_raw:
        poll_ids = [p[0] for p in polls_raw]
        placeholders = ','.join('?' * len(poll_ids))
        
        # Oylar
        cursor.execute(
            f"SELECT poll_id, vote_type FROM votes WHERE user_id = ? AND poll_id IN ({placeholders})",
            [current_user["id"]] + poll_ids
        )
        user_votes = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Beğeniler
        cursor.execute(
            f"SELECT poll_id FROM likes WHERE user_id = ? AND poll_id IN ({placeholders})",
            [current_user["id"]] + poll_ids
        )
        user_likes = {row[0] for row in cursor.fetchall()}
    
    # Response oluştur
    polls = [
        format_poll_response(
            poll,
            user_vote=user_votes.get(poll[0]),
            user_liked=poll[0] in user_likes
        )
        for poll in polls_raw
    ]
    
    return PollListResponse(
        polls=polls,
        total=total,
        page=page,
        per_page=per_page,
        has_next=offset + per_page < total,
        has_prev=page > 1
    )

@router.get("/trending")
async def get_trending_polls(
    limit: int = Query(10, ge=1, le=50),
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db = Depends(get_db)
):
    """
    Trend anketleri getir
    """
    cursor = db.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute(
        """
        SELECT 
            p.id, p.question, p.gercek_votes, p.efsane_votes,
            p.likes_count, p.comments_count, p.created_at, p.expires_at, p.is_active,
            u.id as user_id, u.username, u.display_name, u.avatar_url, u.is_editor,
            c.id as category_id, c.name as category_name, c.icon as category_icon,
            CASE 
                WHEN (p.gercek_votes + p.efsane_votes) > 0 
                THEN ROUND((CAST(p.gercek_votes AS FLOAT) / (p.gercek_votes + p.efsane_votes)) * 100)
                ELSE 50 
            END AS gercek_percentage,
            (julianday(p.expires_at) - julianday(?)) * 86400 AS seconds_left
        FROM polls p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.expires_at > ?
        ORDER BY (p.gercek_votes + p.efsane_votes + p.likes_count) DESC
        LIMIT ?
        """,
        (now, now, limit)
    )
    
    polls_raw = cursor.fetchall()
    return [format_poll_response(poll) for poll in polls_raw]

@router.get("/ending-soon")
async def get_ending_soon_polls(
    limit: int = Query(10, ge=1, le=50),
    db = Depends(get_db)
):
    """
    Süresi yakında dolacak anketleri getir
    """
    cursor = db.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    tomorrow = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute(
        """
        SELECT 
            p.id, p.question, p.gercek_votes, p.efsane_votes,
            p.likes_count, p.comments_count, p.created_at, p.expires_at, p.is_active,
            u.id as user_id, u.username, u.display_name, u.avatar_url, u.is_editor,
            c.id as category_id, c.name as category_name, c.icon as category_icon,
            CASE 
                WHEN (p.gercek_votes + p.efsane_votes) > 0 
                THEN ROUND((CAST(p.gercek_votes AS FLOAT) / (p.gercek_votes + p.efsane_votes)) * 100)
                ELSE 50 
            END AS gercek_percentage,
            (julianday(p.expires_at) - julianday(?)) * 86400 AS seconds_left
        FROM polls p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.expires_at > ? AND p.expires_at < ?
        ORDER BY p.expires_at ASC
        LIMIT ?
        """,
        (now, now, tomorrow, limit)
    )
    
    polls_raw = cursor.fetchall()
    return [format_poll_response(poll) for poll in polls_raw]

@router.get("/categories")
async def get_categories(db = Depends(get_db)):
    """
    Tüm kategorileri getir
    """
    cursor = db.cursor()
    cursor.execute("SELECT id, name, icon, color FROM categories ORDER BY name")
    
    return [
        {"id": row[0], "name": row[1], "icon": row[2], "color": row[3]}
        for row in cursor.fetchall()
    ]

@router.get("/my-limit")
async def get_my_poll_limit(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Kullanıcının kalan günlük anket hakkını getir
    """
    cursor = db.cursor()
    remaining = check_daily_limit(cursor, current_user["id"])
    
    return {
        "daily_limit": DAILY_POLL_LIMIT,
        "remaining": remaining,
        "used": DAILY_POLL_LIMIT - remaining
    }

@router.get("/{poll_id}", response_model=PollResponse)
async def get_poll(
    poll_id: int,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db = Depends(get_db)
):
    """
    Tek bir anketi getir
    """
    cursor = db.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute(
        """
        SELECT 
            p.id, p.question, p.gercek_votes, p.efsane_votes,
            p.likes_count, p.comments_count, p.created_at, p.expires_at, p.is_active,
            u.id as user_id, u.username, u.display_name, u.avatar_url, u.is_editor,
            c.id as category_id, c.name as category_name, c.icon as category_icon,
            CASE 
                WHEN (p.gercek_votes + p.efsane_votes) > 0 
                THEN ROUND((CAST(p.gercek_votes AS FLOAT) / (p.gercek_votes + p.efsane_votes)) * 100)
                ELSE 50 
            END AS gercek_percentage,
            (julianday(p.expires_at) - julianday(?)) * 86400 AS seconds_left
        FROM polls p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.id = ?
        """,
        (now, poll_id)
    )
    
    poll = cursor.fetchone()
    
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anket bulunamadı"
        )
    
    # Kullanıcı oyu ve beğenisi
    user_vote = None
    user_liked = False
    
    if current_user:
        cursor.execute(
            "SELECT vote_type FROM votes WHERE user_id = ? AND poll_id = ?",
            (current_user["id"], poll_id)
        )
        vote_result = cursor.fetchone()
        if vote_result:
            user_vote = vote_result[0]
        
        cursor.execute(
            "SELECT id FROM likes WHERE user_id = ? AND poll_id = ?",
            (current_user["id"], poll_id)
        )
        user_liked = cursor.fetchone() is not None
    
    return format_poll_response(poll, user_vote=user_vote, user_liked=user_liked)

@router.post("", response_model=PollResponse, status_code=status.HTTP_201_CREATED)
async def create_poll(
    poll_data: PollCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Yeni anket oluştur
    """
    cursor = db.cursor()
    
    # Editör değilse günlük limiti kontrol et
    if not current_user.get("is_editor"):
        remaining = check_daily_limit(cursor, current_user["id"])
        if remaining <= 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Günlük anket limitinizi doldurdunuz. Yarın tekrar deneyin."
            )
    
    # Kategori kontrolü
    cursor.execute("SELECT id FROM categories WHERE id = ?", (poll_data.category_id,))
    if not cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz kategori"
        )
    
    # Anketi oluştur
    expires_at = (datetime.now() + timedelta(days=POLL_DURATION_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute(
        """
        INSERT INTO polls (user_id, category_id, question, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (current_user["id"], poll_data.category_id, poll_data.question, expires_at, created_at)
    )
    
    poll_id = cursor.lastrowid
    
    # Günlük sayacı artır (editör değilse)
    if not current_user.get("is_editor"):
        increment_daily_count(cursor, current_user["id"])
    
    db.commit()
    
    # Kategori bilgisini al
    cursor.execute("SELECT id, name, icon FROM categories WHERE id = ?", (poll_data.category_id,))
    category = cursor.fetchone()
    
    return {
        "id": poll_id,
        "question": poll_data.question,
        "gercek_votes": 0,
        "efsane_votes": 0,
        "likes_count": 0,
        "comments_count": 0,
        "created_at": created_at,
        "expires_at": expires_at,
        "is_active": True,
        "user_id": current_user["id"],
        "username": current_user["username"],
        "display_name": current_user["display_name"],
        "avatar_url": current_user["avatar_url"],
        "is_editor": current_user["is_editor"],
        "category_id": category[0],
        "category_name": category[1],
        "category_icon": category[2],
        "gercek_percentage": 50,
        "seconds_left": POLL_DURATION_DAYS * 24 * 60 * 60,
        "user_vote": None,
        "user_liked": False
    }

@router.delete("/{poll_id}", response_model=MessageResponse)
async def delete_poll(
    poll_id: int,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Anketi sil
    """
    cursor = db.cursor()
    
    # Anketi bul
    cursor.execute("SELECT user_id FROM polls WHERE id = ?", (poll_id,))
    poll = cursor.fetchone()
    
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anket bulunamadı"
        )
    
    # Yetki kontrolü
    if poll[0] != current_user["id"] and not current_user.get("is_editor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu anketi silme yetkiniz yok"
        )
    
    # Sil
    cursor.execute("DELETE FROM polls WHERE id = ?", (poll_id,))
    db.commit()
    
    return MessageResponse(message="Anket başarıyla silindi")