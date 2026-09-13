# Custódia do Blind HOLDOUT do MVP2

## Objetivo

Este procedimento permite ao custodiante criar e selar o HOLDOUT sem revelar
seus casos ao processo de desenvolvimento. O runtime permanece congelado como
`integrated-runtime-mvp2/1`, SHA-256
`5f0df6b41f0d35fcba0a514777a2370385620007ff3e6122473ca6793067514d`.

## Preparação pelo custodiante

1. Copiar os três templates públicos de `evaluation/holdout/templates/` para
   um ambiente de custódia separado.
2. Criar os casos sem codificar no `case_id` seu modo ou resultado esperado.
3. Definir, antes da execução, a decisão esperada, categoria e disposições de
   suporte conforme o schema público.
4. Atribuir cada `case_id` exatamente uma vez a `LEGAL_RULE` ou
   `CASE_APPLICATION` no mapping externo.
5. Calcular o SHA-256 byte a byte do dataset e registrá-lo no mapping e no
   manifest; calcular também o SHA-256 do mapping e registrá-lo no manifest.
6. Preencher datas, contagem e identidade do freeze no manifest e selar os três
   arquivos sem executar o runtime.

Os casos devem ter origem independente, como formulação humana nova, amostragem
independente do corpus ou cenários definidos antes de qualquer execução. Não se
deve copiar ou parafrasear trivialmente o DEV, reutilizar seus `case_id`, nem
desenhar o conjunto para favorecer ou atacar resíduos conhecidos. O custodiante
decide uma quantidade suficientemente diversa; este contrato não fixa uma
distribuição nem um total além do mínimo estrutural de um caso.

O `QueryMode` registra a intenção declarada do caso. Ele não pode ser inferido
da pergunta, da decisão esperada ou da resposta do sistema; em particular,
`CLARIFY` não implica `CASE_APPLICATION`.

Os nomes privados esperados são:

```text
evaluation/holdout/private/blind_holdout_mvp2_v1.json
evaluation/holdout/private/blind_holdout_query_mode_mapping_v1.json
evaluation/holdout/private/blind_holdout_manifest_v1.json
```

## Validação estrutural de custódia

Depois de posicionar o pacote privado, o custodiante pode executar:

```bash
uv run consultor-juridico eval holdout-validate \
  --dataset evaluation/holdout/private/blind_holdout_mvp2_v1.json \
  --query-mode-mapping evaluation/holdout/private/blind_holdout_query_mode_mapping_v1.json \
  --manifest evaluation/holdout/private/blind_holdout_manifest_v1.json
```

O comando valida somente estrutura, hashes, identidade do freeze e cobertura
1:1 do mapping. Ele não usa banco, retrieval ou LLM e não imprime perguntas,
targets ou evidências. Essa operação é `CUSTODY_VALIDATION_READ`, não a primeira
leitura pelo runtime.

Após uma validação bem-sucedida, o custodiante deve preservar os bytes e hashes
validados como pacote lacrado e não fazer ajustes orientados por resultados do
runtime.

## Abertura e execução futuras

A `HOLDOUT_RUNTIME_FIRST_READ` só poderá ocorrer em uma sessão independente,
contra o runtime congelado, depois que o custodiante confirmar a selagem. Uma
mudança posterior no runtime invalida a medição cega. Este documento não cria,
abre nem executa o HOLDOUT.
