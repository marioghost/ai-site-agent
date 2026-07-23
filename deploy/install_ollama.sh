#!/usr/bin/env bash
#
# Install Ollama locally (no Docker) and pull the default models.
# Run:  bash deploy/install_ollama.sh
#
set -euo pipefail

LLM_MODEL="${DEFAULT_LLM_MODEL:-qwen2.5:7b}"
EMBED_MODEL="${DEFAULT_EMBEDDING_MODEL:-bge-m3}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "==> Installing Ollama (official install script)"
  curl -fsSL https://ollama.com/install.sh | sh
else
  echo "==> Ollama already installed: $(ollama --version || true)"
fi

# The installer normally registers a systemd service named 'ollama'.
# Make sure it is running before pulling models.
if command -v systemctl >/dev/null 2>&1; then
  echo "==> Ensuring ollama service is running"
  sudo systemctl enable --now ollama || true
fi

echo "==> Pulling LLM model: $LLM_MODEL"
ollama pull "$LLM_MODEL"

echo "==> Pulling embedding model: $EMBED_MODEL"
ollama pull "$EMBED_MODEL"

echo ""
echo "Installed models:"
ollama list
