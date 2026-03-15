# Aletheia - Setup Guide

Complete installation and setup instructions for Aletheia.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Dependency Installation](#dependency-installation)
4. [Database Initialization](#database-initialization)
5. [Running the Application](#running-the-application)
6. [System Service Installation](#system-service-installation)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Python 3.10+**
- **Node.js 18+** (for frontend)
- **pnpm** (package manager)
- **uv** (Python package manager)

### Required Services

| Service | Local | Cloud |
|---------|-------|-------|
| **Database** | SQLite (default) | N/A |
| **Vector Search** | [Milvus (Docker)](../../docker/milvus/) | Zilliz Cloud |
| **Keyword Search** | [Elasticsearch (Docker)](../../docker/elasticsearch/) | Elastic Cloud |

#### Quick Start: Services with Docker

```bash
# 1. Start Milvus (Vector Search)
cd docker/milvus
./start.sh

# 2. Start Elasticsearch (Keyword Search)
cd docker/elasticsearch
./start.sh

# Or start with Kibana UI
./start.sh --kibana
```

Milvus: `localhost:19530` | Elasticsearch: `localhost:9200` | Kibana: `localhost:5601`

See [docker/milvus/README.md](../../docker/milvus/README.md) and [docker/elasticsearch/README.md](../../docker/elasticsearch/README.md) for detailed configuration.

### API Keys

You need at least one of these API keys:

- `OPENAI_API_KEY` - For GPT-4o and embeddings
- `GOOGLE_API_KEY` - For Gemini
- `KIMI_API_KEY` - For Kimi/Moonshot

---

## Environment Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd aletheia
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# Required: At least one LLM provider
OPENAI_API_KEY=your_openai_key_here
GOOGLE_API_KEY=your_google_key_here
KIMI_API_KEY=your_kimi_key_here

# Optional: Vector Database (defaults to local Milvus)
MILVUS_URI=http://localhost:19530
# Or for Zilliz Cloud:
# MILVUS_URI=https://your-cluster.zillizcloud.com
# MILVUS_TOKEN=your_token

# Optional: Elasticsearch (defaults to local)
ELASTICSEARCH_URL=http://localhost:9200
# Or for Elastic Cloud:
# ELASTICSEARCH_URL=https://your-deployment.es.us-east-1.aws.found.io
# ELASTIC_API_KEY=your_api_key

# Embedding Configuration
EMBEDDING_PROVIDER=ollama  # or "openai", "huggingface"
EMBEDDING_MODEL=mxbai-embed-large:335m
OLLAMA_BASE_URL=http://localhost:11434/v1
```

---

## Dependency Installation

### Backend (Python)

```bash
# Create virtual environment
uv venv

# Activate (Linux/macOS)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
uv sync
```

### Frontend (Node.js)

```bash
cd web

# Install dependencies with pnpm
pnpm install

# Return to root
cd ..
```

---

## Database Initialization

### SQLite (Default - Zero Setup)

Aletheia uses **SQLite** as the default database. No additional setup required - the database will be automatically created at:

```
~/.aletheia/database/aletheia.db
```

**Why SQLite?**
- Zero configuration - works out of the box
- Single file - easy to backup and migrate
- Excellent performance for single-user desktop applications
- No separate server process needed
- Perfect for Aletheia's use case

### Setup Search Indices

```bash
# Initialize Milvus collection
uv run -c "from aletheia.storage.vector_index import VectorIndex; vi = VectorIndex(); vi.create_collection()"

# Initialize Elasticsearch index
uv run -c "from aletheia.storage.bm25_index import BM25Index; bi = BM25Index(); bi.create_index()"
```

---

## Running the Application

### Development Mode

**Terminal 1 - Backend:**
```bash
uv run aletheia daemon --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Frontend:**
```bash
cd web
pnpm dev
```

Access the application at: http://localhost:3000

### Production Mode

**Backend:**
```bash
uv run aletheia daemon --host 0.0.0.0 --port 8000 --workers 4
```

**Frontend:**
```bash
cd web
pnpm build
pnpm start
```

---

## System Service Installation

### Linux (systemd)

```bash
# Install service
chmod +x deploy/install.sh
./deploy/install.sh

# Check status
systemctl --user status aletheia

# View logs
journalctl --user -u aletheia -f
```

### macOS (LaunchAgent)

```bash
# Install service
chmod +x deploy/install_mac.sh
./deploy/install_mac.sh

# Check status
launchctl list | grep aletheia

# View logs
tail -f ~/.aletheia/logs/aletheia.log
```

### Uninstall Service

```bash
./deploy/uninstall.sh
```

---

## Verification

### Test Backend Health

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy"}
```

### Test WebSocket Connection

Open browser dev tools and connect to:
```
ws://localhost:8000/ws/chat
```

Send test message:
```json
{"type": "chat.message", "payload": {"message": "Hello!"}}
```

---

## Troubleshooting

### Backend won't start

**Port already in use:**
```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>
```

**Database locked (SQLite):**
- Only one process can write to SQLite at a time
- Stop other instances: `pkill -f "aletheia daemon"`
- Check permissions: `ls -la ~/.aletheia/database/`

**Missing API keys:**
- At least one LLM provider key required
- Check keys are set in `.env`

### Frontend won't connect

**CORS error:**
- Ensure backend is running on correct port
- Check `ALETHEIA_API_URL` in `web/.env.local`

**WebSocket connection failed:**
- Verify backend is running: `curl http://localhost:8000/health`
- Check firewall settings
- Ensure `NEXT_PUBLIC_WS_URL` is set correctly

### Document ingestion fails

**Vision LLM timeout:**
- Increase timeout in settings
- Check API key quota
- Try different provider

**SQLite database issues:**
- Check disk space: `df -h ~/.aletheia/`
- Verify write permissions: `touch ~/.aletheia/database/test`
- Database location: `~/.aletheia/database/aletheia.db`

### Performance issues

**Slow search:**
- Enable caching (default enabled)
- Check if indices exist in Milvus/ES
- Consider using local embedding model

**High memory usage:**
- Reduce `RETRIEVAL_TOP_K` (default: 5)
- Use smaller embedding model
- Limit concurrent connections

**SQLite performance:**
- SQLite is optimized for single-user use
- For best performance, ensure SSD storage
- Database is automatically vacuumed periodically

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `MILVUS_URI` | `http://localhost:19530` | Milvus/Zilliz connection URI |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | Elasticsearch URL |
| `EMBEDDING_PROVIDER` | `ollama` | Embedding provider: `ollama`, `openai` |
| `EMBEDDING_DIMENSION` | `1024` | Embedding vector dimension |
| `RETRIEVAL_TOP_K` | `5` | Number of results to retrieve |
| `LOG_LEVEL` | `info` | Logging level: `debug`, `info`, `warning` |

---

## Next Steps

- Read [CORE_ARCHITECTURE.md](CORE_ARCHITECTURE.md) for system details
- See [AGENT_ARCHITECTURE_ROADMAP.md](AGENT_ARCHITECTURE_ROADMAP.md) for future features
- Check [API documentation](api/README.md) for programmatic access

---

*Last updated: 2026-02-28*