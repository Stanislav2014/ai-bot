#!/usr/bin/env bash
set -euo pipefail

echo "=== AI Bot Deploy ==="

# Pull latest code
echo "[1/5] Pulling latest code..."
git pull origin "$(git branch --show-current)"

# Check .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in values."
    exit 1
fi

# Build images
echo "[2/5] Building Docker images..."
docker compose build

# Start services
echo "[3/5] Starting services..."
docker compose up -d

# Wait for Ollama to be ready
echo "[4/5] Waiting for Ollama to be ready..."
for i in $(seq 1 30); do
    if docker compose exec ollama ollama list &>/dev/null; then
        echo "Ollama is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "WARNING: Ollama did not become ready in 30s. Models may need to be pulled manually."
    fi
    sleep 1
done

# Pull models if not present
echo "[5/5] Checking models..."
MODELS=("gpt-oss-20b" "qwen3:0.6b" "qwen3.5:27b")
for model in "${MODELS[@]}"; do
    if ! docker compose exec ollama ollama list | grep -q "$model"; then
        echo "Pulling model: $model ..."
        docker compose exec ollama ollama pull "$model" || echo "WARNING: Failed to pull $model (may not exist yet)"
    else
        echo "Model $model already present."
    fi
done

echo ""
echo "=== Deploy complete ==="
echo "Bot logs: make logs"
echo "All logs: make logs-all"
