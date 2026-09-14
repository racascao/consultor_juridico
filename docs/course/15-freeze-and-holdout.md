# 15. Freeze e Blind HOLDOUT

## Objetivo

Congelar o runtime antes de uma medição cega, preservar a cadeia de custódia e
registrar uma decisão de release honesta.

## Onde estamos e incremento

```text
DEV validado → answerer freeze → runtime freeze → Blind HOLDOUT
             → avaliação automática → revisão humana → release 0.2.0
```

## Arquivos desta etapa

- `evaluation/model_selection/*freeze*.json`;
- `evaluation/runtime_freeze/*freeze*.json` e `.sha256`;
- `evaluation/holdout/schemas/` e `templates/` públicos;
- `evaluation/holdout/private/` ignorado pelo Git;
- `evaluation/holdout_custody.py` e `tests/test_holdout_custody.py`;
- `docs/STATE.md` e release notes.

## O que congelar

O answerer freeze deve incluir modelo/digest, prompt/hash, thinking, format,
temperature, top-p/k, penalty, token/context budget, stream, timeout, dataset e
evidências da seleção. O runtime freeze acrescenta retrieval/config, structural
assembly, QueryMode, contrato, Citation Validation e commit de baseline.

Canonicalize JSON antes de calcular SHA-256 e versione o hash ao lado do
manifesto. Na tag oficial:

```text
gold-evidence-selected-answerer/1
d07d5b3ca9feb9c16193a400609215c55ecd5e04f8e26429a035ee51f950e12a

integrated-runtime-mvp2/1
5f0df6b41f0d35fcba0a514777a2370385620007ff3e6122473ca6793067514d
```

Valide programaticamente que o código carregado corresponde ao manifesto. Drift
de qualquer campo invalida a identidade e exige novo freeze.

## Custódia do HOLDOUT

Antes da primeira leitura, preserve externamente dataset, mapping e manifest.
Registre autorização, hash e transição irreversível `FIRST_READ=YES`. Durante a
campanha: runtime imutável, uma execução por caso, nenhum retry oportunista e
raws preservados antes da avaliação.

O repositório pode conter schemas e templates, nunca conteúdo privado:

```gitignore
evaluation/holdout/private/*
```

## Avaliação e decisão

Execute o evaluator automático sem alterar expected; depois realize revisão
humana independente de correção, groundedness, completude e boundary. Preserve
divergências, não "corrija" o gold após ver respostas.

O MVP2 observou 25/36 passes automáticos, 34/36 em correção humana, 36/36 em
groundedness, 32/36 em completude e boundary 36/36. Sem threshold formal
pré-HOLDOUT, a decisão foi qualitativa:

```text
MVP2_ACCEPTED_WITH_KNOWN_LIMITATIONS
HOLDOUT_STATUS=CLOSED_FOR_DEVELOPMENT
```

## Release

Crie a tag somente depois de testes, hashes e decisão documental:

```text
tag=0.2.0
commit=c805ba8eddcbaa91737cb6f9b8cd8f4a6f7fcc3d
```

Não mova uma tag publicada. Documentação pós-freeze pode avançar na `main`,
mas funcionalidade futura pertence ao MVP3 ou outra versão.

## Testes e verificacão

```bash
uv run pytest tests/test_holdout_custody.py \
  tests/test_v02_selected_answerer.py -q
sha256sum evaluation/model_selection/gold_evidence_selected_answerer_freeze_v1.json
sha256sum evaluation/runtime_freeze/integrated_runtime_mvp2_freeze_v1.json
git rev-parse 0.2.0^{}
```

Os hashes e commit devem coincidir com os valores acima. Não execute novamente
o HOLDOUT para escolher resultado melhor.

## Checkpoint final

O sistema agora é funcionalmente equivalente ao MVP2: corpus versionado,
retrieval lexical, evidence estrutural, answerer local, contrato/citação
fail-closed, modos explícitos, CLI e metodologia congelada. Limitações foram
registradas, não ocultadas.

**Anterior:** [avaliação](14-evaluation.md).  
**Referência final:** [estado canônico](../STATE.md).
