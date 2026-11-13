# Estado atual comprovado no repositório

**Sessão da plataforma — publicada em 13/11/2026:** o access token JWT é
curto (30 min padrão, configurável por `ACCESS_TOKEN_MINUTES`). O frontend agora
renova por `/api/auth/me` quando a página está visível e houve atividade recente,
e tenta renovar/repetir uma única vez uma chamada que recebe 401. `/auth/me` exige
token ainda válido; após expiração completa, inatividade prolongada ou mudança da
chave JWT, um novo login continua necessário. Ver `frontend/app.js`,
`backend/app/routes_auth.py` e o handoff `2026-11-13-teste-conexao-modelo.md`.
O código foi publicado no SHA `33c92680c5df22978b0f33ba34a15060b3ac0493`; o código
servido e o health HTTPS foram conferidos. A renovação foi testada com API sintética,
mas não foi possível confirmar uma sessão real de usuário sem credenciais de login.

**Nota de desenvolvimento local — 12/11/2026:** a revisão-base local desta etapa é
`465d6b3e2185d1714bdbbde59383bda94c0b4b40`. A branch isolada
`feat/semantic-llm-fallback` implementa validação do contrato de saída estruturada de
visita antes de marcar uma tentativa LLM como sucedida, tenta o próximo modelo
configurado com o mesmo snapshot e informa o estágio `response_validation` no painel.
Quando nenhuma conexão produz envelope válido, a automação falha fechada e abre a
intervenção existente com motivo específico. Sem migration. A suíte local completa
passou: **223 testes**, no container Python 3.12 com PostgreSQL descartável e
`MEDIA_DIR` temporário. Nenhum provedor real foi chamado. Esta branch não foi enviada,
mesclada nem publicada; não atualiza o estado da VPS descrito nos snapshots históricos
abaixo.

O caminho de evolução inspirado pela DOLA permanece planejado: (1) validação e
observabilidade de respostas estruturadas; (2) diálogo com estado explícito e avaliações
offline; (3) ferramentas operacionais registradas em allowlist, isoladas por tenant e
com confirmação conforme o risco; (4) memória longitudinal aprovada, com proveniência e
expiração; (5) aprendizado supervisionado de correções, sem incorporar conversas brutas
automaticamente. Não há multiagente, CRM/agenda operacional, nem aprendizado online
confirmado nesta revisão.

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

**Atualização em 11/11/2026:** o commit `34168c0` corrige a preservação da resposta
contextual do modelo quando o alerta da equipe sobre uma visita é enviado e reduz um
falso positivo da proteção contra promessas de agendamento. O commit foi enviado para
`origin/main`. A VPS continua sem sincronização confirmada; o estado externo acima é a
última evidência disponível. Respostas do modelo e alerta foram simulados nos testes,
sem chamadas reais a LLM ou WhatsApp.

**Publicação em 11/11/2026:** os commits de implementação `929561e` e `34168c0` foram
publicados; o checkout e as imagens foram sincronizados novamente após o handoff
documentar o release. Em cada execução, API, worker e scheduler usaram a mesma imagem,
healthchecks passaram, o worker respondeu ao ping, `/health` retornou `{"ok":true}` e
o painel respondeu HTTP 200. O banco permaneceu em `0010_wame_api_base_url`, sem
migration. `OUTBOUND_ENABLED=false` foi conferido em API, worker e scheduler. O helper
criou backups criptografados; cópia off-site e ensaio de restauração não foram
confirmados. Nenhuma mensagem WhatsApp foi enviada. Para o SHA atual, compare o
`HEAD` local, `origin/main`, `/opt/orquestra` e o label de revisão das imagens; os
relatórios abaixo guardam os SHAs verificados em cada etapa.

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
| Modelos de conversa, conexões e fallback | Implementado no código | `routes_llm.py`, `routes_agents.py`, `model_router.py`, `llm_client.py`, catálogo `provider_catalog.py` | O painel/banco do tenant controla a principal e a ordem `fallback_config_ids`; catálogo não escolhe modelo. Salvar ou testar conexão faz chamada curta sem persistir resultado nem alterar cooldown/default. Pode consumir quota e não homologa qualidade; não há seed/migration de cadeia por empresa |
| Armazenar documentos e indexar sob demanda | Implementado no código | `routes_knowledge.py`, `embedding_config.py`, `models.py` | Upload não indexa automaticamente; embeddings exigem configuração compatível e não foram homologados aqui |
| Histórico importado e contexto por conversa | Implementado no código | migrations `0008`, models `HistoricalImportBatch`, `ConversationContactAlias`, `Message`; `routes_conversations.py`, `tasks.py`, `history_import.py` | Não implica aprendizado automático nem conhecimento factual aprovado |
| Pipeline privado de conversas | Implementado como ferramentas locais | `scripts/private_knowledge/`, `docs/conhecimento/ingestao-local-whatsapp.md` | Não é parte do serviço da aplicação; material bruto não foi examinado nesta auditoria |
| Grupo de atendimento | Implementado no código; homologação pendente | `interventions.py`, `routes_zapi.py`, migration `0009`, `docs/intervencao-humana-grupo.md` | Envio de teste é externo e real; estado `validated` é confirmação organizacional, não confirmação de leitura fornecida pela API |
| Conversas importadas como base de busca | Não automático; fluxos separados | histórico em `messages`; conhecimento indexado em `knowledge_documents/chunks` | Não assumir que histórico foi indexado ou que conversa histórica virou regra |
| Envio humanizado em blocos | Implementado e publicado em `1f7d1a8`; envio externo segue globalmente desativado | `split_reply_conversational`, `tasks.py`, outbox existente; resposta curta fica inteira, respostas maiores podem virar até 3 blocos de 300 caracteres, intervalo de 2 s; humanização é regra global, não configuração individual | Homologação com fornecedores/clientes não feita; chamada externa iniciada não é cancelável; excesso sobre o limite seguro escala para intervenção; `OUTBOUND_ENABLED=false` nos containers publicados |
| Continuidade conversacional e visita técnica | Interpretação contextual implementada e publicada em `main`; confirmação operacional de visita permanece humana | `Conversation.context_state`, `ConversationProfile.visit_booking_enabled` (falso por padrão), `conversation/behavior.py`, `tasks.py`, `interventions.py`; sem migration | Provedor real ainda não foi homologado. O modelo recebe contexto montado pelo backend, não acessa SQL diretamente. Saída incompatível falha fechada para intervenção. Envio automático permaneceu desativado no release |
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

**IMPLEMENTADO no código local e em `origin/main` (`34168c0`):** para agentes com qualificação de visita ativa, o backend entrega ao modelo histórico recente, estado comercial do banco, perfil do agente e conhecimento recuperado da empresa. O modelo escreve a resposta do turno e devolve um envelope semântico allowlist para registrar confirmações contextuais e o próximo dado solicitado. O backend não interpreta consentimento por uma lista de expressões; valida a saída e somente atualiza estados permitidos quando há uma pergunta pendente. Não são gravadas respostas prontas. Saída inválida falha fechada para intervenção. Ainda não houve homologação deste contrato com Gemini ou outro provedor real, nem sincronização da VPS.

**IMPLEMENTADO:** quando os dados necessários da visita estão completos, o backend solicita validação pelo fluxo existente de intervenção humana. Sem agenda integrada ou confirmação operacional, o status permanece `awaiting_confirmation` e o sistema não declara visita marcada. O resumo estruturado é incluído no contexto da equipe, com telefone somente depois de autorizado. Nenhuma tabela ou migration nova.

**TESTADO em 10/11/2026:** 154 testes unitários passaram; 58 testes de integração passaram no PostgreSQL descartável e 2 testes de consolidação de migrations foram pulados porque a baseline histórica não estava disponível. Os testes sintéticos cobrem conversa preexistente, igreja, escolha de data/horário, retorno por telefone autorizado, tentativa do modelo de confirmar sem agenda, recebedor terceiro, grupo de atendimento não configurado, datas alternativas e isolamento do fluxo de visitas por capacidade de agente. Sem chamadas reais a fornecedores. Consulte `docs/handoff/2026-11-10-contexto-conversacional-global.md`.

**TESTADO em 11/11/2026 no código do commit `34168c0`:** 148 testes unitários passaram, excluindo os seis testes do módulo `test_release_guard.py`; 59 testes da suíte completa de integração passaram e 2 testes de consolidação de migrations foram pulados por falta da baseline histórica. A integração agora verifica que a resposta contextual simulada é persistida e despachada pelo outbox mesmo depois de a conversa ser pausada para a equipe. Um falso positivo que confundia “encaminhar à equipe para confirmar disponibilidade” com promessa de visita foi corrigido; afirmações como “nossa equipe fará a visita amanhã” continuam bloqueadas. Não houve chamada a LLM ou WhatsApp.

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
