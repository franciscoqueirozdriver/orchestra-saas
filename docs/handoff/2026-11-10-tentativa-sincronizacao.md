# Handoff — tentativa de sincronização de continuidade e envio humanizado

**Data:** 10/11/2026
**Commit funcional:** `d17d85a07c760275d59efe604b90eef03a46067b`
**Escopo autorizado:** commit, publicação em `main` e sincronização local/GitHub/VPS.

## Resultado confirmado

- O commit funcional foi criado localmente na branch `feat/enrico-context-booking`.
- O checkout principal foi avançado para a branch local `main` no mesmo commit; os dois caminhos locais não rastreados (`Kit Marca/` e `docs/conhecimento/base-atendimento-climatiza-brasil.md`) foram preservados e não incluídos.
- A alteração não contém arquivos em `backend/migrations/`; não há migration nova para aplicar.
- Unitários: 154 passaram. Integração em PostgreSQL 16/pgvector descartável: 58 passaram e 2 foram pulados por ausência da baseline histórica. Sintaxe JavaScript passou. O teste interativo de Chrome não foi executado porque `playwright-core` não está instalado.

## Sincronização externa

- O `origin/main` local em cache, antes da tentativa, estava em `40272d03188dc14accdb8c63b65b8763435de7de`.
- `git push origin HEAD:main` não publicou: conexão SSH a `github.com:22` expirou. SSH-over-443 também expirou.
- A consulta direta do ref remoto expirou; portanto, o SHA atual do GitHub não foi confirmado. `gh auth status` informou que o token salvo está inválido; nenhum token foi exposto ou alterado.
- O SSH à VPS expirou. O HEAD, estado Git, imagens e revisão Alembic em `/opt/orquestra` não foram lidos nem alterados.
- Nenhum deploy, backup de produção ou migration foi executado. Não se declara GitHub/VPS sincronizados.

## Retomada

1. Restaurar conectividade SSH à VPS e acesso autenticado válido ao GitHub.
2. Fazer fetch/consulta direta de `origin/main`; confirmar que o commit remoto não avançou de forma incompatível antes de tentar o push fast-forward.
3. Confirmar o SHA remoto em `main` e o checkout local. Preservar os dois caminhos locais não rastreados.
4. Verificar GitHub Actions para o SHA final.
5. Na VPS, repetir o preflight documentado em `docs/fluxo-local-github-vps.md` e `scripts/release.py`: limpeza do checkout, commit/imagens atuais e revisão Alembic. O estado da VPS é desconhecido até essa verificação.
6. Não aplicar migrations: o commit funcional não as contém. Fazer deploy somente depois do preflight e das verificações/autorizações previstas no procedimento oficial.
