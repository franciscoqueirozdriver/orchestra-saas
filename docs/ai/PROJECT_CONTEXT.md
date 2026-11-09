# Contexto do projeto

**Referência auditada:** `main` / `origin/main`, commit `40272d0` em 09/11/2026.
Este texto descreve o código local observado. Não certifica o estado da VPS.

## Produto e arquitetura observada

O diBBerDesk é uma aplicação web multiempresa para atendimento por WhatsApp com
agentes de IA, histórico, gestão humana, documentos de conhecimento e conexões de
provedores. “Planejado”, “testado” e “homologado externamente” são estados distintos;
consulte [estado atual](CURRENT_STATE.md) e [riscos](KNOWN_RISKS.md).

| Camada | Implementação observada | Evidência principal |
|---|---|---|
| Interface | HTML/CSS/JavaScript sem framework de build; telas e navegação em `frontend/app.js`, marca/atalhos em `frontend/index.html` e assets | `frontend/` |
| API | Python 3.12, FastAPI, SQLAlchemy, Pydantic Settings; rotas para autenticação, empresas, usuários, agentes, conexões, conversas e conhecimento | `backend/app/main.py`, `backend/app/routes_*.py`, `backend/requirements.lock` |
| Atendimento | Celery/Redis, geração LangGraph com checkpoint PostgreSQL, agrupamento de mensagens, fallback entre conexões de modelo e outbox persistente | `backend/app/tasks.py`, `backend/app/model_router.py`, `backend/app/outbox.py` |
| Dados | PostgreSQL 16 com pgvector; modelos SQLAlchemy e cadeia Alembic `0001`–`0010` | `backend/app/models.py`, `backend/migrations/versions/` |
| Busca | Extração de TXT/MD/CSV/PDF/DOCX/XLSX, chunks e embeddings de 1536 dimensões; configuração de busca pode usar conexão cadastrada | `backend/app/routes_knowledge.py`, `backend/app/embedding_config.py` |
| Modelos externos | Catálogo de presets para Gemini, Groq, Mistral, OpenRouter, OpenAI, xAI, Anthropic e endpoint OpenAI-compatible; modelos são informados manualmente | `backend/app/provider_catalog.py`; catálogo declara `live_provider_verified: false` |
| WhatsApp | Adaptadores Z-API e WAME por uma fábrica de transporte; callback comum e ação manual de criação de grupo se suportada | `backend/app/transport.py`, `backend/app/zapi_client.py`, `backend/app/wame_client.py`, `backend/app/routes_zapi.py` |
| Segurança de aplicação | JWT, hash de senha, cifra de credenciais, limite de login em Redis e validação de destino externo | `backend/app/security.py`, `routes_auth.py`, `url_safety.py`, `config.py` |
| Ingestão privada | Ferramentas locais separadas para inventário/importação; faster-whisper opcional, FFmpeg local e SQLite retomável | `scripts/private_knowledge/`, `scripts/private_knowledge/requirements.txt`, `docs/conhecimento/ingestao-local-whatsapp.md` |
| Hospedagem | Compose com API, worker, scheduler, PostgreSQL/pgvector, Redis e Caddy; aplicação Python é imagem. Frontend e Caddyfile são montados do checkout | `docker-compose.yml`, `Dockerfile`, `Caddyfile`, `docs/fluxo-local-github-vps.md` |
| Operação | Scripts de backup/restauração, bootstrap, deploy e release com verificação de SHA/checkout | `scripts/`, `docs/deploy-hostinger.md`, `docs/fluxo-local-github-vps.md` |

O caminho ponta a ponta de webhook a resposta, intervenção e recuperação está
resumido em [`MESSAGE_FLOW.md`](MESSAGE_FLOW.md); este contexto evita repetir seus
detalhes operacionais.

## Limites de leitura

- O escopo de tenant é resolvido no backend via usuário autenticado e `X-Tenant-ID`;
  administradores de plataforma podem selecionar tenant. Não há evidência nesta
  auditoria de política PostgreSQL RLS geral.
- A área de rotas ainda se chama `routes_zapi.py` e endpoints têm prefixo `/api/zapi`,
  embora transportes WAME estejam presentes. O nome interno não prova exclusividade
  do conector.
- `scripts/private_knowledge/` é um pipeline local isolado; suas migrations SQLite
  não pertencem à cadeia Alembic de produção.
- O diretório local `docs/Conversas/` e demais materiais brutos são privados e foram
  excluídos desta auditoria. Verifique `.gitignore` e `.dockerignore` antes de mudar
  contextos. Não copiar conteúdo privado para este documento.
- A descrição de marca, integrações e publicação deve ser revalidada contra código,
  CI e a instância alvo em cada release.
