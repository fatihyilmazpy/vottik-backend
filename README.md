# 🎯 Gerçek mi? - Backend API

Anket uygulaması için Python FastAPI backend servisi.

## 📁 Proje Yapısı

```
backend/
├── main.py                 # Ana uygulama dosyası
├── requirements.txt        # Python bağımlılıkları
├── .env.example           # Ortam değişkenleri örneği
├── database/
│   ├── __init__.py
│   ├── connection.py      # Veritabanı bağlantı yönetimi
│   └── schema.sql         # Veritabanı şeması
├── models/
│   ├── __init__.py
│   └── schemas.py         # Pydantic modelleri
└── routers/
    ├── __init__.py
    ├── auth.py            # Kimlik doğrulama (kayıt/giriş)
    ├── polls.py           # Anket işlemleri
    ├── votes.py           # Oylama işlemleri
    ├── comments.py        # Yorum işlemleri
    └── users.py           # Kullanıcı/profil işlemleri
```

## 🚀 Kurulum

### 1. PostgreSQL Kurulumu

```bash
# macOS
brew install postgresql
brew services start postgresql

# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql

# Windows
# https://www.postgresql.org/download/windows/ adresinden indirin
```

### 2. Veritabanı Oluşturma

```bash
# PostgreSQL'e bağlan
psql -U postgres

# Veritabanı oluştur
CREATE DATABASE gercekmi_db;

# Çıkış
\q
```

### 3. Python Ortamı

```bash
# Proje klasörüne git
cd backend

# Virtual environment oluştur
python -m venv venv

# Aktif et
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Bağımlılıkları yükle
pip install -r requirements.txt
```

### 4. Ortam Değişkenlerini Ayarla

```bash
# .env dosyası oluştur
cp .env.example .env

# .env dosyasını düzenle ve şifreleri gir
nano .env
```

### 5. Veritabanı Şemasını Yükle

```bash
# PostgreSQL'e şemayı yükle
psql -U postgres -d gercekmi_db -f database/schema.sql
```

### 6. Uygulamayı Başlat

```bash
# Development mode
uvicorn main:app --reload --port 8000

# Production mode
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

## 📖 API Dokümantasyonu

Uygulama çalıştıktan sonra:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔗 API Endpoints

### Kimlik Doğrulama (`/api/auth`)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | `/register` | Yeni kullanıcı kaydı |
| POST | `/login` | Kullanıcı girişi |
| GET | `/me` | Mevcut kullanıcı bilgisi |
| POST | `/refresh` | Token yenileme |

### Anketler (`/api/polls`)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/` | Anketleri listele |
| GET | `/{id}` | Tek anket getir |
| POST | `/` | Yeni anket oluştur |
| DELETE | `/{id}` | Anket sil |
| GET | `/trending` | Trend anketler |
| GET | `/ending-soon` | Süresi dolmak üzere olanlar |
| GET | `/categories` | Kategoriler |
| GET | `/my-limit` | Günlük limit durumu |

### Oylar (`/api/votes`)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | `/` | Oy ver |
| DELETE | `/{poll_id}` | Oyu geri çek |
| GET | `/{poll_id}/my-vote` | Verdiğim oyu getir |

### Yorumlar (`/api/comments`)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/poll/{poll_id}` | Anketin yorumları |
| POST | `/` | Yorum yap |
| PUT | `/{id}` | Yorum düzenle |
| DELETE | `/{id}` | Yorum sil |

### Kullanıcılar (`/api/users`)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/{username}` | Profil getir |
| GET | `/{username}/polls` | Kullanıcının anketleri |
| POST | `/like/{poll_id}` | Beğen |
| DELETE | `/like/{poll_id}` | Beğeniyi kaldır |
| PUT | `/me/profile` | Profil güncelle |

## 🔐 Kimlik Doğrulama

API, JWT (JSON Web Token) tabanlı kimlik doğrulama kullanır.

```bash
# Login yap
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "123456"}'

# Token ile istek yap
curl -X GET "http://localhost:8000/api/polls" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## ⚙️ Önemli Özellikler

### 1. Günlük Anket Limiti
- Her kullanıcı günde **2 anket** oluşturabilir
- Editörler için limit yok

### 2. Anket Süresi
- Her anket **7 gün** aktif kalır
- Süre dolunca otomatik arşivlenir
- Arşivlenmiş anketlere oy/yorum yapılamaz

### 3. Sıralama
- Editör anketleri her zaman en üstte
- Sonra beğeni sayısına göre sıralama

## 🛠️ Geliştirme

```bash
# Test çalıştır
pytest

# Kod formatla
black .

# Lint kontrolü
flake8
```

## 📱 Mobile App Entegrasyonu

React Native uygulaması bu API'yi kullanacak:

```javascript
// API base URL
const API_URL = 'http://localhost:8000/api';

// Örnek: Anketleri çek
const response = await fetch(`${API_URL}/polls`);
const data = await response.json();
```

## 📄 Lisans

MIT License
