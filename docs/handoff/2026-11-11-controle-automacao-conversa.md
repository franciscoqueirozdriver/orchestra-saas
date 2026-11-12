# Handoff — Controle de pausas da automação

Data: 11/11/2026
Estado inicial: branch `feat/automation-control-panel`, base `0330b052dc2b055fe1274d9293b7529e93b0db73`.
Objetivo: dar visibilidade, por conversa, aos bloqueios globais, da conexão, do agente, do contato e do outbox, com ações de recuperação disponíveis no mesmo painel.

## Evidência e alterações

- `backend/app/routes_conversations.py` e `backend/app/schemas.py`: `/conversations` agora expõe autor/direção da mensagem mais recente; `/conversations/{id}/state` agrega estado do envio global, conexão, agente, política do contato, conversa, webhook correlacionado, última execução do modelo e últimas tentativas do outbox. `POST /{id}/consent` registra nova autorização com evidência sob lock de tenant e invalida respostas automáticas pendentes, sem retomar a conversa.
- `frontend/app.js` e `frontend/styles.css`: a conversa ganhou o painel **Controle da automação**, com estados separados por escopo, bloqueios legíveis, direção da última mensagem e últimas tentativas. Operadores podem retomar a conversa; administradores podem alterar envio global, política da conexão, estado do agente e registrar nova autorização com evidência.
- Ações que podem liberar envios reais ou afetar vários contatos pedem confirmação. Registrar consentimento exige evidência textual; isso não apaga pausa humana nem envia mensagem. O painel avisa que opt-out só deve ser removido após nova autorização. Estados `unknown` do outbox não são reenviados.
- Para `external_takeover`, a interface explica que uma mensagem não correlacionada foi classificada como enviada pelo WhatsApp conectado; a direção/autoria da última mensagem ajuda a detectar classificação incorreta do callback.
- Não houve alterações em migrations, código funcional do fluxo de mensagens ou configuração de produção.

## Verificações

- Suíte unitária + integração em Python 3.12, com PostgreSQL pgvector descartável e baseline histórico montado: **219 passaram**. Não houve chamadas externas.
- UI sintética em Chrome headless: passou, incluindo o painel de controle, estados de exemplo e fluxo existente de takeover/retomada.
- `node --check frontend/app.js`, análise sintática Python e `git diff --check`: passaram.
- `bash -n scripts/*.sh database/init/*.sh` e `docker compose --env-file .env.example config --quiet`: passaram.
- Pré-publicação read-only na VPS: checkout limpo em `0330b052dc2b055fe1274d9293b7529e93b0db73`; API, worker e scheduler saudáveis na imagem com esse label; banco em `0010_wame_api_base_url`; envio global está `enabled=true` por override do painel e padrão de ambiente `false`. Nenhum serviço ou estado operacional foi alterado nesta conferência.

## Limites e próxima ação

- Desconexão do provedor, callback não configurado e estado `unknown` exigem investigação operacional; o painel diagnostica, mas não promete reversão automática.
- Retomar IA libera apenas a conversa e aguarda nova mensagem do cliente. Habilitar envio global/conexão/agente pode afetar outros contatos e pode liberar itens pendentes, por isso há confirmações explícitas.
- Antes de publicar: revisar diff, adicionar testes para isolamento/diagnóstico e fluxos das ações administrativas, executar a suíte em ambiente descartável e confirmar com a usuária o comportamento de retomada após opt-out e de agente desativado compartilhado por várias conexões.
- Sem commit, push, merge ou deploy.

## Estado Git final

Branch `feat/automation-control-panel`; alterações locais: `backend/app/routes_conversations.py`, `backend/app/schemas.py`, `frontend/app.js`, `frontend/styles.css`, `tests/integration/test_runtime_safety.py`, `tests/ui/conversation-panel.cjs`, este handoff e `docs/ai/HANDOFF_INDEX.md`. Sem arquivos privados copiados. Revisão atual depende do estado do worktree ao continuar.
