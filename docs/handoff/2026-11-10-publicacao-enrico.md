# Handoff — sincronização e publicação das melhorias conversacionais

**Data operacional:** 10/11/2026 (America/Sao_Paulo; recibo UTC em 11/11)
**Branch:** `main`
**Release de aplicação:** `1f7d1a8333518f0b41d96d72676fd78cd759a8cb`

## Objetivo e resultado

Sincronizar a implementação de continuidade conversacional global, qualificação para
visitas e envio humanizado entre checkout local, GitHub `main` e VPS. A sincronização
foi concluída sem push forçado, sem migration e com envios de saída desativados.

## Estado inicial confirmado

- O checkout local estava em `faadddeb0bb89e112ba572ad17a88b08a43af236`, com dois
  caminhos não rastreados preservados e excluídos deste trabalho: `Kit Marca/` e
  `docs/conhecimento/base-atendimento-climatiza-brasil.md`.
- O checkout de produção estava limpo, detached em
  `bf2f028baf69b5b221d511c3b131075e436144d8`.
- GitHub `main` avançara até `bf2f028`. O push inicial foi rejeitado como
  `fetch first`. A inspeção confirmou que o commit remoto era um merge da PR #10 cuja
  árvore era idêntica ao ancestral local `46bd99c`.
- O GitHub foi acessado por HTTPS usando a credencial previamente configurada. A chave
  SSH carregada pelo usuário é para a VPS e não foi usada para autenticar no GitHub.

## Integração e publicação

- `origin` local permaneceu em HTTPS. O merge remoto foi integrado localmente e o
  `main` foi publicado por fast-forward no GitHub, sem `--force`.
- O SHA de release `1f7d1a8333518f0b41d96d72676fd78cd759a8cb` passou os três jobs do
  GitHub Actions (`test`, `ui`, `migrations`), todos com conclusão `success`.
- A mudança não contém arquivos em `backend/migrations/`. O preflight da VPS leu a
  revisão `0010_wame_api_base_url` e confirmou `Alteração de migrations: False`.
- O preflight de `scripts/release.py` confirmou checkout limpo, imagem/serviços atuais
  e destino alcançável de `origin/main`.
- O release substituiu a versão anterior `bf2f028...` por `1f7d1a8...`. API, worker e
  scheduler passaram a usar a imagem
  `sha256:b5f29fd5617464b2efc9f92e6d73f5089bec75563c0fcef379f2f6bb4caee910`, com label
  de revisão `1f7d1a8...`. O proxy web foi recriado pelo helper.
- O helper criou recibo privado com estado `started_external_checks_pending` e backup
  operacional criptografado com checksum. Os artefatos foram encontrados no diretório
  de preservação da VPS; a cópia externa e um ensaio de restauração não foram
  confirmados.
- `OUTBOUND_ENABLED=false` foi observado na API e no worker. Nenhuma mensagem real foi
  enviada. A habilitação de envio ou de capacidade de visita de qualquer agente exige
  avaliação e autorização operacional separadas.

## Verificações após o release

- `/opt/orquestra` estava em `1f7d1a8...` e limpo.
- API, banco, Redis e scheduler reportaram estado saudável; worker estava em execução e
  respondeu ao `celery inspect ping` (`1 node online`).
- `https://app.salex.tech/health` respondeu `{"ok":true,"service":"orquestra-api"}`.
- A página inicial HTTPS retornou HTTP 200.
- A revisão do banco permaneceu `0010_wame_api_base_url`.
- Não foram executados testes com provedores, envios WhatsApp reais ou homologação
  conversacional com clientes.

## Commits e documentação

O release incluiu os commits locais da funcionalidade e a integração do merge de PR #10.
Depois da publicação, este handoff, `CURRENT_STATE.md`, `HANDOFF_INDEX.md` e o fluxo
local/GitHub/VPS foram atualizados sem alterar código funcional. O commit documental foi
publicado por HTTPS e o checkout Git da VPS foi avançado para o mesmo `main`, sem rebuild
ou reinício adicional. A revisão Git final deve ser confirmada com `git rev-parse HEAD`
em cada ambiente; as imagens de aplicação permanecem no SHA de release acima.

## Riscos e pendências

- Cópia off-site do backup e restauração de ensaio permanecem pendentes.
- Rollback não foi executado nem ensaiado. Não houve alteração de schema; a versão
  anterior conhecida é `bf2f028...`, e o release helper preservou as imagens anteriores
  em tags privadas. Uma reversão de código deve manter o schema e ser feita com revisão
  das imagens/API/worker/web; nenhum rollback automático é prometido.
- As melhorias estão publicadas, mas isso não comprova qualidade do atendimento real.
  Continuidade, fragmentação, confirmação de visita e compatibilidade externa precisam
  de homologação controlada, mantendo saídas suspensas até autorização específica.
- O GitHub foi usado por HTTPS com token já configurado no credential helper. Não
  registrar nem copiar o token para arquivos, terminal ou handoff. SSH permanece o
  caminho de acesso à VPS.

## Próxima ação recomendada

Confirmar a cópia off-site do backup e planejar um piloto controlado. Antes de habilitar
saída, revisar o estado de cada agente, o opt-in de visita, os destinatários de teste e
as respostas observadas; nenhum desses passos foi executado neste release.
