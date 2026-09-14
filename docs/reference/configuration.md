# Configuração

As configurações são carregadas por Pydantic Settings a partir do ambiente e,
opcionalmente, de `.env`. Não versione credenciais reais.

| Variável | Uso | Padrão no Compose |
|---|---|---|
| `DATABASE_URL` | conexão SQLAlchemy | PostgreSQL `db:5432` |
| `POSTGRES_*` | banco e credenciais locais | `consultor_juridico_v02` |
| `OLLAMA_BASE_URL` | endpoint interno | `http://ollama:11434` |
| `OLLAMA_HOST_PORT` | porta publicada | `11435` |
| `INGESTION_*_TIMEOUT` | limites HTTP do bootstrap | 10/30/10/10 s |
| `INGESTION_MAX_ATTEMPTS` | tentativas de aquisição | 3 |
| `PLANALTO_USER_AGENT` | identifica aquisição oficial | valor do `.env.example` |

Portas: PostgreSQL `localhost:5434`; Ollama do mesmo Compose
`localhost:11435` no host e `http://ollama:11434` entre serviços. Uma instância
Ollama nativa em `localhost:11434` não é suportada pelo projeto.

O modelo, prompt e parâmetros de geração pertencem ao freeze e não são knobs de
tuning operacional. O bootstrap pode acessar o Planalto e baixar o modelo;
consultas nunca acessam a web.
