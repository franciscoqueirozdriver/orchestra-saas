# diBBerDesk

Plataforma web multiempresa para atendimento por WhatsApp, com agentes de IA,
histórico de conversas, intervenção humana, conexões de provedores e busca em
documentos. O estado de implementação deve ser lido em
[`docs/ai/CURRENT_STATE.md`](docs/ai/CURRENT_STATE.md); este README é uma entrada
curta, não um relatório de homologação.

## Arquitetura

- **Interface:** HTML, CSS e JavaScript em `frontend/`.
- **API e processamento:** Python 3.12, FastAPI, SQLAlchemy, Celery e LangGraph em
  `backend/`.
- **Dados e fila:** PostgreSQL 16 com pgvector e Redis.
- **WhatsApp:** adaptadores Z-API e WAME. Código presente não significa conta,
  callback, envio ou entrega homologados.
- **Execução:** Docker Compose com API, worker, scheduler, banco, Redis e Caddy.
  API/worker/scheduler executam imagem; frontend e Caddyfile são mounts.

## Começar a trabalhar

Antes de qualquer alteração, leia [`AGENTS.md`](AGENTS.md) e o
[`protocolo de continuidade`](docs/ai/CONTINUITY_PROTOCOL.md). O contexto canônico
fica em [`docs/ai/`](docs/ai/HANDOFF_INDEX.md). Handoffs são registros datados:
consulte-os, mas confronte cada afirmação com código e commit atuais.

Dependências Python estão fixadas em `backend/requirements.lock`; os testes e os
requisitos de execução estão em [`tests/README.md`](tests/README.md). Use ambiente
local descartável para testes de banco. Não use credenciais ou conversas reais em
testes e não execute testes contra produção.

## Desenvolvimento e publicação

Desenvolva localmente, publique mudanças por branch/PR no GitHub e use a VPS somente
como destino de publicação. Merge e deploy são operações separadas que exigem
autorização específica. Siga [`docs/fluxo-local-github-vps.md`](docs/fluxo-local-github-vps.md)
e o procedimento `scripts/release.py`. Nunca sincronize alterações da VPS de volta
automaticamente.

## Privacidade

Não adicione `.env`, credenciais, backups, dumps, uploads, dados de usuários ou
material bruto de `docs/Conversas/` ao Git ou a imagens Docker. Conversas históricas
são contexto de atendimento; não viram fatos comerciais aprovados nem conhecimento
indexado automaticamente. Veja o [processo de preparação privada](docs/conhecimento/preparacao-privada.md),
o [índice de continuidade](docs/ai/HANDOFF_INDEX.md) e as regras em `AGENTS.md`.
