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
| Entrega conversacional é opt-in por agente, usa as partes duráveis existentes e tem limites rígidos de 3 blocos/300 caracteres; resposta que exceder os limites é escalada, não truncada | `backend/app/schemas.py`, `conversation/behavior.py`, `tasks.py`, `outbox.py`; implementação local em `feat/humanized-whatsapp-delivery` | Não ativar em perfis legados implicitamente; manter rate limit, revisão por parte e `unknown`; presença permanece desativada até homologação |

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
