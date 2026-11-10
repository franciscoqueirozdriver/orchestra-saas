# Decisões técnicas consolidadas

Este registro contém decisões encontradas no código e em documentação aprovada. Se
uma mudança recente de produto ou segurança for ambígua, preserve o comportamento e
peça decisão; não inferir autorização a partir de um plano.

| Decisão vigente | Evidência | Aplicação prática |
|---|---|---|
| Desenvolver localmente; GitHub é compartilhamento; VPS só recebe publicação revisada | `AGENTS.md`, `docs/fluxo-local-github-vps.md` | Não editar VPS para desenvolver nem sincronizar alterações dela automaticamente |
| Publicar SHA completo e exigir checkout remoto limpo | `scripts/release.py`, `docs/fluxo-local-github-vps.md` | Parar e preservar se houver alteração/arquivo novo; nunca `reset --hard` ou `git clean` |
| Separação por tenant é validada no servidor, não confiada à UI | `backend/app/dependencies.py`, rotas/modelos | Mudanças em APIs, filas e consultas devem revalidar tenant e usuário |
| Segredos de provedores são cifrados; callback usa segredo próprio | `backend/app/security.py`, `routes_zapi.py`, `models.py` | Não registrar segredo, URL privada de callback, payload sensível ou `.env` |
| Credenciais de modelo e configuração da busca são conceitos relacionados, mas distintos | `routes_llm.py`, `embedding_config.py`, `routes_knowledge.py`; `docs/conhecimento/armazenamento-e-busca.md` | Não duplicar chave se uma conexão cadastrada foi selecionada; busca ainda requer modelo/configuração compatível |
| Embeddings têm 1536 dimensões nesta revisão | `config.py`, schema/migration `0006`, testes/configuração | Mudança exige análise de schema, reindexação e compatibilidade; não apenas campo de UI |
| Efeitos externos passam por controle de saída, outbox e reconciliação; não prometer exactly-once | `outbound_control.py`, `outbox.py`, `tasks.py`, `docs/consolidacao/2026-11-05-revisao-pr1.md` | Falhas ambíguas de envio precisam de revisão; não repetir às cegas |
| Histórico de mensagens não é conhecimento aprovado automaticamente | `Message`, `KnowledgeDocument`, docs `conhecimento/` | Manter proveniência e finalidade; não indexar ou transformar conversa em preço/regra sem aprovação |
| A intervenção humana requer grupo/participantes configurados e validação pela organização; criação por API é manual | `routes_zapi.py`, `interventions.py`, `docs/intervencao-humana-grupo.md` | Não criar grupo nem disparar mensagem real automaticamente; provedores podem não confirmar entrega |
| Migrations Alembic são a cadeia do banco da aplicação; SQL sob `docs/intencoes/` é proposta | `backend/migrations/versions/`, `AGENTS.md`, docs de consolidação | Não importar migrations propostas para Alembic nem editar revisão histórica sem análise específica |
| API/worker/scheduler usam imagem; frontend/Caddy são mounts no Compose | `docker-compose.yml`, `Dockerfile` | Um arquivo Python no checkout da VPS não prova que está rodando; conferir SHA da imagem e binds |
| Saída de mensagens inicia suspensa no helper de release | `scripts/release.py`, `docs/consolidacao/2026-11-05-revisao-pr1.md` | Não habilitar envio como efeito incidental de deploy; piloto precisa de autorização operacional própria |
| Entrega conversacional em blocos é política global do canal, usa as partes duráveis existentes e tem limites rígidos de 3 blocos/300 caracteres; resposta que exceder os limites é escalada, não truncada | `backend/app/conversation/behavior.py`, `tasks.py`, `outbox.py`; implementação local em `feat/enrico-context-booking` | Não depender do perfil de cada agente para dividir mensagens; manter rate limit, revisão por parte e `unknown`; presença permanece desativada; campos antigos do perfil permanecem aceitos por compatibilidade, mas não controlam a política global |
| Fluxos comerciais específicos, como qualificar e encaminhar visita técnica, dependem de capacidade habilitada no perfil do agente; não são consequência da política global de linguagem | `ConversationProfile.visit_booking_enabled`, `tasks.py`, formulário “Tom e conversa” | Humanização e continuidade são compartilhadas; habilitar visita técnica somente para agentes que realmente oferecem e encaminham esse serviço |
| Continuidade, redução de perguntas repetidas e linguagem natural são políticas globais do núcleo; identidade, especialidade, catálogo, tom e objetivo pertencem ao perfil de cada agente | `backend/app/conversation/behavior.py`, `tasks.py`, `Conversation.context_state`; atualização de perfil continua em `routes_agents.py` e `ConversationProfile` | Reutilizar memória factual e regras de menor atrito para todos os agentes; não copiar contexto comercial específico da Climatiza Brasil para instruções globais |
| Preferência de visita não equivale a agendamento confirmado; sem integração operacional, encaminhar para confirmação humana e dizer que está pendente | `backend/app/tasks.py` (`_request_visit_confirmation`), `interventions.py`, estado em `Conversation.context_state` | Não afirmar visita reservada sem agenda/aceite verificável. Campo `confirmed` não é definido por texto do modelo |
| Confirmar retorno usa canal WhatsApp atual e exige consentimento; pessoa que recebe a equipe é distinta do decisor | `backend/app/zapi_payload.py` (`direct_contact_phone`), `conversation/behavior.py`, `interventions.py` | Rejeitar identificadores de grupo/LID, não inferir nome do perfil e pedir o nome do recebedor somente se for outra pessoa |

## Decisões antigas ou documentos de proposta

- Documentos de outubro e o README inicial descrevem Z-API como único provedor. Isso
  foi superado no código posterior por suporte WAME (`transport.py`, `wame_client.py`,
  migrations `0009`/`0010` e commits `68fc944` a `895393a`).
- Propostas de trazer funcionalidades de A Mesa em `docs/intencoes/` continuam
  propostas ou evidências de referência, salvo partes que tenham sido implementadas
  e verificadas separadamente. SQL proposto não é schema em uso.
- A estratégia original de usar conexões de conversa e embeddings pode evoluir; o
  comportamento atual deve ser lido em `routes_llm.py` e `embedding_config.py`, não
  inferido de capturas de tela ou texto de onboarding antigo.
