#!/bin/bash
# Elasticsearch Reset Script - ⚠️ Deletes all data!
set -e
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "⚠️  WARNING: This will DELETE all Elasticsearch data!"
read -p "Type 'yes' to continue: " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

docker compose --profile kibana down -v 2>/dev/null || docker compose down -v
echo "✅ All data deleted. Run ./start.sh to start fresh."
