# Milvus Standalone - Docker Deployment

Docker Compose setup for running Milvus vector database locally.

## 📋 Prerequisites

- Docker Engine 20.10.0+
- Docker Compose 2.0.0+
- At least 4GB RAM available

## 🚀 Quick Start

```bash
cd docker/milvus
./start.sh
```

## 📁 File Structure

```
docker/milvus/
├── docker-compose.yml       # Compose configuration (Milvus v2.6.11)
├── embedEtcd.yaml           # Embedded etcd config
├── user.yaml                # User custom config
├── start.sh                 # Start with health check
├── stop.sh                  # Stop service
├── reset.sh                 # ⚠️ Delete all data
└── README.md                # This file
```

## 🔌 Connection Info

| Service | Endpoint | Port |
|---------|----------|------|
| Milvus gRPC | `localhost:19530` | 19530 |
| Milvus WebUI | http://localhost:9091/webui/ | 9091 |
| etcd | `localhost:2379` | 2379 |

## 🛠️ Usage

### Start Milvus
```bash
./start.sh
```

### Stop Milvus
```bash
./stop.sh
```
Data preserved in Docker volume `milvus-data`.

### View Data Volume
```bash
docker volume ls | grep milvus
docker volume inspect milvus_milvus-data
```

### Reset (⚠️ Delete All Data)
```bash
./reset.sh
```
**Warning**: This deletes the `milvus-data` Docker volume permanently!

### Check Health
```bash
curl http://localhost:9091/healthz
```

### View Logs
```bash
docker logs -f milvus-standalone
```

## ⚙️ Configuration

Edit `user.yaml` to customize Milvus settings, then restart:

```yaml
# Example
proxy:
  healthCheckTimeout: 1000
```

## 🔗 Integration with Aletheia

Update your `.env` file in the project root:

```bash
MILVUS_URI=http://localhost:19530
```

## 🐛 Troubleshooting

### Port Already in Use
Edit `docker-compose.yml` and change the ports:
```yaml
ports:
  - "19531:19530"  # Change host port
```

### Container Won't Start
```bash
# Check logs
docker logs milvus-standalone

# Reset and start fresh
./reset.sh && ./start.sh
```

### Permission Issues
Using Docker volumes (instead of bind mounts) avoids most permission issues. If you still have problems:

```bash
# Check volume exists
docker volume ls

# Remove volume manually if needed
docker volume rm milvus_milvus-data
```

## 📚 Resources

- [Milvus Documentation](https://milvus.io/docs)
- [Aletheia Architecture](../../docs/CORE_ARCHITECTURE.md)
