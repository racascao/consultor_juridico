# Limitações

O MVP2 foi aceito com limitações conhecidas:

- corpus restrito à Lei Federal nº 9.784/1999;
- retrieval exclusivamente lexical e recall inicial de 26/44 provisions no
  Blind HOLDOUT, ampliado para 40/44 pelo assembly estrutural;
- contrato de saída válido em 34/36 casos do HOLDOUT;
- correção jurídica humana 34/36, completude 32/36 e all-pass 32/36;
- `CASE_APPLICATION` não aplica a lei a fatos concretos: solicita clarificação;
- sem vector search, embeddings ou RRF no runtime final;
- sem acesso web durante a consulta;
- streaming real não integra o answerer congelado (`stream=false`);
- métricas automáticas e revisão jurídica humana podem divergir.

O sistema não é uma fonte jurídica autônoma nem substitui análise profissional.
Quando o contrato ou a evidência falham, a arquitetura prefere falhar fechado.

O HOLDOUT v1 está fechado para desenvolvimento. Melhorias exigem novo baseline,
dataset DEV independente e uma versão posterior.
