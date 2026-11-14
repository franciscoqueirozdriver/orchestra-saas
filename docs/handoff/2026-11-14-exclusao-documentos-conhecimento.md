# Handoff — exclusão de documentos da base de conhecimento

Data: 2026-11-14
Estado inicial: branch `feat/knowledge-document-delete`, baseada em `6972bc8342282fd52f57b2273c8e938c3a76335b` (`origin/main`). Checkout principal estava em outra branch com alterações pendentes e arquivos privados/não rastreados; foi preservado sem modificações.

## Objetivo e fontes

Adicionar à tela Conhecimento uma ação explícita para excluir documento, protegida por confirmação, e sincronizar local/GitHub/VPS conforme autorização do usuário. Foram consultados `AGENTS.md`, `docs/ai/CONTINUITY_PROTOCOL.md`, `CURRENT_STATE.md`, `HANDOFF_INDEX.md`, `docs/fluxo-local-github-vps.md`, `scripts/release.py`, a rota de conhecimento e testes relacionados.

## Implementação

- `frontend/app.js`: a lista mostra **Excluir** para `platform_admin` e `tenant_admin`; a confirmação avisa que o documento e todos os trechos serão removidos da busca e que a operação é irreversível. Cancelar não chama a API. Confirmar chama `DELETE /api/knowledge/documents/{id}`, atualiza a lista e mostra resultado.
- `tests/ui/knowledge-storage.cjs`: cobertura do diálogo, cancelamento sem requisição e exclusão confirmada.
- `tests/integration/test_runtime_safety.py`: cobertura de remoção de documento e chunks, preservação de outro tenant e resposta 404 ao tentar excluir documento alheio.
- A rota já existia em `backend/app/routes_knowledge.py`; exige papel administrativo, filtra pelo tenant e apaga chunks e documento na mesma sessão. Não foi necessária migration ou alteração de backend.

## Verificações

- `node --check frontend/app.js`: passou.
- `node --check tests/ui/knowledge-storage.cjs`: passou.
- `git diff --check`: passou.
- Teste UI Chrome headless: passou; confirmou cancelamento sem exclusão e confirmação com exatamente uma requisição DELETE.
- `tests/integration/test_runtime_safety.py -k document_delete`, em container local com PostgreSQL descartável: **1 passed, 71 deselected**.
- Nenhum teste ou envio foi executado contra produção ou provedores externos.

## Publicação e limites

A publicação ainda não foi confirmada. A consulta HTTPS ao GitHub retornou `main` em `6972bc8342282fd52f57b2273c8e938c3a76335b`. A consulta inicial à VPS falhou porque o agente SSH recusou a assinatura da chave; não foi possível confirmar estado limpo, versão publicada, revisão Alembic, imagens ou saúde dos serviços. A conta local de `gh` também reportou token inválido. Não declarar esta alteração sincronizada nem publicada até que a branch seja integrada e o procedimento de release confirme o destino. A tentativa de rede/GitHub não alterou os arquivos do checkout principal.

O documento `docs/conhecimento/base-conhecimento-agentes.md`, criado no checkout principal durante a sessão, e todas as alterações pendentes desse checkout foram preservados e não fazem parte desta branch.

## Próxima ação

Recuperar acesso autorizado de leitura à VPS e o mecanismo HTTPS de GitHub/PR; confirmar checkout remoto limpo e versão atual; concluir push/PR/CI/merge; publicar o SHA completo via `scripts/release.py`; verificar API, painel e serviços sem enviar mensagens; então registrar SHA e estado finais neste handoff.

Estado Git ao redigir: três arquivos de implementação/testes modificados e este handoff/índice adicionados; sem commit, push, merge ou deploy. O estado deve ser atualizado antes do encerramento.
