# =============================================
# Users Router - Kullanıcı İşlemleri (SQLite Uyumlu)
# =============================================

from fastapi import APIRouter, HTTPException, Depends, status, Query
from datetime import datetime
from typing import Optional

from models.schemas import UserProfile, MessageResponse, PollListResponse
from database.connection import get_db
from routers.auth import get_current_user, get_current_user_optional

router = APIRouter()

# =============================================
# API ENDPOINTS
# =============================================

@router.get("/{username}", response_model=UserProfile)
async def get_user_profile(
    username: str,
    db = Depends(get_db)
):
    """
    Kullanıcı profilini getir
    """
    cursor = db.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Kullanıcıyı bul
    cursor.execute(
        """
        SELECT id, username, display_name, avatar_url, is_editor, created_at
        FROM users 
        WHERE username = ? AND is_active = 1
        """,
        (username,)
    )
    user = cursor.fetchone()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı"
        )
    
    user_id = user[0]
    
    # Toplam anket sayısı
    cursor.execute(
        "SELECT COUNT(*) FROM polls WHERE user_id = ?",
        (user_id,)
    )
    total_polls = cursor.fetchone()[0]
    
    # Aktif anket sayısı
    cursor.execute(
        "SELECT COUNT(*) FROM polls WHERE user_id = ? AND expires_at > ?",
        (user_id, now)
    )
    active_polls = cursor.fetchone()[0]
    
    # Toplam aldığı oy sayısı
    cursor.execute(
        """
        SELECT COALESCE(SUM(gercek_votes + efsane_votes), 0) 
        FROM polls WHERE user_id = ?
        """,
        (user_id,)
    )
    total_votes_received = cursor.fetchone()[0]
    
    # Toplam aldığı beğeni sayısı
    cursor.execute(
        "SELECT COALESCE(SUM(likes_count), 0) FROM polls WHERE user_id = ?",
        (user_id,)
    )
    total_likes_received = cursor.fetchone()[0]
    
    return {
        "id": user[0],
        "username": user[1],
        "display_name": user[2],
        "avatar_url": user[3],
        "is_editor": bool(user[4]),
        "created_at": user[5],
        "total_polls": total_polls,
        "active_polls": active_polls,
        "archived_polls": total_polls - active_polls,
        "total_votes_received": total_votes_received,
        "total_likes_received": total_likes_received
    }

@router.get("/{username}/polls", response_model=PollListResponse)
async def get_user_polls(
    username: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, pattern="^(active|archived)$"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db = Depends(get_db)
):
    """
    Kullanıcının anketlerini getir
    """
    cursor = db.cursor()
    offset = (page - 1) * per_page
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Kullanıcıyı bul
    cursor.execute(
        "SELECT id FROM users WHERE username = ? AND is_active = 1",
        (username,)
    )
    user = cursor.fetchone()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı"
        )
    
    user_id = user[0]
    
    # Base query
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
        WHERE p.user_id = ?
    """
    
    params = [now, user_id]
    
    # Status filtresi
    if status_filter == "active":
        base_query += " AND p.expires_at > ?"
        params.append(now)
    elif status_filter == "archived":
        base_query += " AND p.expires_at <= ?"
        params.append(now)
    
    # Toplam sayı
    count_query = f"SELECT COUNT(*) FROM ({base_query})"
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]
    
    # Sıralama ve pagination
    base_query += " ORDER BY p.created_at DESC LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    
    cursor.execute(base_query, params)
    polls_raw = cursor.fetchall()
    
    # Kullanıcı oyları ve beğenileri
    user_votes = {}
    user_likes = set()
    
    if current_user and polls_raw:
        poll_ids = [p[0] for p in polls_raw]
        placeholders = ','.join('?' * len(poll_ids))
        
        cursor.execute(
            f"SELECT poll_id, vote_type FROM votes WHERE user_id = ? AND poll_id IN ({placeholders})",
            [current_user["id"]] + poll_ids
        )
        user_votes = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute(
            f"SELECT poll_id FROM likes WHERE user_id = ? AND poll_id IN ({placeholders})",
            [current_user["id"]] + poll_ids
        )
        user_likes = {row[0] for row in cursor.fetchall()}
    
    polls = [
        {
            "id": poll[0],
            "question": poll[1],
            "gercek_votes": poll[2],
            "efsane_votes": poll[3],
            "likes_count": poll[4],
            "comments_count": poll[5],
            "created_at": poll[6],
            "expires_at": poll[7],
            "is_active": bool(poll[8]),
            "user_id": poll[9],
            "username": poll[10],
            "display_name": poll[11],
            "avatar_url": poll[12],
            "is_editor": bool(poll[13]),
            "category_id": poll[14],
            "category_name": poll[15],
            "category_icon": poll[16],
            "gercek_percentage": poll[17] if poll[17] else 50,
            "seconds_left": poll[18],
            "user_vote": user_votes.get(poll[0]),
            "user_liked": poll[0] in user_likes
        }
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

@router.post("/like/{poll_id}", response_model=MessageResponse)
async def like_poll(
    poll_id: int,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Anketi beğen
    """
    cursor = db.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Anket var mı?
    cursor.execute(
        "SELECT id, expires_at FROM polls WHERE id = ?",
        (poll_id,)
    )
    poll = cursor.fetchone()
    
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anket bulunamadı"
        )
    
    # Süre dolmuş mu?
    if poll[1] < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu anketin süresi dolmuş"
        )
    
    # Zaten beğenmiş mi?
    cursor.execute(
        "SELECT id FROM likes WHERE user_id = ? AND poll_id = ?",
        (current_user["id"], poll_id)
    )
    if cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu anketi zaten beğenmişsiniz"
        )
    
    # Beğeni ekle
    cursor.execute(
        "INSERT INTO likes (user_id, poll_id, created_at) VALUES (?, ?, ?)",
        (current_user["id"], poll_id, now)
    )
    
    # Sayacı güncelle
    cursor.execute(
        "UPDATE polls SET likes_count = likes_count + 1 WHERE id = ?",
        (poll_id,)
    )
    
    db.commit()
    
    return MessageResponse(message="Anket beğenildi")

@router.delete("/like/{poll_id}", response_model=MessageResponse)
async def unlike_poll(
    poll_id: int,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Beğeniyi kaldır
    """
    cursor = db.cursor()
    
    # Beğeni var mı?
    cursor.execute(
        "SELECT id FROM likes WHERE user_id = ? AND poll_id = ?",
        (current_user["id"], poll_id)
    )
    like = cursor.fetchone()
    
    if not like:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu anketi beğenmemişsiniz"
        )
    
    # Beğeniyi sil
    cursor.execute(
        "DELETE FROM likes WHERE id = ?",
        (like[0],)
    )
    
    # Sayacı güncelle
    cursor.execute(
        "UPDATE polls SET likes_count = likes_count - 1 WHERE id = ?",
        (poll_id,)
    )
    
    db.commit()
    
    return MessageResponse(message="Beğeni kaldırıldı")

@router.put("/me/profile", response_model=MessageResponse)
async def update_profile(
    display_name: Optional[str] = Query(None, max_length=100),
    avatar_url: Optional[str] = Query(None, max_length=500),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Profil güncelle
    """
    cursor = db.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    updates = []
    params = []
    
    if display_name is not None:
        updates.append("display_name = ?")
        params.append(display_name)
    
    if avatar_url is not None:
        updates.append("avatar_url = ?")
        params.append(avatar_url)
    
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Güncellenecek alan belirtilmedi"
        )
    
    updates.append("updated_at = ?")
    params.append(now)
    params.append(current_user["id"])
    
    query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    
    db.commit()
    
    return MessageResponse(message="Profil güncellendi")