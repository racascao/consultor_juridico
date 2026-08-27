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

echo "Preparando modelos congelados do MVP1..."
ollama pull "$EMBEDDING_MODEL"
if [ "$SEMANTIC_JUDGE_MODEL" != "$EMBEDDING_MODEL" ]; then
    ollama pull "$SEMANTIC_JUDGE_MODEL"
fi
echo "Modelos do MVP1 prontos."

wait "$ollama_pid"
