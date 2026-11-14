# Quadro de Tarefas — Reserva Temporária por Arquivos

> Estados: pendente, assumida, bloqueada, implementada, testada, integrada, publicada. “Feito” não significa automaticamente “testado” ou “em produção”.

| # | Tarefa | Responsável | Branch | SHA de entrada | Última atualização | Arquivos reservados | Estado | Expiração |
|---|---|---|---|---|---|---|---|---|
| OP-2026-11-14 | Registrar memória compartilhada e sincronizar apenas `docs/operacoes/` | Codex | `feat/knowledge-index-governance` | `6972bc8342282fd52f57b2273c8e938c3a76335b` | 14/11/2026 | somente `docs/operacoes/` | implementada; commit/push desta tarefa em andamento | ao encerrar |
| KI-2026-11-13 | Revisar e decidir publicação da governança/fallback da indexação, incluindo migration `0013` | Não atribuído | `feat/knowledge-index-governance` | `6972bc8342282fd52f57b2273c8e938c3a76335b` | 14/11/2026 | alterações locais em `backend/app/`, `backend/migrations/versions/0013_knowledge_index_governance.py`, `frontend/app.js`, testes e documentos relacionados | pendente de revisão; não integrada/publicada; resultados de testes ainda precisam ser revalidados | sem reserva ativa |

## Regras

- Duas tarefas diferentes não podem gravar nos mesmos arquivos ao mesmo tempo.
- Outros agentes podem ler os arquivos reservados, mas não gravar neles enquanto a reserva estiver válida.
- A reserva expira se não for renovada; tarefas abandonadas não ficam bloqueadas para sempre.
- Ao encerrar a sessão, atualizar o estado e liberar a reserva no commit da tarefa.
- Se o arquivo mudou desde o início da reserva, reler e ajustar antes de gravar.

## Histórico de reservas liberadas

| # | Tarefa | Arquivos | SHA de saída | Data | Estado final |
|---|---|---|---|---|---|
| | | | | | |
