# Contexto Compartilhado — Snapshot Verificado

> Estado conferido em 14/11/2026, após o release da exclusão de documentos. O SHA local indicado é a base do checkout de trabalho no início desta atualização; após o commit, use `git rev-parse HEAD` para descobrir o HEAD atual. Não usar este snapshot como substituto de uma nova verificação.

## Identificação da sessão

| Campo | Valor | Validade |
|---|---|---|
| Data | 14/11/2026 | confirmado |
| Agente que conferiu este snapshot | Codex | confirmado |
| Branch local | `feat/knowledge-index-governance` | confirmado |
| SHA de entrada do checkout de trabalho | `6972bc8342282fd52f57b2273c8e938c3a76335b` | confirmado |
| SHA local da referência `main` | `b83e589d59355eb267e4d73f668b17501816a852` | confirmado |
| SHA de saída desta atualização | Consultar `git rev-parse HEAD` no checkout após commit/push | referência operacional |
| Remotos conferidos | GitHub (`origin`) e VPS (`/opt/orquestra`) | confirmado |
| Checkout VPS limpo | Sim, detached em `b83e589` | confirmado |
| Checkout principal limpo | Não; branch de trabalho tem modificações e arquivos não rastreados anteriores a esta tarefa | confirmado |

## Estado de publicação (três linhas independentes)

| Linha | SHA | Data | Evidência | Validade |
|---|---|---|---|---|
| Checkout de trabalho (local) | Branch `feat/knowledge-index-governance`, base `6972bc8`, working tree sujo | 14/11/2026 | `git status --short --branch --untracked-files=all` e `git rev-parse HEAD` | confirmado |
| Referência local `main` | `b83e589d59355eb267e4d73f668b17501816a852` | 14/11/2026 | `git rev-parse main` após fetch/merge da PR #14 | confirmado |
| `main` no GitHub (`origin/main`) | `b83e589d59355eb267e4d73f668b17501816a852` | 14/11/2026 | `git fetch origin main`; PR #14 em estado merged | confirmado |
| VPS Hostinger (`/opt/orquestra`) | `b83e589d59355eb267e4d73f668b17501816a852`, detached e limpo | 14/11/2026 | `scripts/release.py` e verificação SSH pós-deploy | confirmado |
| Revisão do banco | `0012_conversation_memory` | 14/11/2026 | consulta Alembic somente leitura via helper de release | confirmado |
| Serviços pós-release | API, worker, scheduler, DB e Redis saudáveis; worker respondeu ping Celery | 14/11/2026 | `docker compose ps`, `celery inspect ping`, `/health` e HTTP da página | confirmado |
| Saída WhatsApp global | `OUTBOUND_ENABLED=false` em API e worker | 14/11/2026 | inspeção somente da variável nos containers | confirmado |

## Pedido e não entregue

| Pedido | Evidência no código | Estado | Validade |
|---|---|---|---|
| "digitando…" (`presence_enabled`) | `ZapiTransport.composing` e `WameTransport.composing` devolvem `False`, não chamam API | não implementado | confirmado (código) |
| Indexação com revisor + decisor | `routes_knowledge.py`, `knowledge_indexing.py`, migration `0013` | alterações locais visíveis; não integrado nem publicado. Alegações de testes no handoff local não rastreado não foram reexecutadas nesta conferência | código local confirmado; testes não verificados |
| Roteamento de modelos por empresa | `docs/planos/2026-11-13-roteamento-modelos-empresa-e-agentes.md` | planejado, não implementado | documentado |

## Autorizações com prazo

| Ato | Data | SHA | Autorizado por | Válido até |
|---|---|---|---|---|
| Merge da exclusão de documentos (PR #14) | 14/11/2026 | `b83e589d59355eb267e4d73f668b17501816a852` | Usuário | consumida — concluída |
| Deploy da exclusão de documentos | 14/11/2026 | `b83e589d59355eb267e4d73f668b17501816a852` | Usuário | consumida — concluída |
| Aplicar migration | — | — | — | nenhuma migration neste release; demais autorizações não presumidas |
| Ligar envio (`OUTBOUND_ENABLED`) | — | — | — | não autorizado; permanece `false` |

> Autorização de uma sessão não se estende à seguinte.

## Regras ativas (referência, não copiar)

- Regras duradouras: `docs/ai/DECISIONS.md`
- Riscos: `docs/ai/KNOWN_RISKS.md`
- Handoffs datados: `docs/handoff/` (índice em `docs/ai/HANDOFF_INDEX.md`)
- Protocolo: `docs/ai/CONTINUITY_PROTOCOL.md`

## Próxima ação e verificações necessárias

- Revisar o diff e a migration `0013_knowledge_index_governance` da branch `feat/knowledge-index-governance`; reexecutar os testes pertinentes em ambiente descartável antes de aceitar os resultados relatados em registros locais não publicados.
- Decidir separadamente se a governança de indexação deve seguir para PR; não aplicar migration em produção sem revisar compatibilidade, backup e autorização.
- Antes de qualquer nova publicação, verificar novamente GitHub, checkout da VPS, revisão do banco, imagens e saúde dos serviços. Os dados acima são um snapshot de 14/11.
