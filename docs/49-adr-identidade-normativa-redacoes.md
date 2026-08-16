# ADR — Identidade normativa separada de ocorrências documentais

## Status

Proposto para revisão arquitetural na Fase 4B.3.3.

## Contexto

A captura oficial apresenta múltiplas redações normativas do mesmo artigo e
rubricas históricas alternativas. Interpretar cada LegalElement como identidade
produziu 65 chaves ARTICLE duplicadas; consolidá-las sob um único CAPUT perderia
subárvores históricas e violaria o modelo 004.

## Alternativas

1. manter cada redação como identidade LegalElement;
2. permitir múltiplos CAPUTs;
3. criar um element_type REDACTION;
4. separar identidade (`LegalProvision`) de ocorrência (`LegalElement`);
5. criar ainda uma terceira entidade LegalRedaction.

## Decisão proposta

Adotar duas camadas. `LegalProvision` representa identidade normativa estável por
LegalAct e ancestralidade normativa. `LegalElement` representa uma ocorrência
documental daquela identidade em uma LegalVersion. Redação é a ocorrência raiz e
sua subárvore; não se cria LegalRedaction no MVP1.

Status, texto, ordem e proveniência pertencem a LegalElement. NOTE não possui
LegalProvision. Cada ocorrência ARTICLE conserva exatamente um CAPUT. Ocorrências
históricas e corrente podem apontar para o mesmo provision, com no máximo uma
CURRENT por provision em cada LegalVersion.

`LegalElement.legal_act_id` é redundância física controlada. Sua autoridade
semântica continua sendo `LegalVersion.legal_act_id`; FKs compostas impedem que a
ocorrência pertença a versão ou provision de outro ato e impedem divergência de
`element_type` entre occurrence e provision.

## Consequências

- artigos e headings históricos são preservados sem duplicar identidade;
- a identidade sobrevive a reparse e novas capturas;
- Chunk continua ligado ao texto exato por LegalElement;
- Evidence e Citation alcançam identidade e snapshot documental;
- migration 005 cria uma tabela, duas colunas e FKs compostas em LegalElement;
- o parser ganha reconciliação determinística de identity_key;
- mudanças reais de ancestralidade continuam podendo exigir revisão fechada;
- nenhuma temporalidade legal ou evento de Emenda é inferido.
