# Desenvolvimento local → GitHub → publicação na VPS

Atualizado em 06/11/2026. A pasta local é o ambiente de desenvolvimento;
GitHub `main` é a fonte compartilhada; `/opt/orquestra` é o checkout de publicação.
Não editar código diretamente na VPS nem sincronizar mudanças dela de volta.

## Estado publicado

O release da aplicação usa o commit completo
`edccf4617181a4b58ff81bd3c809887e10355712`. API, worker e scheduler usam a mesma
imagem etiquetada com esse SHA. Este handoff e as correções documentais serão
publicados em commit posterior somente de documentação; após sincronizar o checkout
da VPS, o `HEAD` do repositório poderá estar nesse commit posterior, enquanto as
imagens continuarão corretamente identificadas com o SHA do release da aplicação.
O checkout remoto deve permanecer limpo. A revisão Alembic é
`0007_search_connection`; não houve alteração do schema da aplicação.

O deploy foi autorizado, conferido e executado em 06/11/2026. O recibo privado é
`~/orchestra-releases/20261106T024352Z/receipt.json`. O backup operacional
criptografado foi criado sob `~/orchestra-preservacao/.../operational-backups`;
confirme a cópia externa dos arquivos e checksums e preserve a passphrase em local
separado. O recibo indica `started_external_checks_pending`, estado do helper que
exige validação pós-deploy, não falha de build. A checagem HTTPS de saúde foi feita;
ver o [handoff detalhado](handoff/2026-11-06-publicacao-e-ingestao.md).

O helper de release forçou `OUTBOUND_ENABLED=false` nos contêineres novos. Respostas
automáticas de saída ficam suspensas até um piloto autorizado e uma configuração
explícita. Não altere essa variável como parte de uma atualização comum.

## Rotina de desenvolvimento

```bash
cd "$HOME/Documentos/orchestra-saas"
git fetch origin
git switch -c feature/nome-da-alteracao origin/main
```

Use dados sintéticos, revise as alterações e segredos, e adicione arquivos por
caminho explícito. Não inclua `.env`, `docs/Conversas/`, transcrições, exports,
backups, uploads ou dados de clientes. A pasta
O rascunho local da base comercial da empresa permanece fora do Git até revisão de
privacidade, atualidade e decisão de publicação.

Validação local recomendada com Python 3.12 e o ambiente de desenvolvimento:

```bash
python -m pytest -q
python docs/intencoes/atendimento-natural-a-mesa/validacao/verificar_prototipo.py
node --check frontend/app.js
bash -n scripts/*.sh database/init/*.sh
docker compose --env-file .env.example config --quiet
git diff --check
```

A suíte de integração SQL exige banco descartável `orchestra_consolidation_test`,
em `127.0.0.1` ou no serviço de CI. Informe `TEST_DATABASE_URL` e
`ORCHESTRA_BASELINE_ROOT` conforme o workflow. Ela recria apenas o schema do banco de
teste. Nunca use DSN de produção. O CI executa os testes, integração de migrations,
validação de shell/Compose e build da imagem.

Publique a branch e abra PR para `main`. Merge em `main` e deploy são decisões
separadas; precisam de autorização explícita. Registre e valide o SHA completo do
commit final de `main`; não presuma que o SHA da branch é o SHA publicado.

## Publicar uma próxima versão

1. Confira GitHub Actions aprovado para o SHA que se pretende publicar.
2. Na VPS, confira `git status --short --untracked-files=all`, `HEAD`, imagens em
   execução e revisão Alembic. Se houver qualquer alteração local ou arquivo novo,
   pare e preserve/revise; não use `reset --hard`, `git clean` ou `rsync` reverso.
3. Execute `scripts/release.py SHA_COMPLETO --checkout-root /opt/orquestra` sem
   `--apply`. O modo de conferência atualiza referências e lê Git, imagens e banco;
   não reinicia serviços nem aplica migrations.
4. Revise commit anterior/destino, schema, cadeia de migrations, backup, compatibilidade,
   impacto de saída e janela de manutenção. Leia também
   `docs/security-and-operations.md`.
5. Com a autorização correspondente, execute `--apply` com a revisão Alembic
   observada imediatamente antes. Para mudanças de schema, use `--allow-schema-change`
   somente após revisar migrations, backup, compatibilidade e reversão.
6. Confira recibo, HTTPS, API, worker/scheduler, sites que compartilham Caddy e
   fluxos com destinatários de teste autorizados. Não envie mensagens reais sem
   autorização específica.

O helper exige checkout limpo, SHA completo alcançável de `origin/main` e destino
descendente do HEAD remoto. No `--apply`, cria recibo privado, exige backup
operacional, fixa tags das imagens anteriores, faz checkout detached e executa o
deploy. Deploy pode aplicar Alembic e reiniciar API, worker, scheduler e proxy. O
helper desliga saída por padrão e não faz rollback de banco automaticamente.

## Reversão

Use o recibo daquela publicação, imagens fixadas e backup correspondente. Uma
reversão de código não reverte o banco por si só. Não apague volumes/imagens nem
execute downgrade sem revisar dados posteriores, migrations e compatibilidade.
Restauração de banco exige janela, consistência e autorização; pode perder gravações
posteriores. Reversão da aplicação deve incluir frontend/Caddy se forem alterados.

## Privacidade e histórico de conversas

`docs/Conversas/`, transcrições, SQLite de staging, JSONL de transferência e corpus
derivado são privados e ficam fora do Git e das imagens Docker. O exportador local
gera o pacote de transferência; o importador da aplicação grava mensagens como
histórico tenant-scoped, com autor, ordem, data original, hash e idempotência.
Depois de publicada a versão com migration 0008 e concluída a importação, abra
**Conversas**, escolha a conversa e consulte a linha do tempo. Mensagens históricas
de cliente/equipe também podem compor o contexto recente quando aquele contato voltar.

O commit `db66dde71dd4c85304632e65a3d9c8849599670f` foi validado por CI, mas está
na PR #7 até integração. O pacote privado exportado tem 7.934 mensagens em 58
conversas, após deduplicar cópias idênticas pelo hash. Ainda não o transporte nem
importe até a migration estar publicada. Não indexe automaticamente o corpus na
base de conhecimento: o histórico é conversa e contexto, não regra comercial
aprovada. Veja [`docs/historico-whatsapp.md`](historico-whatsapp.md),
[`docs/conhecimento/preparacao-privada.md`](conhecimento/preparacao-privada.md) e o
[handoff detalhado](handoff/2026-11-06-publicacao-e-ingestao.md).
