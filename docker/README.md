# Docker Services for Aletheia

Docker Compose configurations for external services required by Aletheia.

## 📦 Available Services

| Service | Folder | Purpose | Port |
|---------|--------|---------|------|
| **Milvus** | [milvus/](milvus/) | Vector search | 19530 |
| **Elasticsearch** | [elasticsearch/](elasticsearch/) | BM25 keyword search | 9200 |

## 🚀 Quick Start

```bash
# Terminal 1: Start Milvus
cd docker/milvus && ./start.sh

# Terminal 2: Start Elasticsearch
cd docker/elasticsearch && ./start.sh
# Or with Kibana UI: ./start.sh --with-kibana
```

Verify services:
```bash
curl http://localhost:9091/healthz  # Milvus
curl http://localhost:9200          # Elasticsearch
```

## 📂 Service Structure

Each service folder contains:

```
service-name/
├── docker-compose.yml    # Compose configuration
├── config files          # Service-specific configs (read-only)
├── start.sh              # Start with health check
├── stop.sh               # Stop service
├── reset.sh              # ⚠️ Delete all data
└── README.md             # Service documentation
```

## 💾 Data Storage

Both services use **Docker volumes** (not bind mounts):

| Service | Volume Name | Purpose |
|---------|-------------|---------|
| Milvus | `milvus_milvus-data` | Vector data & etcd |
| Elasticsearch | `elasticsearch_es-data` | Indices & documents |

### View Volumes
```bash
docker volume ls | grep -E "milvus|es-data"
```

### Backup Data
```bash
# Backup Milvus
docker run --rm -v milvus_milvus-data:/data -v $(pwd):/backup alpine tar czf /backup/milvus-backup.tar.gz -C /data .

# Backup Elasticsearch
docker run --rm -v elasticsearch_es-data:/data -v $(pwd):/backup alpine tar czf /backup/es-backup.tar.gz -C /data .
```

### Restore Data
```bash
# Restore Milvus
docker run --rm -v milvus_milvus-data:/data -v $(pwd):/backup alpine tar xzf /backup/milvus-backup.tar.gz -C /data

# Restore Elasticsearch (stop service first)
./reset.sh
docker run --rm -v elasticsearch_es-data:/data -v $(pwd):/backup alpine tar xzf /backup/es-backup.tar.gz -C /data
./start.sh
```

## 🔧 Managing Services

| Script | Description |
|--------|-------------|
| `./start.sh` | Start service with health check |
| `./stop.sh` | Stop service (preserve data in Docker volume) |
| `./reset.sh` | ⚠️ Delete Docker volume and all data |

## 🌐 Integration

Update your project `.env`:

```bash
# Milvus
MILVUS_URI=http://localhost:19530

# Elasticsearch
ELASTICSEARCH_URL=http://localhost:9200
```

## 📊 Architecture

```
┌─────────────────┐     ┌─────────────────┐
│     Milvus      │     │  Elasticsearch  │
│   (Port 19530)  │     │   (Port 9200)   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
            ┌────────▼────────┐
            │  Aletheia    │
            │  Hybrid Search  │
            └─────────────────┘
```

## 🐛 Troubleshooting

### Out of Memory
- Milvus: ~2-4GB RAM
- Elasticsearch: ~2-4GB RAM (configurable via `ES_JAVA_OPTS`)

With limited RAM:
1. Start only the services you need
2. Reduce ES heap in `docker-compose.yml`: `-Xms512m -Xmx512m`
3. Use cloud versions

### Port Conflicts
Edit ports in `docker-compose.yml`:
```yaml
ports:
  - "19531:19530"  # Change host port
```

### Permission Issues
Using Docker volumes avoids most permission problems. If issues persist:
```bash
# Remove volume and start fresh
./reset.sh
./start.sh
```

### Service Won't Start
```bash
# Check logs
docker logs <container-name>

# Reset and restart
./reset.sh && ./start.sh
```

## 📚 Documentation

- [Milvus Documentation](https://milvus.io/docs)
- [Elasticsearch Documentation](https://www.elastic.co/docs)
- [Aletheia Setup](../docs/SETUP.md)
