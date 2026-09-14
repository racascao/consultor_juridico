# 09. Answerer local

## Objetivo

Enviar pergunta e evidências autorizadas ao Gemma4:12b pelo Ollama e obter a
resposta bruta, sem ainda aceitá-la como contrato válido.

## Onde estamos e incremento

```text
question + EvidenceItems → prompt → OllamaSelectedAnswerer → raw JSON text
```

## Arquivos desta etapa

- `application/gold_evidence/prompt.py`;
- `application/rag/ports.py`;
- `infrastructure/ollama/selected_answerer.py`;
- `evaluation/selected_answerer.py` e freeze JSON;
- testes `test_v02_selected_answerer.py` e `test_v02_gold_ollama_runner.py`.

## Prompt assembly

`system_prompt_for("2")` fixa o contrato comportamental. `build_user_prompt`
serializa pergunta e cada evidência com `stable_key` e texto. Não passe HTML,
resultados fora do EvidenceSet ou instruções vindas do corpus.

```python
class FrozenAnswerer(Protocol):
    def generate(self, *, system_prompt: str, user_prompt: str) -> str: ...
```

A aplicação depende dessa porta, não de HTTPX. Isso permite testar o pipeline
com answerer fake.

## Adapter Ollama

Recorte fiel ao contrato do payload (tratamento completo de erros foi omitido):

```python
payload = {
    "model": "gemma4:12b",
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    "think": False,
    "format": "json",
    "stream": False,
    "options": {
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 20,
        "repeat_penalty": 1.0,
        "num_predict": 1024,
        "num_ctx": 8192,
    },
}
response = client.post(f"{base_url}/api/chat", json=payload)
response.raise_for_status()
message = response.json()["message"]
if message.get("thinking"):
    raise SelectedAnswererError("THINKING_RETURNED_WHEN_DISABLED")
return message["content"]
```

Antes de gerar, `_validate` consulta `/api/tags` e compara modelo/digest com o
freeze. Ausência, digest diferente, HTTP inválido ou campo `response` ausente
gera `SelectedAnswererError`; não existe fallback para modelo do host.

## Configuração congelada

```text
model=gemma4:12b
digest=4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c
prompt=gold-evidence-answering/2
thinking=disabled  format=json  stream=false  timeout=180
temperature=0.7  top_p=0.8  top_k=20  repeat_penalty=1.0
num_predict=1024  num_ctx=8192
```

Dentro do Compose, use `http://ollama:11434`. No host, a mesma instância é
exposta em `localhost:11435`; `localhost:11434` não pertence ao projeto. GPU é
necessária para a latência aceitável observada do modelo de 12B.

## Testes

Com `httpx.MockTransport`, valide URL, payload exato, timeout, digest,
`stream=false`, `format=json`, respostas HTTP e JSON malformadas. O timeout de
180 s é configurado no `httpx.Client` no composition root. Não execute
inferência nos testes automáticos.

```bash
uv run pytest tests/test_v02_selected_answerer.py \
  tests/test_v02_gold_ollama_runner.py -q
```

Uma chamada manual é opcional e só deve ocorrer após `ollama list` confirmar o
digest. Preserve a saída bruta; não faça retry para escolher resposta melhor.

## Checkpoint

Os testes provam payload e fail-closed. Um fake retorna texto bruto ao pipeline.
Ainda não confiamos nesse texto: o próximo capítulo fecha o contrato JSON.

**Anterior:** [Evidence Assembly](08-evidence-assembly.md).  
**Próximo:** [Structured Output](10-structured-output.md).
