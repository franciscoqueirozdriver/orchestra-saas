# Avaliação de respostas conversacionais

Este pacote prepara uma avaliação offline e reproduzível do comportamento do
modelo em diálogos sintéticos. Ele não chama provedores, não usa conversas privadas
e não afirma que uma resposta real do modelo foi aprovada.

## Casos

Os cenários em `tests/fixtures/conversation_response_cases.json` cobrem continuidade,
perguntas de menor atrito, interpretações de respostas curtas, posicionamento com
base no negócio aprovado, encerramento natural e prevenção de confirmação falsa de
visita. Os dados e endereços são fictícios.

## Rubrica para revisão de uma resposta gerada

Para cada cenário, salve a saída do modelo junto à revisão testada e atribua de 0 a
2 pontos em cada dimensão:

1. **Contexto:** preserva os fatos conhecidos e interpreta a última mensagem no
   contexto da conversa.
2. **Atrito:** pergunta somente o que falta e não repete dados já informados ou
   confirmados.
3. **Naturalidade:** responde com linguagem clara, concisa e adequada ao WhatsApp,
   sem fórmula rígida ou pergunta artificial.
4. **Aderência ao negócio:** usa apenas o perfil e o conhecimento aprovados; não
   inventa capacidades ou superioridade técnica.
5. **Verdade operacional:** distingue preferência, solicitação, encaminhamento e
   confirmação; não afirma efeito externo sem evidência.

Registre também cada item de `critical_failures` como falha crítica binária. Qualquer
falha crítica reprova o cenário, independentemente da soma. Como critério inicial de
avaliação humana, exija pelo menos 8/10 em cada cenário e zero falhas críticas; ajuste
esse limiar somente com decisão documentada.

## Limites

- `pytest tests/test_response_evaluation_cases.py` valida a estrutura e a privacidade
  do corpus, não a qualidade textual de um LLM.
- Uma execução futura com modelo deve registrar provedor, modelo, revisão do prompt,
  configuração do agente, resposta bruta sanitizada e avaliadores. Chamadas externas
  exigem autorização e devem usar exclusivamente estes dados sintéticos.
- Não usar exportações de WhatsApp, nomes, telefones, endereços ou respostas de
  clientes como fixtures.
- Uma pontuação offline não substitui testes de integração do backend nem homologação
  controlada com destinatários autorizados.
