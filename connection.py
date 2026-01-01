# =============================================
# Veritabanı Bağlantı Yönetimi - SQLite (Thread-Safe)
# =============================================

import os
import sqlite3
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

# SQLite veritabanı dosyası
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "gercekmi.db")

def get_connection():
    """Veritabanı bağlantısı oluştur (thread-safe)"""
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Dict-like erişim
    return conn

def get_db():
    """FastAPI dependency için veritabanı bağlantısı"""
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

@contextmanager
def get_db_cursor(dict_cursor=True):
    """Context manager ile cursor al"""
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def create_tables():
    """Tabloları oluştur"""
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    cursor = conn.cursor()
    
    # Users tablosu
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Categories tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            icon TEXT,
            color TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Polls tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS polls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            category_id INTEGER REFERENCES categories(id),
            question TEXT NOT NULL,
            gercek_votes INTEGER DEFAULT 0,
            efsane_votes INTEGER DEFAULT 0,
            likes_count INTEGER DEFAULT 0,
            comments_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        )
    ''')
    
    # Votes tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            poll_id INTEGER REFERENCES polls(id),
            vote_type TEXT NOT NULL CHECK (vote_type IN ('gercek', 'efsane')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, poll_id)
        )
    ''')
    
    # Likes tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            poll_id INTEGER REFERENCES polls(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, poll_id)
        )
    ''')
    
    # Comments tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            poll_id INTEGER REFERENCES polls(id),
            content TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Daily poll limits tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_poll_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            poll_date DATE NOT NULL,
            poll_count INTEGER DEFAULT 1,
            UNIQUE(user_id, poll_date)
        )
    ''')
    
    # Varsayılan kategorileri ekle
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
        cursor.execute('''
            INSERT OR IGNORE INTO categories (name, icon, color) VALUES (?, ?, ?)
        ''', (name, icon, color))
    
    # Editör kullanıcısı ekle (şifre: editor123)
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, email, password_hash, display_name, is_editor)
        VALUES (?, ?, ?, ?, ?)
    ''', ('editor', 'editor@gercekmi.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYr.Kj5Yu5Ky', 'Editör', 1))
    
    conn.commit()
    conn.close()
    print("✅ Veritabanı tabloları oluşturuldu")

def test_connection():
    """Bağlantıyı test et"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        print("✅ Veritabanı bağlantısı başarılı")
        return True
    except Exception as e:
        print(f"❌ Veritabanı bağlantı hatası: {e}")
        return False

if __name__ == "__main__":
    test_connection()
    create_tables()