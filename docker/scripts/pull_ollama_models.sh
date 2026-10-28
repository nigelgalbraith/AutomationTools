
#!/usr/bin/env bash
set -euo pipefail

MODELS=(
  "phi3:latest"
)

echo "[ollama-init] Checking Ollama models..."

for model in "${MODELS[@]}"; do
  if ollama list | awk 'NR > 1 {print $1}' | grep -Fxq "$model"; then
    echo "[ollama-init] $model already present"
  else
    echo "[ollama-init] Pulling $model..."
    ollama pull "$model"
  fi
done

echo "[ollama-init] Done."
