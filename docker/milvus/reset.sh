#!/bin/bash
# Milvus Reset Script - ⚠️ Deletes all data!
set -e
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "⚠️  WARNING: This will DELETE all Milvus data!"
read -p "Type 'yes' to continue: " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

docker compose down -v
rm -f embedEtcd.yaml user.yaml
echo "✅ All data deleted. Run ./start.sh to start fresh."
