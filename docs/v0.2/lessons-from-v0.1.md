# Aprendizados da v0.1

A v0.1.0 permanece congelada e forneceu a base empírica para a reconstrução.
Seus resultados não são descartados nem reinterpretados.

- O benchmark oficial congelado da v0.1 registrou 80%; essa medida pertence
  somente àquele protocolo e dataset.
- Testes manuais com linguagem natural apresentaram desempenho inferior ao
  benchmark e revelaram erros de alvo.
- Evidência verdadeira não implica evidência relevante para a pergunta.
- Rastreabilidade completa não implica correção do alvo jurídico.
- O juiz semântico anterior avaliava suporte da claim, mas não avaliava
  adequadamente a relação pergunta-resposta.
- Validators e heurísticas acumulados aumentaram complexidade sem resolver a
  localização básica de forma geral.
- Condicionais distribuídos por diversos arquivos tornaram o workflow difícil
  de observar e alterar com segurança.
- A otimização avançou antes de retrieval e relevância básicos estarem
  suficientemente estabilizados.

A v0.2 responde a esses aprendizados separando relevância da evidência e
qualidade da resposta, tornando ambiguidade explícita e priorizando retrieval
antes da geração.
