# Handoff — auditoria de contexto e continuidade

**Data:** 09/11/2026

**Objetivo:** investigar o checkout local e criar orientação de continuidade entre modelos, sem alterar código funcional ou estado de produção.

## Estado inicial

- Branch `main`, `HEAD` e ref local `origin/main` em `40272d0` (`Evita deadlock do checkpointer ao gerar respostas.`).
- `git status` mostrava `Kit Marca/` e `docs/conhecimento/base-atendimento-climatiza-brasil.md` não rastreados. Preservados, não adicionados e não inspecionados.
- Repositório GitHub remoto e VPS não foram consultados nesta sessão; a referência local `origin/main` não prova alinhamento remoto atual.

## Fontes examinadas

`AGENTS.md` (único arquivo de instrução de agente encontrado; sem regra Cursor/CLAUDE/Gemini no checkout), `README.md`, estrutura de `backend/`, `frontend/`, `scripts/`, `tests/`,
`docker-compose.yml`, `Dockerfile`, `.gitignore`, `.dockerignore`, rotas/modelos,
configuração, migrations `0001`–`0010`, histórico Git visível, `docs/handoff/`,
`docs/consolidacao/`, documentação de deployment, provedores, conhecimento e intervenção,
documentos de intenção A Mesa e arquivos TODO. O acervo bruto em `docs/Conversas/` foi
excluído da leitura.

## Conclusões com evidência local

- O sistema contém FastAPI/Python, frontend HTML/CSS/JS, PostgreSQL/pgvector, Redis/Celery,
  LangGraph, Caddy e Compose. Z-API e WAME aparecem no código atual; o README e TODO
  mantêm trechos antigos que afirmam exclusividade Z-API.
- A cadeia Alembic local chega a `0010_wame_api_base_url`, e inclui histórico,
  intervenção humana e URL base WAME. Nenhum banco foi consultado.
- O handoff de 06/11 descreve implantação e estado válidos naquela data. Commits
  posteriores visíveis em `main` incluem grupos, WAME, apresentação da API oficial e
  correção de setup de checkpointer; não se confirmou o que foi publicado depois.
- Existem testes para rotas, contratos, scheduler, migrações e UI. Nenhum foi executado
  nesta auditoria. Resultados de documentos antigos se aplicam aos SHAs datados neles.
- `docs/Conversas/` está excluída de Git e Docker segundo as regras observadas; não se
  abriu o material privado. O conteúdo não foi copiado para documentos novos.

## Arquivos de continuidade

Criados em `docs/ai/`: `PROJECT_CONTEXT.md`, `CURRENT_STATE.md`, `DECISIONS.md`,
`KNOWN_RISKS.md`, `HANDOFF_INDEX.md` e `CONTINUITY_PROTOCOL.md`. `AGENTS.md` recebeu
links curtos de inicialização e regra para acrescentar novos handoffs sem substituir
os históricos.

## Divergências/limitações

- README e dois arquivos TODO não refletem WAME, grupo via API e migrations posteriores.
- `docs/fluxo-local-github-vps.md` e o handoff de 06/11 são snapshots. Estado atual da
  VPS, imagens, banco, serviços, CI remoto e status remoto de GitHub permanecem sem
  confirmação.
- Propostas de `docs/intencoes/` não são prova de implementação. SQL proposto não foi
  executado nesta auditoria.

## Testes e validação

Nenhum teste de aplicação, build, migration, CI, VPS ou provedor foi executado. Foi
feita inspeção read-only do Git/arquivos e verificação manual dos caminhos citados e
dos limites de privacidade. Nenhuma migration, base, variável de ambiente ou serviço
foi alterado.

## Próxima ação

Revisar os documentos canônicos e harmonizar README/TODO com eles em uma tarefa
documental separada, após confirmar quais pendências de produto permanecem vigentes.
Em uma sessão que envolva publicação, consultar remoto/CI/VPS apenas dentro do escopo
autorizado e registrar a revisão efetiva.

## Estado Git final

Este handoff e documentos canônicos são alterações locais ainda não commitadas. Não
houve `git add`, commit, push, merge ou deploy. Materiais locais não rastreados
continuam preservados.
