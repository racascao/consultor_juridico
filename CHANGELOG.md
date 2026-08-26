# Changelog

## 0.1.0 — MVP1 congelado

### Adicionado

- corpus oficial CF/88 + ADCT com captura binária, hash e proveniência;
- parsing determinístico, identidade normativa, materialização e retrieval
  híbrido (FTS + pgvector);
- EvidenceSet, citações, locator fidelity, polarity guard e validação semântica;
- EBCG_V2 para respostas controladas por evidência, sem geração jurídica livre;
- CLI de ingestão, parsing, indexação, retrieval, consulta e modo interativo.

### Segurança e qualidade

- cadeia auditável até a fonte oficial;
- abstenção fail-closed quando a evidência não é suficiente;
- modelo do juiz semântico congelado em `ministral-3:8b`;
- avaliação offline v2: 8/10 respondíveis corretos, 1/1 abstenção correta e
  zero respostas inseguras.

### Limitações conhecidas

- `Hit@10=0.900` permanece abaixo do threshold histórico de `0.905`;
- E2E nativo final contra v2, qualifier preservation e formal stability ainda
  não foram medidos;
- contexto estrutural de prisão perpétua e retrieval de estado de sítio seguem
  como limitações documentadas.
