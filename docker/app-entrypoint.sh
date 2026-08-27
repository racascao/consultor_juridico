#!/bin/sh
set -eu

if [ "${SKIP_APP_BOOTSTRAP:-0}" != "1" ]; then
    echo "Verificando a preparação do MVP1..."
    if ! consultor-juridico bootstrap; then
        echo "BOOTSTRAP_FAILED: não foi possível preparar o MVP1." >&2
        echo "Diagnóstico opcional:" >&2
        echo "docker compose run --rm -e SKIP_APP_BOOTSTRAP=1 app consultor-juridico bootstrap" >&2
        exit 1
    fi
fi

case "${1:-}" in
    version|bootstrap|search|consult|db|ingest|document|parse|index|retrieval|eval)
        set -- consultor-juridico "$@"
        ;;
esac

exec "$@"
