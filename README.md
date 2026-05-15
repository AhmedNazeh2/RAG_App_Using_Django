# AI_RAG_Using_Django

A production-ready RAG (Retrieval-Augmented Generation) chatbot built with **Django + DRF**.  
Users register, upload their own documents (PDF / TXT), and ask questions answered exclusively from their own files.  
All data is fully isolated per user.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔐 Auth | JWT (access + refresh tokens) via `djangorestframework-simplejwt` |
| 📄 Documents | Upload PDF / TXT → auto-chunked, embedded, stored in ChromaDB |
| 💬 Chat | Ask questions → RAG retrieval → LLM answer with source citations |
| 🕑 History | Last 20 Q&A pairs, per-user, deletable |
| 🎨 UI | Dark, responsive SPA (Django template, no build step needed) |
| 🐳 Docker | Single `docker-compose up` to run everything |
| 🧪 Tests | Full unit test suite covering auth, documents, chat, RAG utils |

---


## ⚙️ Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | Django secret key — generate a long random string |
| `DEBUG` | ✅ | `True` for development, `False` for production |
| `OPENAI_API_KEY` | ⚠️ | OpenAI key for GPT-4o-mini + embeddings |
| `GROQ_API_KEY` | ⚠️ | Groq key (free alternative to OpenAI) |
| `LLM_PROVIDER` | ✅ | `openai` or `groq` (default: `openai`) |
| `CHROMA_PERSIST_DIR` | ✅ | Path for ChromaDB persistence (default: `./chroma_db`) |
| `CHUNK_SIZE` | ✅ | Words per chunk (default: `500`) |
| `CHUNK_OVERLAP` | ✅ | Overlap between chunks (default: `50`) |

> **Note:** Either `OPENAI_API_KEY` **or** `GROQ_API_KEY` is required for AI features.  
> If using Groq, embeddings fall back to the free `all-MiniLM-L6-v2` model (sentence-transformers).

---

## 🚀 Setup — Local (without Docker)

### Prerequisites
- Python 3.10+
- pip

### Steps

```bash
# 1. Clone
git clone https://github.com/AhmedNazeh2/RAG_App_Using_Django.git
cd RAG_App_Using_Django

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY or GROQ_API_KEY

# 5. Run migrations
python manage.py migrate

# 6. Start server
python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser — the UI will load automatically.

---

## 🐳 Setup — Docker

```bash
# 1. Clone & configure
git clone https://github.com/AhmedNazeh2/RAG_App_Using_Django.git
cd RAG_App_Using_Django
cp .env.example .env
# Edit .env

# 2. Build & run
docker-compose up --build

# App available at http://localhost:8000
```

## 📡 API Reference

All endpoints below `/api/auth/login/` and `/api/auth/register/` require:
```
Authorization: Bearer <access_token>
```

### Auth

#### Register
```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com", "password": "securepass123"}'

# Response 201
{"message": "Account created successfully."}
```

#### Login
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "securepass123"}'

# Response 200
{"access": "<jwt_token>", "refresh": "<refresh_token>"}
```

#### Refresh Token
```bash
curl -X POST http://localhost:8000/api/auth/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh_token>"}'
```

#### Get Current User
```bash
curl http://localhost:8000/api/auth/me/ \
  -H "Authorization: Bearer <access_token>"

# Response 200
{"id": 1, "username": "alice", "email": "alice@example.com"}
```

---

### Documents

#### Upload a Document
```bash
curl -X POST http://localhost:8000/api/documents/upload/ \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@/path/to/your/document.pdf"

# Response 201
{
  "id": 1,
  "filename": "document.pdf",
  "file_size": 204800,
  "file_size_display": "200.0 KB",
  "chunk_count": 42,
  "uploaded_at": "2025-01-01T10:00:00Z"
}
```

#### List My Documents
```bash
curl http://localhost:8000/api/documents/ \
  -H "Authorization: Bearer <access_token>"
```

#### Delete a Document
```bash
curl -X DELETE http://localhost:8000/api/documents/1/ \
  -H "Authorization: Bearer <access_token>"
```

---

### Chat

#### Ask a Question
```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the remote work policy?"}'

# Response 201
{
  "id": 5,
  "question": "What is the remote work policy?",
  "answer": "According to the uploaded policy document, employees may work remotely up to 3 days per week...",
  "sources": ["policy.pdf — chunk 3", "policy.pdf — chunk 7"],
  "created_at": "2025-01-01T11:00:00Z"
}
```

#### Chat History
```bash
curl http://localhost:8000/api/chat/history/ \
  -H "Authorization: Bearer <access_token>"
```

#### Delete a History Entry
```bash
curl -X DELETE http://localhost:8000/api/chat/history/5/ \
  -H "Authorization: Bearer <access_token>"
```

---

## 🔒 Security & Data Isolation

- Every database query is filtered by `owner=request.user` — no user can access another's data
- ChromaDB collections are namespaced as `user_<id>` — vectors are fully isolated
- JWT tokens expire after 1 hour; refresh tokens after 7 days
- File uploads are stored under `media/documents/user_<id>/`
- Max upload size: 10 MB

---

## 🔄 RAG Pipeline

```
Upload
  └─ Extract text (pypdf / plain text)
       └─ Chunk text (500 words, 50-word overlap)
            └─ Embed chunks (OpenAI text-embedding-3-small OR sentence-transformers)
                 └─ Store in ChromaDB (collection: user_<id>)

Query
  └─ Embed question
       └─ Cosine similarity search in user's collection (top-5 chunks)
            └─ Build prompt: system + context + question
                 └─ Call LLM (GPT-4o-mini or Groq Llama3)
                      └─ Return answer + source citations
```

---

## 📦 Tech Stack

| Layer | Choice |
|---|---|
| Framework | Django 4.2 + Django REST Framework |
| Auth | JWT — `djangorestframework-simplejwt` |
| Vector Store | ChromaDB (persistent, disk-backed) |
| Embeddings | OpenAI `text-embedding-3-small` / `sentence-transformers` |
| LLM | OpenAI `gpt-4o-mini` / Groq `llama3-8b-8192` |
| Database | SQLite (default) |
| Frontend | Vanilla JS SPA served as a Django template |
