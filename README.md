# AI Playground

A self-hosted AI chat interface and API server built with **Python Flask** and the **[g4f](https://github.com/xtekky/gpt4free)** library. Features an interactive dark-theme web UI with four modes — Chat, Image Generation, Vision, and Document Analysis — plus a fully OpenAI-compatible REST API.

**Session memory** is stored in **PostgreSQL** when `DATABASE_URL` is set, and falls back to a local JSON file otherwise. No code changes needed to switch.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-green)
![g4f](https://img.shields.io/badge/g4f-7.5.0-purple)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14%2B-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Table of Contents

1. [Features](#features)
2. [Project Structure](#project-structure)
3. [Quick Start](#quick-start-local)
4. [Environment Variables](#environment-variables)
5. [PostgreSQL Setup](#postgresql-setup)
6. [Free Models vs HuggingFace Models](#free-models-vs-huggingface-models)
7. [API Reference](#api-reference)
8. [Deployment](#deployment)
9. [Supported Document Formats](#supported-document-formats)

---

## Features

| Feature | Details |
|---|---|
| **Chat** | Multi-turn conversations with persistent session memory |
| **Image Generation** | FLUX (Pollinations), Aria (Opera), FLUX.1-dev/schnell (HuggingFace) |
| **Vision** | Upload an image and ask the AI questions about it |
| **Document Analysis** | Extract and query PDF, Word, Excel, CSV, TXT, and more |
| **15+ Free Models** | Perplexity, PollinationsAI, YqCloud, Opera — no API key required |
| **19 HuggingFace Models** | DeepSeek, Llama, Qwen, GPT-OSS (HF token required) |
| **PostgreSQL Sessions** | Conversation history in Postgres with JSON file fallback |
| **OpenAI-Compatible API** | Drop-in for any OpenAI client |
| **Streaming** | SSE token-by-token streaming via `stream: true` |

---

## Project Structure

```
ai-playground/
├── app.py                  # Flask application factory — registers all blueprints
├── ai_server.py            # Entry point: loads app.py and starts the server
│
├── api/                    # Route blueprints (one file per feature)
│   ├── __init__.py
│   ├── chat.py             # POST /v1/chat/completions
│   ├── images.py           # POST /v1/images/generations
│   ├── vision.py           # POST /v1/upload  (vision analysis)
│   ├── extract.py          # POST /v1/extract  (document text extraction)
│   ├── models.py           # GET  /v1/models, /v1/providers
│   └── sessions.py         # GET/DELETE /v1/sessions/*
│
├── db/                     # Storage backend
│   ├── __init__.py
│   └── sessions.py         # Auto-selects PostgreSQL or JSON file fallback
│
├── utils/                  # Shared utilities
│   ├── __init__.py
│   ├── providers.py        # Provider registry and model catalog
│   ├── g4f_client.py       # g4f client builder and response helpers
│   └── file_extract.py     # PDF / Word / Excel / CSV text extraction
│
├── templates/
│   └── index.html          # Interactive web UI (dark theme, 4 modes)
│
├── .env.example            # Environment variable template
├── requirements.txt        # Python dependencies
└── README.md
```

---

## Quick Start (Local)

### 1. Clone

```bash
git clone https://github.com/mauricegift/ai-scraper.git
cd ai-scraper
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env — minimum required: nothing (runs with JSON sessions out of the box)
# Add DATABASE_URL for PostgreSQL, HF_TOKEN for HuggingFace models
```

### 5. Run

```bash
python3 ai_server.py
```

Open **http://localhost:5000** in your browser.

---

## Environment Variables

Copy `.env.example` to `.env` and edit as needed. All variables are optional
except where noted.

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5000` | Port the server listens on |
| `SESSION_SECRET` | random | Flask session signing key — set a fixed value in production |
| `FLASK_DEBUG` | `false` | Enable Flask debug mode (never `true` in production) |
| `DATABASE_URL` | _(empty)_ | PostgreSQL connection URL — leave blank to use JSON file storage |
| `HF_TOKEN` | _(empty)_ | HuggingFace token for HF models — free models don't need this |

---

## PostgreSQL Setup

Session memory defaults to a local `sessions_store.json` file. Set `DATABASE_URL`
to switch to PostgreSQL — **no code changes required**. The app creates the
`ai_sessions` table automatically on first startup.

### Option A — Local PostgreSQL (development / self-hosted VPS)

#### 1. Install PostgreSQL

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y postgresql postgresql-contrib

# macOS (Homebrew)
brew install postgresql@15 && brew services start postgresql@15
```

#### 2. Create a database and user

```bash
sudo -u postgres psql
```

Inside the `psql` shell:

```sql
-- Create a dedicated user (replace the password)
CREATE USER aiuser WITH PASSWORD 'str0ngPassw0rd';

-- Create the database
CREATE DATABASE ai_playground OWNER aiuser;

-- Grant full privileges
GRANT ALL PRIVILEGES ON DATABASE ai_playground TO aiuser;

-- Exit
\q
```

#### 3. Verify the connection

```bash
psql postgresql://aiuser:str0ngPassw0rd@localhost:5432/ai_playground -c '\l'
```

#### 4. Set DATABASE_URL in your .env

```dotenv
DATABASE_URL=postgresql://aiuser:str0ngPassw0rd@localhost:5432/ai_playground
```

#### 5. Restart the server

```bash
python3 ai_server.py
# Startup log will show: "SessionStore: connected to PostgreSQL"
```

The table is created automatically:

```sql
CREATE TABLE ai_sessions (
    session_id  VARCHAR(255)  PRIMARY KEY,
    messages    JSONB         NOT NULL DEFAULT '[]',
    turns       INTEGER       NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
```

---

### Option B — Remote / Self-Hosted VPS PostgreSQL

If your database lives on a different machine (e.g. `192.168.1.10`):

```dotenv
DATABASE_URL=postgresql://aiuser:str0ngPassw0rd@192.168.1.10:5432/ai_playground
```

Make sure PostgreSQL is configured to accept remote connections:

#### Allow remote connections

Edit `/etc/postgresql/<version>/main/postgresql.conf`:

```
listen_addresses = '*'
```

Edit `/etc/postgresql/<version>/main/pg_hba.conf` — add a line for your app server IP:

```
# TYPE  DATABASE        USER      ADDRESS           METHOD
host    ai_playground   aiuser    <your-app-ip>/32  md5
```

Reload PostgreSQL:

```bash
sudo systemctl reload postgresql
```

#### Open the firewall port

```bash
# UFW
sudo ufw allow from <your-app-ip> to any port 5432

# iptables
sudo iptables -A INPUT -p tcp --dport 5432 -s <your-app-ip> -j ACCEPT
```

---

### Option C — Managed Cloud PostgreSQL

Use a connection string from your provider. Always add `?sslmode=require` for
cloud databases:

```dotenv
# Supabase
DATABASE_URL=postgresql://postgres:password@db.xxxx.supabase.co:5432/postgres?sslmode=require

# Neon
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require

# Railway
DATABASE_URL=postgresql://postgres:pass@containers-us-west-xxx.railway.app:6543/railway

# Render
DATABASE_URL=postgresql://user:pass@dpg-xxx.oregon-postgres.render.com:5432/dbname?sslmode=require
```

---

### Fallback Behaviour

If `DATABASE_URL` is blank or the connection fails at startup, the app
automatically falls back to `sessions_store.json` in the project root and
logs a warning. No manual intervention needed.

---

## Free Models vs HuggingFace Models

The model selector shows two groups:

### ✅ Free — No Token Needed

These work immediately — no signup, no credits, no API key:

| Model ID | Provider | Capabilities |
|---|---|---|
| `auto` | Perplexity | Chat |
| `turbo` | Perplexity | Chat |
| `gpt41` | Perplexity | Chat |
| `gpt5` | Perplexity | Chat |
| `gpt5_thinking` | Perplexity | Chat |
| `llama` | Perplexity | Chat |
| `mistral` | Perplexity | Chat |
| `claude` | Perplexity | Chat |
| `openai` | PollinationsAI | Chat + Vision |
| `openai-fast` | PollinationsAI | Chat + Vision |
| `flux` | PollinationsAI | Image Generation |
| `gpt-4` | YqCloud | Chat |
| `gpt-4o` | YqCloud | Chat |
| `gpt-3.5-turbo` | YqCloud | Chat |
| `aria` | Opera | Chat + Image |

### 🔑 HuggingFace — Token + Monthly Credits

Requires a [HuggingFace account](https://huggingface.co) with a valid read token.
Free tier has monthly usage limits. When limits are hit the app shows a clear
error with suggestions to switch to a free model.

---

## API Reference

Base URL: `http://localhost:5000`

### GET /v1/models
List all models with capabilities, provider, and free/paid status.

```bash
curl http://localhost:5000/v1/models
```

### GET /v1/providers
List all providers with capability and auth metadata.

### POST /v1/chat/completions
OpenAI-compatible chat endpoint.

```bash
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt41",
    "provider": "perplexity",
    "messages": [{"role": "user", "content": "Hello!"}],
    "session_id": "my-session",
    "system": "Be concise.",
    "max_tokens": 2048,
    "temperature": 0.7,
    "stream": false
  }'
```

| Field | Type | Default | Description |
|---|---|---|---|
| `model` | string | `auto` | Model ID |
| `messages` | array | required | `[{role, content}]` |
| `provider` | string | auto | Provider key — auto-detected from model if omitted |
| `session_id` | string | — | Key for persistent history |
| `system` | string | — | System prompt |
| `max_tokens` | int | 2048 | Max response tokens |
| `temperature` | float | 0.7 | Sampling temperature |
| `stream` | bool | false | SSE token streaming |
| `reset_session` | bool | false | Clear history before this turn |
| `hf_token` | string | — | HuggingFace token override |

### POST /v1/images/generations

```bash
curl -X POST http://localhost:5000/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A sunset over the ocean", "model": "flux", "size": "1024x1024"}'
```

### POST /v1/upload — Vision

```bash
curl -X POST http://localhost:5000/v1/upload \
  -F "file=@photo.jpg" \
  -F "prompt=What is in this image?" \
  -F "model=openai" \
  -F "provider=pollinations"
```

### POST /v1/extract — Document text extraction

```bash
curl -X POST http://localhost:5000/v1/extract -F "file=@report.pdf"
```

### Sessions

```bash
GET    /v1/sessions            # list all sessions
GET    /v1/sessions/{id}       # get session history
DELETE /v1/sessions/{id}       # delete one session
DELETE /v1/sessions            # delete all sessions
```

### GET /health

```bash
curl http://localhost:5000/health
# {"status":"ok","storage_backend":"postgres","active_sessions":3,...}
```

---

## Deployment

### Option 1 — Replit

1. Import this repository on [replit.com](https://replit.com).
2. Add environment variables in the **Secrets** tab (`DATABASE_URL`, `HF_TOKEN`, etc.).
3. Set the run command to `python3 ai_server.py`.
4. Click **Deploy** for a public `.replit.app` URL with TLS.

### Option 2 — Linux VPS (systemd)

```bash
# Install Python
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip

# Clone and install
git clone https://github.com/mauricegift/ai-scraper.git /opt/ai-playground
cd /opt/ai-playground
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env
cp .env.example .env && nano .env   # fill in DATABASE_URL, HF_TOKEN, etc.
```

Create `/etc/systemd/system/ai-playground.service`:

```ini
[Unit]
Description=AI Playground
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/ai-playground
EnvironmentFile=/opt/ai-playground/.env
ExecStart=/opt/ai-playground/venv/bin/python3 ai_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ai-playground
sudo systemctl status ai-playground
```

### Option 3 — Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python3", "ai_server.py"]
```

```bash
docker build -t ai-playground .
docker run -d -p 5000:5000 \
  -e DATABASE_URL=postgresql://... \
  -e HF_TOKEN=hf_... \
  --name ai-playground ai-playground
```

### Option 4 — Nginx + Gunicorn (Production)

```bash
pip install gunicorn
gunicorn -w 4 -b 127.0.0.1:5000 "app:create_app()"
```

`/etc/nginx/sites-available/ai-playground`:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_read_timeout 120s;

        # Required for SSE streaming
        proxy_buffering    off;
        proxy_cache        off;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/ai-playground /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
# Add HTTPS
sudo certbot --nginx -d yourdomain.com
```

### Option 5 — Railway / Render / Fly.io

Set the start command to `python3 ai_server.py` and add your environment
variables in the platform dashboard. All three platforms support
PostgreSQL add-ons that provide a `DATABASE_URL` automatically.

---

## Supported Document Formats

| Format | Extensions |
|---|---|
| PDF | `.pdf` |
| Microsoft Word | `.docx`, `.doc` |
| Microsoft Excel | `.xlsx`, `.xls` |
| Plain text | `.txt`, `.md`, `.log`, `.rtf` |
| Delimited data | `.csv`, `.tsv` |
| Code / markup | `.json`, `.yaml`, `.xml`, `.html`, `.js`, `.py`, `.sh`, `.toml`, `.ini` |

---

## License

MIT — free to use, modify, and deploy.
