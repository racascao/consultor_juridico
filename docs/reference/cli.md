# CLI

O comando oficial é `consultor_juridico`. O nome legado com hífen não faz
parte do pacote congelado.

```bash
consultor_juridico
consultor_juridico --help
consultor_juridico status
consultor_juridico bootstrap
consultor_juridico tutorial
consultor_juridico consult "Qual é o prazo para decidir o recurso?" \
  --mode legal-rule
```

Sem argumentos e em TTY, abre o menu Rich. Em non-TTY, informa como acessar a
ajuda e encerra com status 2. `status` inspeciona prontidão sem inferência;
`bootstrap` prepara dependências idempotentemente; `tutorial` explica modos e
limites; `consult` oferece uso scriptável.

No Docker:

```bash
docker compose up --build
docker compose run --rm app consultor_juridico
```

O primeiro comando executa o bootstrap one-shot; `app exited with code 0`
significa sucesso. Grupos `db`, `corpus`, `retrieval`, `rag` e `eval` são
interfaces avançadas de administração e diagnóstico.
