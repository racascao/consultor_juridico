# Citation Validation

A validação de citações é obrigatória antes de apresentar a resposta.

```text
Validated Evidence Set
        ↓
       LLM
        ↓
Claims + evidence_ids
        ↓
CitationValidator
        ↓
VALID → resposta
INVALID → regeneração controlada → fallback
```

## Regras

1. Todo `evidence_id` precisa existir no Evidence Set atual.
2. A evidência precisa estar validada.
3. O dispositivo citado deve corresponder ao LegalElement da evidência.
4. Norma e versão devem corresponder.
5. URL deve corresponder ao SourceDocument.
6. Claims factuais relevantes não podem ficar sem evidência.
7. Não aceitar referências que existam apenas no conhecimento paramétrico do modelo.

## Contrato conceitual

```json
{
  "claims": [
    {
      "id": "c1",
      "text": "...",
      "evidence_ids": ["ev-001"]
    }
  ]
}
```

A validação deve consultar o modelo jurídico persistido. Regex pode auxiliar na extração, mas nunca deve ser a autoridade.
