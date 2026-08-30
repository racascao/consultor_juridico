#!/bin/sh
set -eu

ollama serve &
ollama_pid=$!

cleanup() {
    kill "$ollama_pid" 2>/dev/null || true
}
trap cleanup INT TERM

echo "Aguardando o servidor Ollama..."
until ollama list >/dev/null 2>&1; do
    sleep 1
done

echo "Preparando modelos locais do MVP2..."
ollama pull "$OLLAMA_EMBEDDING_MODEL"
if [ "$OLLAMA_CONSULTATION_MODEL" != "$OLLAMA_EMBEDDING_MODEL" ]; then
    ollama pull "$OLLAMA_CONSULTATION_MODEL"
fi
echo "Modelos do MVP2 prontos."

wait "$ollama_pid"
