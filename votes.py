# =============================================
# Votes Router - Oy İşlemleri (SQLite Uyumlu)
# =============================================

from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime
from typing import Optional

from models.schemas import VoteCreate, VoteResponse, MessageResponse
from database.connection import get_db
from routers.auth import get_current_user

router = APIRouter()

# =============================================
# API ENDPOINTS
# =============================================

@router.post("", response_model=VoteResponse)
async def vote(
    vote_data: VoteCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Ankete oy ver
    
    - **poll_id**: Anket ID'si
    - **vote_type**: "gercek" veya "efsane"
    
    Kullanıcı oyunu değiştirebilir.
    """
    cursor = db.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Anket var mı ve aktif mi kontrol et
    cursor.execute(
        "SELECT id, expires_at, gercek_votes, efsane_votes FROM polls WHERE id = ?",
        (vote_data.poll_id,)
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
    
    # Daha önce oy vermiş mi?
    cursor.execute(
        "SELECT id, vote_type FROM votes WHERE user_id = ? AND poll_id = ?",
        (current_user["id"], vote_data.poll_id)
    )
    existing_vote = cursor.fetchone()
    
    if existing_vote:
        old_vote_type = existing_vote[1]
        
        # Aynı oyu tekrar veriyorsa
        if old_vote_type == vote_data.vote_type:
            return VoteResponse(
                poll_id=vote_data.poll_id,
                vote_type=vote_data.vote_type,
                message="Zaten bu şekilde oy vermişsiniz"
            )
        
        # Oyu değiştir
        cursor.execute(
            "UPDATE votes SET vote_type = ? WHERE id = ?",
            (vote_data.vote_type, existing_vote[0])
        )
        
        # Anket sayaçlarını güncelle
        if vote_data.vote_type == "gercek":
            cursor.execute(
                "UPDATE polls SET gercek_votes = gercek_votes + 1, efsane_votes = efsane_votes - 1 WHERE id = ?",
                (vote_data.poll_id,)
            )
        else:
            cursor.execute(
                "UPDATE polls SET efsane_votes = efsane_votes + 1, gercek_votes = gercek_votes - 1 WHERE id = ?",
                (vote_data.poll_id,)
            )
        
        db.commit()
        
        return VoteResponse(
            poll_id=vote_data.poll_id,
            vote_type=vote_data.vote_type,
            message="Oyunuz değiştirildi"
        )
    
    # Yeni oy
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        "INSERT INTO votes (user_id, poll_id, vote_type, created_at) VALUES (?, ?, ?, ?)",
        (current_user["id"], vote_data.poll_id, vote_data.vote_type, created_at)
    )
    
    # Anket sayacını güncelle
    if vote_data.vote_type == "gercek":
        cursor.execute(
            "UPDATE polls SET gercek_votes = gercek_votes + 1 WHERE id = ?",
            (vote_data.poll_id,)
        )
    else:
        cursor.execute(
            "UPDATE polls SET efsane_votes = efsane_votes + 1 WHERE id = ?",
            (vote_data.poll_id,)
        )
    
    db.commit()
    
    return VoteResponse(
        poll_id=vote_data.poll_id,
        vote_type=vote_data.vote_type,
        message="Oyunuz kaydedildi"
    )

@router.delete("/{poll_id}", response_model=MessageResponse)
async def remove_vote(
    poll_id: int,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Oyu geri çek
    """
    cursor = db.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Anket var mı ve aktif mi?
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
    
    if poll[1] < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu anketin süresi dolmuş"
        )
    
    # Oy var mı?
    cursor.execute(
        "SELECT id, vote_type FROM votes WHERE user_id = ? AND poll_id = ?",
        (current_user["id"], poll_id)
    )
    vote = cursor.fetchone()
    
    if not vote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu ankete oy vermemişsiniz"
        )
    
    # Oyu sil
    cursor.execute(
        "DELETE FROM votes WHERE id = ?",
        (vote[0],)
    )
    
    # Sayacı güncelle
    if vote[1] == "gercek":
        cursor.execute(
            "UPDATE polls SET gercek_votes = gercek_votes - 1 WHERE id = ?",
            (poll_id,)
        )
    else:
        cursor.execute(
            "UPDATE polls SET efsane_votes = efsane_votes - 1 WHERE id = ?",
            (poll_id,)
        )
    
    db.commit()
    
    return MessageResponse(message="Oyunuz geri çekildi")

@router.get("/{poll_id}/my-vote")
async def get_my_vote(
    poll_id: int,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Kullanıcının bu anketteki oyunu getir
    """
    cursor = db.cursor()
    
    cursor.execute(
        "SELECT vote_type, created_at FROM votes WHERE user_id = ? AND poll_id = ?",
        (current_user["id"], poll_id)
    )
    vote = cursor.fetchone()
    
    if not vote:
        return {"vote_type": None, "voted_at": None}
    
    return {
        "vote_type": vote[0],
        "voted_at": vote[1]
    }