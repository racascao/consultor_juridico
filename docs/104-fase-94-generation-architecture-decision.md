# Fase 94 — MVP1 Generation Architecture Decision

## Decisão

O MVP1 deixa de tratar o LLM Generator como autor de proposições jurídicas. A
próxima implementação adotará **Evidence-Bound Controlled Generation v1
(EBCG-v1)**: a proposição jurídica apresentada ao usuário será uma reprodução
controlada do snapshot de uma única evidência já autorizada.

Essa decisão substitui a geração livre de `claim.text`; não altera retrieval,
ranking, seleção, sufficiency, modelos, schema ou os experimentos congelados.

## Informação decidida antes do LLM

Antes de qualquer chamada opcional ao LLM, o pipeline já determina:

1. a pergunta do usuário;
2. o `EvidenceSet` persistido e seus EvidenceItems validados;
3. o conjunto de candidatos escolhido pelo selector existente;
4. o snapshot textual, código, rótulo de citação, URL e cadeia documental de
   cada EvidenceItem;
5. a Core Evidence e a Core Claim determinísticas descritas abaixo.

Não há classificação nova de relevância, `core_answer`, dependência material
ou intenção jurídica da pergunta. Isso evita reintroduzir o bloqueio do Atomic
Claim Acceptance.

## Core Evidence

A Core Evidence é o EvidenceItem com o menor sufixo numérico de
`evidence_code` no EvidenceSet (`EV001`, quando presente). Esse código já é
atribuído pelo `build_evidence_set` conforme a ordem final do selector atual.

Logo, EBCG-v1 é uma **projeção determinística da seleção já aprovada**, não um
novo ranking ou uma segunda Evidence Selection. A escolha deve ordenar pelos
códigos, e não confiar na ordem incidental de `EvidenceSet.items`, pois o
relacionamento ORM não declara ordenação física.

Se não houver EvidenceItem validado e textual para essa posição, a resposta é
abstenção canônica. Não há fallback para outro item: esse fallback seria uma
nova política de seleção e está fora desta decisão.

## Core Claim controlada

Para a Core Evidence `EV001`, o runtime cria exatamente:

```text
C1.text           = EV001.text_snapshot.strip()
C1.evidence_codes = ("EV001",)
answer             = C1.text
```

Não há paráfrase, complemento, artigo manual, inferência, combinação de
evidências ou conteúdo escrito pelo modelo. A claim é um excerto factual da
fonte oficial e a Citation existente fornece label, URL e cadeia auditável.

`parent_context` continua disponível somente nos caminhos de validação já
existentes. Ele não é concatenado à Core Claim, pois isso criaria uma
composição de elementos sem uma citação independente do pai e reabriria VCSA.

## Papel residual do LLM

O Generator LLM deixa o caminho de produção de claims jurídicas. O único papel
residual do LLM no MVP1 é o **Semantic Support Validator como veto
fail-closed**: ele pode rejeitar uma Core Claim, mas nunca cria, reescreve,
expande ou promove uma proposição jurídica.

Não existe fallback para geração livre se esse veto falhar. O resultado é a
abstenção canônica.

## Cadeia de validação preservada

Após a construção controlada, a ordem continua:

```text
Core Claim determinística
  -> Attribution determinística (deve confirmar somente EV001)
  -> Locator Fidelity Guard
  -> Citation Validator
  -> Polarity Guard
  -> Semantic Support Validator (veto)
  -> persistência/renderização ou abstenção
```

Qualquer alteração da attribution para outro EvidenceItem, cadeia de citação
inválida, locator incompatível, polaridade bloqueada ou suporte semântico
inconclusivo produz abstenção. Citations, locators e provenance continuam sendo
derivados de EvidenceItems; a prosa não é autorizada a inventá-los.

## Componentes reutilizados

- `build_evidence_set` e os snapshots atuais;
- `GeneratedResponse` e `GeneratedClaim`;
- `deterministically_attribute`, como confirmação e não escolha da Core;
- Locator Fidelity Guard;
- Citation Validator e persistência existente de Claim/Citation;
- Polarity Guard;
- Semantic Support Validator;
- renderer atual de citations e abstenção canônica.

Não serão integrados: Atomic, VCSA materialization, Structural Expansion,
Structural Reserve e ajustes experimentais de Evidence Selection.

## Menor plano de implementação único

1. Criar um construtor puro `EvidenceBoundGenerator` compatível com a interface
   atual de geração, sem HTTP/Ollama, que seleciona `EV001` por código e cria
   `C1` a partir de `text_snapshot`.
2. Trocar somente o wiring de produção de Generator no serviço/composição da
   CLI pelo construtor controlado; o modelo `ministral-3:8b` permanece apenas
   no Semantic Support Validator.
3. Exigir que a attribution confirme `C1 -> EV001`; qualquer reatribuição
   falha fechadamente.
4. Reusar sem alterações os validators e a persistência atuais.
5. Adicionar testes puros de determinismo, ordenação por `evidence_code`,
   fidelidade textual, ausência de chamada LLM e preservação de validators.
6. Executar uma única medição E2E no destino explícito da Fase 93. Se atingir
   `>=9/10`, `unsafe=0` e a abstenção esperada, parar e seguir para stability.

## Limitações aceitas

EBCG-v1 responde somente por um excerto normativo central já selecionado. Não
é um sintetizador de múltiplas disposições, não reconstrói pai+filho e não
resolve estado de sítio. Uma seleção incorreta ou um fragmento incapaz de
sustentar sozinho a resposta resulta em abstenção, não em expansão heurística.

## Estado

Arquitetura congelada para uma única implementação posterior. Esta fase não
alterou código, não executou LLM, não modificou banco e não realizou E2E.
