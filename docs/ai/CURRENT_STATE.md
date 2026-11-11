# Estado atual comprovado no repositório

**Snapshot de referência:** 09/11/2026, `main` e `origin/main` em `40272d0` (`Evita deadlock do
checkpointer ao gerar respostas.`). Git exibia dois caminhos não rastreados locais:
`Kit Marca/` e `docs/conhecimento/base-atendimento-climatiza-brasil.md`. Seus conteúdos
foram preservados e não foram inspecionados nem adicionados. Nenhuma alteração foi
feita antes deste documento.

Esta página é um snapshot do checkout, não um atestado de produção. “Implementado”
significa que o código correspondente existe; não implica execução, CI verde ou
homologação de fornecedor.

## Vocabulário de status

- **IMPLEMENTADO:** há código correspondente na revisão indicada.
- **TESTADO:** teste/comando foi executado com resultado registrado para uma revisão
  específica. Nenhum teste foi executado nesta auditoria.
- **DOCUMENTADO:** a evidência disponível está em documentos, sem comprovação de código.
- **PLANEJADO:** aparece em plano/TODO, sem implementação confirmada.
- **DESCONHECIDO:** não foi possível confirmar, em especial estado externo/produção.

## Funcionalidades e evidências

| Área | Estado | Evidência observada | O que não se conclui |
|---|---|---|---|
| Login, usuários e seleção de empresa | Implementado | `routes_auth.py`, `routes_users.py`, `dependencies.py`, `models.py` | Auditoria completa de autorização/tenant não foi executada nesta tarefa |
| Agentes, regras de conversa e envio humano no painel | Implementado | `routes_agents.py`, `routes_conversations.py`, `conversation/`, `tasks.py` | Qualidade conversacional em produção não foi avaliada |
| Conexões Z-API e WAME | Implementado no código | `routes_zapi.py`, `transport.py`, `zapi_client.py`, `wame_client.py`, UI `frontend/app.js`; commits `68fc944`, `13ca542`, `895393a`; `docs/conexoes-whatsapp.md` documenta WAME oficial/QR e Z-API QR | Não confirma credenciais válidas, sessão conectada, callbacks, envio ou entrega reais; código da API oficial Z-API não está disponível na tela |
| Criar grupo por API e escalonamento humano | Implementado no código | `routes_zapi.py`, `interventions.py`, `schemas.py`, `models.py`, migration `0009`, `docs/intervencao-humana-grupo.md`; commit `707fa3c` | Não comprova grupo criado, validação operacional ou aceite concorrente em serviço real |
| Modelos de conversa, conexões e fallback | Implementado no código | `routes_llm.py`, `model_router.py`, `llm_client.py`, catálogo `provider_catalog.py` (Gemini, Groq, Mistral, OpenRouter, OpenAI, xAI, Anthropic e OpenAI-compatible) | IDs de modelo são manuais; catálogo explicitamente não verifica provedores em tempo real. Cadastro não valida acesso nem quotas externas |
| Armazenar documentos e indexar sob demanda | Implementado no código | `routes_knowledge.py`, `embedding_config.py`, `models.py` | Upload não indexa automaticamente; embeddings exigem configuração compatível e não foram homologados aqui |
| Histórico importado e contexto por conversa | Implementado no código | migrations `0008`, models `HistoricalImportBatch`, `ConversationContactAlias`, `Message`; `routes_conversations.py`, `tasks.py`, `history_import.py` | Não implica aprendizado automático nem conhecimento factual aprovado |
| Pipeline privado de conversas | Implementado como ferramentas locais | `scripts/private_knowledge/`, `docs/conhecimento/ingestao-local-whatsapp.md` | Não é parte do serviço da aplicação; material bruto não foi examinado nesta auditoria |
| Grupo de atendimento | Implementado no código; homologação pendente | `interventions.py`, `routes_zapi.py`, migration `0009`, `docs/intervencao-humana-grupo.md` | Envio de teste é externo e real; estado `validated` é confirmação organizacional, não confirmação de leitura fornecida pela API |
| Conversas importadas como base de busca | Não automático; fluxos separados | histórico em `messages`; conhecimento indexado em `knowledge_documents/chunks` | Não assumir que histórico foi indexado ou que conversa histórica virou regra |
| Envio humanizado em blocos | Implementado localmente como política global do canal; sem homologação externa | branch `feat/enrico-context-booking`: `split_reply_conversational` e partes do outbox existente; resposta curta fica inteira, demais até 3 blocos de 300 caracteres, intervalo fixo de 2 s; campos antigos de perfil são mantidos apenas por compatibilidade e não controlam a entrega | Respostas acima do limite seguro escalam para intervenção; composing segue desativado; chamada externa já iniciada não é cancelável; não foi feito deploy |
| Qualificação e encaminhamento para visita técnica | Implementado localmente, opt-in por capacidade do perfil do agente | `ConversationProfile.visit_booking_enabled`, falso por padrão; sem migration, em `feat/enrico-context-booking` | Habilitar apenas agentes com fluxo de visitas real; nenhum agendamento automático sem confirmação operacional; homologação humana ainda pendente |
| Integração com Instagram, billing SaaS, ferramentas MCP/CRM/agenda, multiagente | Planejado ou não verificado | `TODO.md`, `docs/intencoes/`, documentação de contratação | Documentação/proposta não demonstra implementação |

## Banco e migrations

Os modelos atuais declaram `tenants`, `users`, `agents`, `zapi_instances`, `llm_configs`,
`conversations`, `historical_import_batches`, `conversation_contact_aliases`, `messages`,
`webhook_events`, `knowledge_search_configs`, `knowledge_documents`, `knowledge_chunks`,
`memory_items`, `outbox_messages`, `model_runs`, `conversation_turns`,
`conversation_actions`, `intervention_requests` e `outbox_parts` (`backend/app/models.py`).
Isso descreve o ORM do checkout, não o schema efetivamente aplicado em qualquer banco.
O bootstrap de banco declara usuário de aplicação separado do superuser (`database/init/01-app-user.sh`). Busca por declarações de RLS/policies na cadeia atual não encontrou políticas PostgreSQL; o isolamento observado nas rotas é aplicação/backend. Isso não substitui auditoria completa de consultas.

Cadeia local em `backend/migrations/versions/`: `0001_initial` → `0002_delivery_controls`
→ `0003_model_routing` → `0004_model_run_uniqueness` → `0005_conversation_core` →
`0006_knowledge_storage` → `0007_search_connection` → `0008_historical_conversations` →
`0009_human_interventions` → `0010_wame_api_base_url`. Não foi consultado banco nesta
auditoria e nenhuma migration foi executada.

## Testes

Existem testes unitários, integração com banco descartável condicional, testes de
contratos e UI em `tests/`. A existência dos arquivos não informa seu resultado atual.
Nesta auditoria não foram executados testes, CI nem verificações de build. Histórico
de resultados está datado em handoffs/relatórios; confira o commit correspondente antes
de reutilizá-lo.

## Git e publicação

O checkout local estava alinhado ao ref local `origin/main` em `40272d0`. O histórico
visível contém commits de suporte a WAME, grupos de intervenção e ajuste do checkpointer.
O estado atual do GitHub remoto não foi consultado pela rede. O estado do checkout,
imagens, banco e serviços da VPS também não foi consultado. O handoff de 06/11 descreve
uma publicação no estado de então; os commits posteriores tornam inadequado tratá-lo
como fotografia atual.

## Trabalho em andamento — branch local

Em `feat/enrico-context-booking`, a segmentação global e as correções de continuidade
estão alteradas localmente sobre `46bd99c`. A implementação reutiliza `outbox_parts` e não
adiciona migration. Ver `docs/handoff/2026-11-10-envio-humanizado.md` para os arquivos,
verificações iniciais; o handoff `docs/handoff/2026-11-10-contexto-conversacional-global.md`
registra a atualização global da entrega. Suítes unitária (154) e de integração (58)
passaram em containers locais; dois testes de integração foram pulados por ausência da
baseline histórica. A UI sintética foi atualizada para confirmar que não há toggle por
agente. Homologação externa não foi executada. O núcleo global instrui resposta concisa
e completa na primeira geração; excesso ainda escala sem uma segunda geração. A entrada e o dispatcher compartilham lock de tenant:
evento, incremento de revisão e cancelamento de partes pendentes são transacionais; o
worker reconhece o marcador interno para não repetir a invalidação. A chamada externa
que já iniciou não é cancelável e uma identidade de contato ambígua não é atribuída por
inferência. `respond_to_conversation` aguarda se há evento preemptivo ainda não
processado para a conversa. Não houve commit, publicação ou alteração na VPS.

## Continuidade conversacional e visitas — alteração local em `feat/enrico-context-booking`

**IMPLEMENTADO no código local:** o núcleo comum mantém um resumo estruturado e com prazo dentro de `Conversation.context_state`, adicional ao histórico de mensagens. Registra fatos explícitos com referência da mensagem e tempo; no primeiro uso também reconstrói o resumo a partir de até 200 mensagens recentes de conversas preexistentes, exceto quando o contexto expirou. Usa telefone numérico direto do provedor como metadado não confirmado; evita enviar dígitos do telefone ao modelo; confirma com o cliente o canal de WhatsApp ou alternativo; e identifica a pessoa que receberá a equipe sem inferir nome de perfil ou papel de decisor. As regras de linguagem, continuidade e envio em blocos são globais. O perfil de agente continua sendo a fonte de especialidade, produto, tom e objetivo; fluxos de negócio como qualificação para visita dependem da capacidade individual `visit_booking_enabled`.

**IMPLEMENTADO:** quando os dados necessários da visita estão completos, o backend solicita validação pelo fluxo existente de intervenção humana. Sem agenda integrada ou confirmação operacional, o status permanece `awaiting_confirmation` e o texto não declara visita marcada. O resumo estruturado é incluído no contexto da equipe, com telefone somente depois de autorizado. Nenhuma tabela ou migration nova.

**TESTADO em 10/11/2026:** 154 testes unitários passaram; 58 testes de integração passaram no PostgreSQL descartável e 2 testes de consolidação de migrations foram pulados porque a baseline histórica não estava disponível. Os testes sintéticos cobrem conversa preexistente, igreja, escolha de data/horário, retorno por telefone autorizado, tentativa do modelo de confirmar sem agenda, recebedor terceiro, grupo de atendimento não configurado, datas alternativas e isolamento do fluxo de visitas por capacidade de agente. Sem chamadas reais a fornecedores. Consulte `docs/handoff/2026-11-10-contexto-conversacional-global.md`.

**NÃO HOMOLOGADO:** extração determinística pode não reconhecer mensagens ambíguas; não há integração de agenda e não foram homologados fornecedores, grupo real nem a experiência com clientes. O estado da VPS e publicação não foram consultados nem alterados.

## Sincronização autorizada — verificação de 10/11/2026

O commit `d17d85a07c760275d59efe604b90eef03a46067b` está confirmado no checkout
local `main`. A verificação de migrations mostrou que a mudança não altera
`backend/migrations/`; o novo campo de capacidade reside no JSON já existente do perfil.
Os testes locais registrados acima foram executados antes do commit. A branch de
trabalho também aponta para esse commit.

**GitHub e VPS não estão confirmados como sincronizados.** O ref local em cache
`origin/main` ainda aponta para `40272d03188dc14accdb8c63b65b8763435de7de`; o push
falhou porque `github.com:22` expirou, SSH-over-443 também expirou e `gh auth status`
reportou token salvo inválido. Uma consulta direta ao ref remoto expirou, então o SHA
remoto atual é desconhecido. O SSH da VPS `orquestra@2.25.101.96` também expirou; o
HEAD e a limpeza de `/opt/orquestra` não foram verificados nesta etapa. Nenhum deploy,
migration ou alteração remota foi executado. Ver o handoff
[`2026-11-10-tentativa-sincronizacao.md`](../handoff/2026-11-10-tentativa-sincronizacao.md)
antes de retomar a publicação.
