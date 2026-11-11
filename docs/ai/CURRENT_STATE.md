# Estado atual comprovado no repositório

**Snapshot de referência:** 10/11/2026. O release de aplicação confirmado é
`1f7d1a8333518f0b41d96d72676fd78cd759a8cb`; um commit posterior somente documental
atualiza os handoffs e o procedimento. Compare o `HEAD` Git em cada ambiente antes de
novas alterações. O checkout `/opt/orquestra` foi confirmado no SHA do release após
publicação. Git local exibia dois caminhos não rastreados:
`Kit Marca/` e `docs/conhecimento/base-atendimento-climatiza-brasil.md`. Seus conteúdos
foram preservados e não foram inspecionados nem adicionados nesta sincronização.

**Atualização posterior em 11/11/2026:** o commit `929561e327163d4a9bb11abc9a0f418f3542a462`
foi enviado a `origin/main` e a branch local `main` avançou ao mesmo SHA. O deploy dessa
revisão ainda não foi confirmado. A última revisão de aplicação confirmada na VPS
continua sendo `1f7d1a8333518f0b41d96d72676fd78cd759a8cb`; nova verificação SSH falhou
porque o agente recusou assinar com a chave carregada. Não inferir sincronização VPS.

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
| Envio humanizado em blocos | Implementado e publicado em `1f7d1a8`; envio externo segue globalmente desativado | `split_reply_conversational`, `tasks.py`, outbox existente; resposta curta fica inteira, respostas maiores podem virar até 3 blocos de 300 caracteres, intervalo de 2 s; humanização é regra global, não configuração individual | Homologação com fornecedores/clientes não feita; chamada externa iniciada não é cancelável; excesso sobre o limite seguro escala para intervenção; `OUTBOUND_ENABLED=false` nos containers publicados |
| Continuidade conversacional e visita técnica | Código publicado em `1f7d1a8`; interpretação semântica de respostas curtas está em desenvolvimento local na branch `fix/enrico-live-visit-followups`; confirmação operacional de visita permanece humana | `Conversation.context_state`, `ConversationProfile.visit_booking_enabled` (falso por padrão), `conversation/behavior.py`, `tasks.py`, `interventions.py`; sem migration | A resposta semântica do provedor real ainda não foi homologada. O modelo recebe contexto montado pelo backend, não acessa SQL diretamente. Saída incompatível falha fechada para intervenção |
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
auditoria. Na publicação de `1f7d1a8`, a revisão lida em produção era
`0010_wame_api_base_url`; não havia migration Alembic no diff e nenhuma foi aplicada.

## Testes

Existem testes unitários, integração com banco descartável condicional, testes de
contratos e UI em `tests/`. Para o commit funcional antes do merge, foram executados
154 testes unitários e 58 de integração (2 pulados pela ausência de baseline histórica).
No GitHub Actions do SHA `1f7d1a8`, os jobs `test`, `ui` e `migrations` concluíram com
`success`. Isso não homologa provedores nem o comportamento de conversas em produção.

## Git e publicação

Local, GitHub `main` e `/opt/orquestra` foram confirmados em
`1f7d1a8333518f0b41d96d72676fd78cd759a8cb` após o deploy. API, worker e scheduler
reportaram a mesma imagem `sha256:b5f29fd5617464b2efc9f92e6d73f5089bec75563c0fcef379f2f6bb4caee910`
com label desse SHA; API, banco, Redis e scheduler estavam saudáveis, o worker respondeu
ao ping, `https://app.salex.tech/health` retornou sucesso e a página principal retornou
HTTP 200. A revisão permaneceu `0010_wame_api_base_url`; nenhuma migration foi aplicada.
O helper criou backup criptografado e recibo privado; cópia externa do backup e ensaio
de restauração continuam sem confirmação. `OUTBOUND_ENABLED=false` foi observado na API
e no worker. Detalhes em `docs/handoff/2026-11-10-publicacao-enrico.md`.

## Continuidade conversacional e visitas

**IMPLEMENTADO e publicado:** o núcleo comum mantém um resumo estruturado e com prazo dentro de `Conversation.context_state`, adicional ao histórico de mensagens. Registra fatos explícitos com referência da mensagem e tempo; no primeiro uso também reconstrói o resumo a partir de até 200 mensagens recentes de conversas preexistentes, exceto quando o contexto expirou. Usa telefone numérico direto do provedor como metadado não confirmado e evita enviar seus dígitos ao modelo. As regras globais de linguagem, continuidade e envio em blocos são comuns a todos os agentes. O perfil do agente continua sendo a fonte de especialidade, produto, tom e objetivo; a qualificação de visita depende da capacidade individual `visit_booking_enabled`.

**EM DESENVOLVIMENTO LOCAL na branch `fix/enrico-live-visit-followups`:** para agentes com qualificação de visita ativa, o backend entrega ao modelo histórico recente, resumo do banco, perfil do agente e conhecimento recuperado da empresa. O modelo escreve a resposta do turno e devolve um envelope semântico allowlist para registrar confirmações contextuais e o próximo dado solicitado. O backend não interpreta consentimento por uma lista de expressões; valida a saída e somente atualiza estados permitidos quando há uma pergunta pendente. Não são gravadas respostas prontas. Saída inválida falha fechada para intervenção. Ainda não houve homologação deste contrato com Gemini ou outro provedor real.

**IMPLEMENTADO:** quando os dados necessários da visita estão completos, o backend solicita validação pelo fluxo existente de intervenção humana. Sem agenda integrada ou confirmação operacional, o status permanece `awaiting_confirmation` e o sistema não declara visita marcada. O resumo estruturado é incluído no contexto da equipe, com telefone somente depois de autorizado. Nenhuma tabela ou migration nova.

**TESTADO em 10/11/2026:** 154 testes unitários passaram; 58 testes de integração passaram no PostgreSQL descartável e 2 testes de consolidação de migrations foram pulados porque a baseline histórica não estava disponível. Os testes sintéticos cobrem conversa preexistente, igreja, escolha de data/horário, retorno por telefone autorizado, tentativa do modelo de confirmar sem agenda, recebedor terceiro, grupo de atendimento não configurado, datas alternativas e isolamento do fluxo de visitas por capacidade de agente. Sem chamadas reais a fornecedores. Consulte `docs/handoff/2026-11-10-contexto-conversacional-global.md`.

**TESTADO em 11/11/2026 no commit `929561e`:** 148 testes unitários passaram, excluindo os seis testes do módulo `test_release_guard.py`; 59 testes da suíte completa de integração passaram e 2 testes de consolidação de migrations foram pulados por falta da baseline histórica. A interpretação contextual de “Claro” foi simulada com resposta estruturada do modelo; não houve chamada a LLM ou WhatsApp. Uma execução da suíte unitária completa teve 152 aprovados e 3 falhas ambientais: checkout read-only sem `safe.directory` e dois fixtures de deploy sem `.env`.

**NÃO HOMOLOGADO:** a extração de fatos explícitos ainda é determinística; resposta semântica depende da capacidade do provedor de seguir o envelope e interpretar o histórico. Saída inválida é encaminhada para intervenção. Não há integração de agenda e não foram homologados fornecedores, grupo real nem a experiência desta branch com clientes.

## Git e publicação — atualização em 11/11/2026

O commit `929561e327163d4a9bb11abc9a0f418f3542a462` está na branch local `main` e em
`origin/main`. A VPS não foi atualizada nesta sessão. O último release conhecido na VPS
é `1f7d1a8333518f0b41d96d72676fd78cd759a8cb`, de acordo com a checagem anterior; não foi
possível verificar novamente o checkout remoto porque o agente SSH recusou assinar.
Os dois caminhos privados não rastreados foram preservados e continuam fora do commit.

## Histórico da sincronização anterior

O histórico da tentativa inicial de sincronização está preservado em
[`2026-11-10-tentativa-sincronizacao.md`](../handoff/2026-11-10-tentativa-sincronizacao.md).
Depois dela, a origem Git foi usada por HTTPS com a credencial já configurada; não foi
necessário usar SSH para GitHub. O `main` local e `origin/main` foram avançados para
`1f7d1a8333518f0b41d96d72676fd78cd759a8cb`; os dois arquivos locais não rastreados
foram preservados. Esse SHA passou os jobs `test`, `ui` e `migrations` no GitHub Actions
e foi publicado em `/opt/orquestra` com saída desativada. Não houve migration.

O deploy anterior estava em `bf2f028baf69b5b221d511c3b131075e436144d8`; a API, worker e
scheduler estão na imagem identificada acima. API e frontend público responderam; o
healthcheck da API foi positivo. O backup cifrado foi criado; cópia off-site e restore
de ensaio permanecem pendentes. Consulte o handoff de publicação para os comandos e
limitações confirmadas.
