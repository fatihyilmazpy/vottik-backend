# =============================================
# Comments Router - Yorum İşlemleri (SQLite Uyumlu)
# =============================================

from fastapi import APIRouter, HTTPException, Depends, status, Query
from datetime import datetime
from typing import Optional

from models.schemas import CommentCreate, CommentResponse, CommentListResponse, MessageResponse
from database.connection import get_db
from routers.auth import get_current_user, get_current_user_optional

router = APIRouter()

# =============================================
# API ENDPOINTS
# =============================================

@router.get("/poll/{poll_id}", response_model=CommentListResponse)
async def get_comments(
    poll_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db = Depends(get_db)
):
    """
    Anketin yorumlarını getir
    """
    cursor = db.cursor()
    offset = (page - 1) * per_page
    
    # Anket var mı?
    cursor.execute("SELECT id FROM polls WHERE id = ?", (poll_id,))
    if not cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anket bulunamadı"
        )
    
    # Toplam yorum sayısı
    cursor.execute(
        "SELECT COUNT(*) FROM comments WHERE poll_id = ? AND is_active = 1",
        (poll_id,)
    )
    total = cursor.fetchone()[0]
    
    # Yorumları getir
    cursor.execute(
        """
        SELECT 
            c.id, c.content, c.created_at, c.updated_at,
            u.id, u.username, u.display_name, u.avatar_url, u.is_editor
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.poll_id = ? AND c.is_active = 1
        ORDER BY c.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (poll_id, per_page, offset)
    )
    
    comments_raw = cursor.fetchall()
    
    comments = [
        {
            "id": row[0],
            "content": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "user_id": row[4],
            "username": row[5],
            "display_name": row[6],
            "avatar_url": row[7],
            "is_editor": bool(row[8]),
            "is_own": current_user["id"] == row[4] if current_user else False
        }
        for row in comments_raw
    ]
    
    return CommentListResponse(
        comments=comments,
        total=total,
        page=page,
        per_page=per_page,
        has_next=offset + per_page < total,
        has_prev=page > 1
    )

@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    comment_data: CommentCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Yorum yap
    """
    cursor = db.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Anket var mı ve aktif mi?
    cursor.execute(
        "SELECT id, expires_at FROM polls WHERE id = ?",
        (comment_data.poll_id,)
    )
    poll = cursor.fetchone()
    
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anket bulunamadı"
        )
    
    if poll[1] < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu anketin süresi dolmuş, yorum yapılamaz"
        )
    
    # Yorumu oluştur
    cursor.execute(
        """
        INSERT INTO comments (user_id, poll_id, content, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (current_user["id"], comment_data.poll_id, comment_data.content, now, now)
    )
    
    comment_id = cursor.lastrowid
    
    # Anket yorum sayısını güncelle
    cursor.execute(
        "UPDATE polls SET comments_count = comments_count + 1 WHERE id = ?",
        (comment_data.poll_id,)
    )
    
    db.commit()
    
    return {
        "id": comment_id,
        "content": comment_data.content,
        "created_at": now,
        "updated_at": now,
        "user_id": current_user["id"],
        "username": current_user["username"],
        "display_name": current_user["display_name"],
        "avatar_url": current_user["avatar_url"],
        "is_editor": current_user["is_editor"],
        "is_own": True
    }

@router.put("/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int,
    content: str = Query(..., min_length=1, max_length=1000),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Yorumu düzenle (sadece kendi yorumu)
    """
    cursor = db.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Yorum var mı?
    cursor.execute(
        """
        SELECT c.id, c.user_id, c.poll_id, c.created_at,
               u.username, u.display_name, u.avatar_url, u.is_editor
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = ? AND c.is_active = 1
        """,
        (comment_id,)
    )
    comment = cursor.fetchone()
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Yorum bulunamadı"
        )
    
    # Yetki kontrolü
    if comment[1] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu yorumu düzenleme yetkiniz yok"
        )
    
    # Güncelle
    cursor.execute(
        "UPDATE comments SET content = ?, updated_at = ? WHERE id = ?",
        (content, now, comment_id)
    )
    
    db.commit()
    
    return {
        "id": comment_id,
        "content": content,
        "created_at": comment[3],
        "updated_at": now,
        "user_id": comment[1],
        "username": comment[4],
        "display_name": comment[5],
        "avatar_url": comment[6],
        "is_editor": bool(comment[7]),
        "is_own": True
    }

@router.delete("/{comment_id}", response_model=MessageResponse)
async def delete_comment(
    comment_id: int,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Yorumu sil (soft delete)
    """
    cursor = db.cursor()
    
    # Yorum var mı?
    cursor.execute(
        "SELECT id, user_id, poll_id FROM comments WHERE id = ? AND is_active = 1",
        (comment_id,)
    )
    comment = cursor.fetchone()
    
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Yorum bulunamadı"
        )
    
    # Yetki kontrolü (kendi yorumu veya editör)
    if comment[1] != current_user["id"] and not current_user.get("is_editor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu yorumu silme yetkiniz yok"
        )
    
    # Soft delete
    cursor.execute(
        "UPDATE comments SET is_active = 0 WHERE id = ?",
        (comment_id,)
    )
    
    # Anket yorum sayısını güncelle
    cursor.execute(
        "UPDATE polls SET comments_count = comments_count - 1 WHERE id = ?",
        (comment[2],)
    )
    
    db.commit()
    
    return MessageResponse(message="Yorum silindi")