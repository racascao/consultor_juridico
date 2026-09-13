FROM python:3.13-slim

WORKDIR /app

# Configurações de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Instalação de utilitários básicos
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalação do uv dentro do container
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copia arquivos de dependência e configuração
COPY pyproject.toml uv.lock README.md alembic.ini ./

# Cria o .venv interno do container e instala dependências
RUN uv sync --frozen --no-install-project

# Copia o código-fonte
COPY src/ ./src/

# Copia somente o freeze runtime-critical e seus artifacts referenciados.
COPY evaluation/model_selection/gold_evidence_selected_answerer_freeze_v1.json \
    ./evaluation/model_selection/gold_evidence_selected_answerer_freeze_v1.json
COPY evaluation/datasets/lei_9784_gold_evidence_dev_v1.json \
    ./evaluation/datasets/lei_9784_gold_evidence_dev_v1.json
COPY evaluation/runs/gemma4_12b_prompt_v2_full_responses.jsonl \
    evaluation/runs/gold_evidence_input_prompt_v2.jsonl \
    evaluation/runs/gold_evidence_stability_prompt_v2_input.jsonl \
    evaluation/runs/gold_evidence_posthoc_gold012_prompt_v2_input.jsonl \
    evaluation/runs/gold_evidence_cross_model_manifest_v1.json \
    ./evaluation/runs/
COPY evaluation/results/gemma4_12b_prompt_v2_full_final_review.json \
    evaluation/results/gemma4_12b_prompt_v2_gold012_material_review.json \
    evaluation/results/gemma4_12b_prompt_v2_risk_scorecard.json \
    evaluation/results/gemma4_12b_prompt_v2_format_json_reconsideration_v1_risk_scorecard.json \
    evaluation/results/gemma4_12b_prompt_v2_format_json_reconsideration_v1_final_comparison.json \
    evaluation/results/gemma4_12b_prompt_v2_format_json_reconsideration_v1_full_final_review.json \
    evaluation/results/gemma4_12b_prompt_v2_format_json_reconsideration_v1_gold012_material_review.json \
    ./evaluation/results/

# Instala a aplicação no ambiente do container
RUN uv sync --frozen

# Sem ENTRYPOINT fixo: `docker compose run --rm app bash` abre o shell.
CMD ["consultor-juridico"]
