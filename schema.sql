-- =============================================
-- GERÇEK Mİ? - Anket Uygulaması Veritabanı Şeması
-- PostgreSQL için optimize edilmiştir
-- =============================================

-- Kullanıcılar Tablosu
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    avatar_url VARCHAR(500),
    is_editor BOOLEAN DEFAULT FALSE,  -- Editör kullanıcı mı?
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Kategoriler Tablosu
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    icon VARCHAR(10),  -- Emoji ikonu
    color VARCHAR(7),  -- Hex renk kodu
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Anketler Tablosu
CREATE TABLE polls (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id),
    question TEXT NOT NULL,
    gercek_votes INTEGER DEFAULT 0,
    efsane_votes INTEGER DEFAULT 0,
    likes_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,  -- 7 gün sonrası
    
    -- Indexler için
    CONSTRAINT valid_expiry CHECK (expires_at > created_at)
);

-- Oylar Tablosu (Her kullanıcı her ankete 1 kez oy verebilir)
CREATE TABLE votes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    poll_id INTEGER REFERENCES polls(id) ON DELETE CASCADE,
    vote_type VARCHAR(10) NOT NULL CHECK (vote_type IN ('gercek', 'efsane')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Her kullanıcı her ankete sadece 1 oy verebilir
    UNIQUE(user_id, poll_id)
);

-- Beğeniler Tablosu
CREATE TABLE likes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    poll_id INTEGER REFERENCES polls(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Her kullanıcı her anketi sadece 1 kez beğenebilir
    UNIQUE(user_id, poll_id)
);

-- Yorumlar Tablosu
CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    poll_id INTEGER REFERENCES polls(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Günlük Anket Limiti Takibi
CREATE TABLE daily_poll_limits (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    poll_date DATE NOT NULL,
    poll_count INTEGER DEFAULT 1,
    
    -- Her kullanıcı için günlük tek kayıt
    UNIQUE(user_id, poll_date)
);

-- =============================================
-- INDEXLER (Performans için)
-- =============================================

-- Anketler için indexler
CREATE INDEX idx_polls_user_id ON polls(user_id);
CREATE INDEX idx_polls_category_id ON polls(category_id);
CREATE INDEX idx_polls_expires_at ON polls(expires_at);
CREATE INDEX idx_polls_created_at ON polls(created_at DESC);
CREATE INDEX idx_polls_likes_count ON polls(likes_count DESC);
CREATE INDEX idx_polls_is_active ON polls(is_active);

-- Aktif anketleri hızlı çekmek için composite index
CREATE INDEX idx_polls_active_sorted ON polls(is_active, likes_count DESC, created_at DESC) 
    WHERE is_active = TRUE;

-- Editör anketlerini hızlı çekmek için
CREATE INDEX idx_polls_editor ON polls(user_id, created_at DESC) 
    WHERE user_id IN (SELECT id FROM users WHERE is_editor = TRUE);

-- Oylar için indexler
CREATE INDEX idx_votes_poll_id ON votes(poll_id);
CREATE INDEX idx_votes_user_id ON votes(user_id);

-- Beğeniler için indexler
CREATE INDEX idx_likes_poll_id ON likes(poll_id);
CREATE INDEX idx_likes_user_id ON likes(user_id);

-- Yorumlar için indexler
CREATE INDEX idx_comments_poll_id ON comments(poll_id);
CREATE INDEX idx_comments_user_id ON comments(user_id);
CREATE INDEX idx_comments_created_at ON comments(created_at DESC);

-- =============================================
-- VARSAYILAN VERİLER
-- =============================================

-- Kategoriler
INSERT INTO categories (name, icon, color) VALUES
    ('Ekonomi', '💰', '#10b981'),
    ('Teknoloji', '💻', '#6366f1'),
    ('Spor', '⚽', '#f59e0b'),
    ('Siyaset', '🏛️', '#ef4444'),
    ('Eğlence', '🎬', '#ec4899'),
    ('Sağlık', '🏥', '#14b8a6'),
    ('Kripto', '₿', '#f97316'),
    ('Otomotiv', '🚗', '#8b5cf6');

-- Editör kullanıcısı (şifre: editor123 - hash'lenmiş hali)
INSERT INTO users (username, email, password_hash, display_name, is_editor) VALUES
    ('editor', 'editor@gercekmi.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYr.Kj5Yu5Ky', 'Editör', TRUE);

-- =============================================
-- FONKSİYONLAR VE TRİGGERLAR
-- =============================================

-- Anket oy sayısını güncelleme fonksiyonu
CREATE OR REPLACE FUNCTION update_poll_vote_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.vote_type = 'gercek' THEN
            UPDATE polls SET gercek_votes = gercek_votes + 1 WHERE id = NEW.poll_id;
        ELSE
            UPDATE polls SET efsane_votes = efsane_votes + 1 WHERE id = NEW.poll_id;
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        IF OLD.vote_type = 'gercek' THEN
            UPDATE polls SET gercek_votes = gercek_votes - 1 WHERE id = OLD.poll_id;
        ELSE
            UPDATE polls SET efsane_votes = efsane_votes - 1 WHERE id = OLD.poll_id;
        END IF;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_vote_count
AFTER INSERT OR DELETE ON votes
FOR EACH ROW EXECUTE FUNCTION update_poll_vote_count();

-- Beğeni sayısını güncelleme fonksiyonu
CREATE OR REPLACE FUNCTION update_poll_like_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE polls SET likes_count = likes_count + 1 WHERE id = NEW.poll_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE polls SET likes_count = likes_count - 1 WHERE id = OLD.poll_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_like_count
AFTER INSERT OR DELETE ON likes
FOR EACH ROW EXECUTE FUNCTION update_poll_like_count();

-- Yorum sayısını güncelleme fonksiyonu
CREATE OR REPLACE FUNCTION update_poll_comment_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE polls SET comments_count = comments_count + 1 WHERE id = NEW.poll_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE polls SET comments_count = comments_count - 1 WHERE id = OLD.poll_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_comment_count
AFTER INSERT OR DELETE ON comments
FOR EACH ROW EXECUTE FUNCTION update_poll_comment_count();

-- Süresi dolan anketleri otomatik deaktif etme (Cron job ile çalıştırılacak)
CREATE OR REPLACE FUNCTION deactivate_expired_polls()
RETURNS INTEGER AS $$
DECLARE
    affected_rows INTEGER;
BEGIN
    UPDATE polls 
    SET is_active = FALSE 
    WHERE expires_at < CURRENT_TIMESTAMP AND is_active = TRUE;
    
    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    RETURN affected_rows;
END;
$$ LANGUAGE plpgsql;

-- updated_at otomatik güncelleme
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_comments_updated_at
BEFORE UPDATE ON comments
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- GÖRÜNÜMLER (VIEWS)
-- =============================================

-- Aktif anketler görünümü (Anasayfa için)
CREATE VIEW v_active_polls AS
SELECT 
    p.id,
    p.question,
    p.gercek_votes,
    p.efsane_votes,
    p.likes_count,
    p.comments_count,
    p.created_at,
    p.expires_at,
    u.id AS user_id,
    u.username,
    u.display_name,
    u.avatar_url,
    u.is_editor,
    c.id AS category_id,
    c.name AS category_name,
    c.icon AS category_icon,
    -- Kalan süre hesaplama
    EXTRACT(EPOCH FROM (p.expires_at - CURRENT_TIMESTAMP)) AS seconds_left,
    -- Yüzde hesaplama
    CASE 
        WHEN (p.gercek_votes + p.efsane_votes) > 0 
        THEN ROUND((p.gercek_votes::DECIMAL / (p.gercek_votes + p.efsane_votes)) * 100)
        ELSE 50 
    END AS gercek_percentage
FROM polls p
JOIN users u ON p.user_id = u.id
LEFT JOIN categories c ON p.category_id = c.id
WHERE p.is_active = TRUE AND p.expires_at > CURRENT_TIMESTAMP
ORDER BY u.is_editor DESC, p.likes_count DESC, p.created_at DESC;

-- Arşivlenmiş anketler görünümü
CREATE VIEW v_archived_polls AS
SELECT 
    p.id,
    p.question,
    p.gercek_votes,
    p.efsane_votes,
    p.likes_count,
    p.comments_count,
    p.created_at,
    p.expires_at,
    u.id AS user_id,
    u.username,
    u.display_name,
    u.avatar_url,
    u.is_editor,
    c.id AS category_id,
    c.name AS category_name,
    c.icon AS category_icon,
    CASE 
        WHEN (p.gercek_votes + p.efsane_votes) > 0 
        THEN ROUND((p.gercek_votes::DECIMAL / (p.gercek_votes + p.efsane_votes)) * 100)
        ELSE 50 
    END AS gercek_percentage
FROM polls p
JOIN users u ON p.user_id = u.id
LEFT JOIN categories c ON p.category_id = c.id
WHERE p.expires_at <= CURRENT_TIMESTAMP
ORDER BY p.expires_at DESC;
