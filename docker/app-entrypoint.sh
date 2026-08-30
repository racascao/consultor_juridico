#!/bin/sh
set -eu

if [ "${1:-}" = "standby" ]; then
    echo "Imagem CLI pronta; o bootstrap será executado pelo container efêmero."
    exit 0
fi

if [ "${SKIP_APP_BOOTSTRAP:-0}" != "1" ]; then
    echo "Verificando a preparação do corpus v0.2..."
    if ! consultor-juridico bootstrap; then
        echo "BOOTSTRAP_FAILED: não foi possível preparar o corpus v0.2." >&2
        echo "Diagnóstico opcional:" >&2
        echo "docker compose run --rm -e SKIP_APP_BOOTSTRAP=1 app consultor-juridico bootstrap" >&2
        exit 1
    fi
fi

case "${1:-}" in
    version|bootstrap|corpus|db|indice|retrieval|eval)
        set -- consultor-juridico "$@"
        ;;
esac

exec "$@"
