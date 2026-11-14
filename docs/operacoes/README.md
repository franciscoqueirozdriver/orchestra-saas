# Registro de Operações Compartilhado — Orquestra / diBBerDesk

Ponto de entrada operacional para todos os agentes que atuam neste repositório (humano, Codex, Cursor, OpenCode). Cada informação tem sua fonte principal; esta pasta apenas agrega e aponta.

## Fontes principais (não duplicar aqui)

- Estado, decisões e riscos: `docs/ai/CURRENT_STATE.md`, `docs/ai/DECISIONS.md`, `docs/ai/KNOWN_RISKS.md`
- Fluxo de mensagens: `docs/ai/MESSAGE_FLOW.md`
- Protocolo de continuidade: `docs/ai/CONTINUITY_PROTOCOL.md`
- Índice de handoffs: `docs/ai/HANDOFF_INDEX.md`
- Handoffs datados: `docs/handoff/`

## Estrutura desta pasta

| Arquivo | Propósito |
|---|---|
| `CONTEXTO.md` | Snapshot verificado dos ambientes e estado atual (checkout local, `main` GitHub, VPS, banco) |
| `TAREFAS.md` | Quadro de tarefas com reserva temporária por arquivos |
| `INDICE.md` | Histórico curto de entregas com SHA e links |
| `INCIDENTES.md` | Problemas, causas, correções e pendências |
| `PROMPTS_E_RESULTADOS/` | Somente prompts e resultados relevantes, sanitizados |

## Controles de memória confiável (protocolo)

1. **Evidência e validade:** cada afirmação sobre o sistema deve apontar para código, teste, commit ou verificação de produção, com data. Classificar como: confirmado, documentado, inferido ou pendente de verificação.
2. **Estados distintos da tarefa:** pendente, assumida, bloqueada, implementada, testada, integrada, publicada. “Feito” não significa automaticamente “testado” ou “em produção”.
3. **Reserva temporária de tarefa:** responsável, escopo, branch, SHA de entrada e horário da última atualização. A reserva expira se não for renovada.
4. **Registro de release:** SHA no GitHub, SHA na VPS, revisão do banco, estado dos serviços e verificações feitas. Nunca guardar credenciais, dados de clientes ou conteúdo de conversas.
5. **Registro de incidentes:** causa, impacto, correção, evidência de resolução e risco restante.
6. **Limite para prompts:** guardar apenas prompts que levaram a decisões ou mudanças relevantes, com resumo da resposta e como foi verificada. Não arquivar conversas inteiras por padrão.
7. **Markdown no Git não é memória em tempo real:** para todos verem uma atualização, ela precisa ser commitada e enviada ao GitHub, e os outros precisam atualizar o checkout. Conferir o SHA e sincronizar antes de começar. Nunca tratar anotação não publicada como compartilhada.
8. **Um escritor por vez em `CONTEXTO.md`:** quem encerra a sessão atualiza o arquivo no commit dela. Se o arquivo mudou desde o início, relê e ajusta os fatos, sem reescrever por cima.

## Regras de ouro

- Não criar `docs/operacoes/HANDOFFS/`.
- Não copiar regras do Enrico para um segundo arquivo de decisões.
- Não preencher estado de produção sem conferir no Git e no código da sessão.
- Separação clara de ambientes: checkout de trabalho, `main` no GitHub, produção na VPS e revisão do banco, cada um com data e evidência.
