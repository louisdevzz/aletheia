# Elasticsearch Single Node - Docker Deployment

Docker Compose setup for running Elasticsearch locally for Aletheia BM25 search.

## 📋 Prerequisites

- Docker Engine 20.10.0+
- Docker Compose 2.0.0+
- At least 4GB RAM available

### Linux Only: vm.max_map_count

Elasticsearch requires `vm.max_map_count >= 262144`:

```bash
# Check current value
sysctl vm.max_map_count

# Set temporarily
sudo sysctl -w vm.max_map_count=262144

# Set permanently
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

The `start.sh` script will check and offer to set this for you.

## 🚀 Quick Start

```bash
cd docker/elasticsearch

# Start Elasticsearch only
./start.sh

# Or start with Kibana UI
./start.sh --with-kibana
```

## 📁 File Structure

```
docker/elasticsearch/
├── docker-compose.yml          # ES 8.17.0 + optional Kibana
├── elasticsearch.yml           # ES config
├── start.sh                    # Start with health check
├── stop.sh                     # Stop service
├── reset.sh                    # ⚠️ Delete all data
└── README.md                   # This file
```

## 🔌 Connection Info

| Service | Endpoint | Description |
|---------|----------|-------------|
| Elasticsearch | http://localhost:9200 | REST API |
| Kibana (optional) | http://localhost:5601 | Data visualization UI |

## 🛠️ Usage

### Start Elasticsearch
```bash
./start.sh
```

### Start with Kibana
```bash
./start.sh --with-kibana
```

### Stop Elasticsearch
```bash
./stop.sh
```
Data preserved in Docker volume `es-data`.

### View Data Volume
```bash
docker volume ls | grep es-data
docker volume inspect elasticsearch_es-data
```

### Reset (⚠️ Delete All Data)
```bash
./reset.sh
```
**Warning**: This deletes the `es-data` Docker volume permanently!

### Check Health
```bash
curl http://localhost:9200/_cluster/health
curl http://localhost:9200/_cat/indices?v
```

### View Logs
```bash
docker logs -f elasticsearch
```

## ⚙️ Configuration

Edit `elasticsearch.yml` to customize settings, then restart.

To change JVM heap size, edit `docker-compose.yml`:
```yaml
environment:
  - "ES_JAVA_OPTS=-Xms2g -Xmx2g"  # Increase to 2GB
```

## 🔗 Integration with Aletheia

Update your `.env` file in the project root:

```bash
ELASTICSEARCH_URL=http://localhost:9200
```

### Initialize BM25 Index

```bash
uv run -c "from aletheia.storage.bm25_index import BM25Index; bi = BM25Index(); bi.create_index()"
```

## 🐛 Troubleshooting

### vm.max_map_count too low
```bash
sudo sysctl -w vm.max_map_count=262144
```

### Port Already in Use
Edit `docker-compose.yml` and change the ports:
```yaml
ports:
  - "9201:9200"  # Change host port
```

### Out of Memory
Reduce heap size in `docker-compose.yml`:
```yaml
environment:
  - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
```

### Permission Issues
Using Docker volumes (instead of bind mounts) avoids most permission issues. If you still have problems:

```bash
# Check volume
docker volume ls

# Remove volume manually if needed
docker volume rm elasticsearch_es-data
```

### Container Won't Start
```bash
# Check logs
docker logs elasticsearch

# Reset and start fresh
./reset.sh && ./start.sh
```

## 📚 Resources

- [Elasticsearch Documentation](https://www.elastic.co/docs)
- [Aletheia Architecture](../../docs/CORE_ARCHITECTURE.md)
