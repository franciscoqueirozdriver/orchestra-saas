# Handoff — consolidação, ingestão privada e publicação Orquestra

**Data:** 06/11/2026

**Fonte de código:** `franciscoqueirozdriver/orchestra-saas`

**Pasta de desenvolvimento:** `$HOME/Documentos/orchestra-saas`

**Destino:** VPS `/opt/orquestra` (usuário de operação `orquestra`)

Este documento registra o estado revisado após a publicação autorizada. Não contém
conteúdo de conversas, transcrições, credenciais nem dados de clientes. Para a
rotina repetível, consulte [fluxo local/GitHub/VPS](../fluxo-local-github-vps.md).

## 1. Estado final resumido

- No instante do deploy, GitHub `main`, checkout local `main` e checkout da VPS
  apontavam para `edccf4617181a4b58ff81bd3c809887e10355712`.
- Este handoff e os ajustes documentais posteriores ao deploy formam um commit
  apenas de documentação. Depois de publicado, o checkout da VPS é avançado para
  esse SHA documental sem reiniciar serviços; as imagens continuam apontando para
  o SHA do release de aplicação listado abaixo.
- API, worker e scheduler executam a mesma imagem Docker, com label de revisão
  apontando para esse SHA. Todos foram reportados saudáveis após o deploy.
- PostgreSQL permaneceu em `0007_search_connection`. O destino não contém alterações
  em `backend/migrations/`; nenhuma migration Alembic foi aplicada nessa publicação.
- A API respondeu `{"ok":true,"service":"orquestra-api"}` em
  `https://app.salex.tech/health` após o deploy.
- `OUTBOUND_ENABLED=false` foi forçado pelo release helper. Não há autorização de
  piloto ou envio real implícita neste handoff.
- O acervo de WhatsApp continua somente em staging privado local. Nenhum dado foi
  enviado a provedor de IA/embeddings ou importado/indexado em produção.

## 2. Histórico Git e composição da publicação

| Marco | SHA | Descrição |
|---|---|---|
| `main` antes da atualização | `6bb38bdd779001c82f1d28827913afaee1466ce5` | Ponto comum que estava no GitHub e na VPS antes da publicação |
| Funcionalidade de usuários de empresa já desenvolvida na branch | `72416511a2ebb890c89317708271a43431079c82` | Permite gerenciar usuários da empresa |
| Publicação final | `edccf4617181a4b58ff81bd3c809887e10355712` | Inclui a funcionalidade acima e o staging privado de conversas |

O commit final foi publicado diretamente em GitHub `main` conforme autorização da
responsável. A branch local foi trocada para `main` e avançada por fast-forward.
O workflow [Validate no GitHub Actions](https://github.com/franciscoqueirozdriver/orchestra-saas/actions/runs/42151925161)
terminou com conclusão `success` para o SHA final.

O commit de documentação criado após esse release não modifica código, frontend,
Compose, Dockerfile ou migrations. A pasta `docs/` é excluída do contexto Docker; por
isso não exige rebuild/restart e não altera a identificação das imagens de aplicação.

O commit novo acrescentou/alterou somente código do pipeline privado, migrations
SQLite exclusivas do staging, testes sintéticos e documentação técnica. Também
foram incluídas as alterações de gestão de usuários que já estavam no commit
anterior da branch. As migrations `0002`–`0004` do pipeline WhatsApp não são Alembic,
não são chamadas pela aplicação de produção e não estão na cadeia de schema do
PostgreSQL.

### Arquivo mantido fora do Git

`docs/conhecimento/base-atendimento-climatiza-brasil.md` permanece como arquivo local
não rastreado e não foi incluído. Ele reúne dados comerciais e informações extraídas
de conversas, propostas e contratos; precisa de revisão de privacidade, atualidade e
autorização da empresa antes de qualquer publicação ou upload. Os arquivos brutos em
`docs/Conversas/` também continuam ignorados por Git e Docker.

## 3. Processo e resultado da ingestão privada

### Persistência e proveniência

O banco SQLite de staging fica fora do repositório, protegido por permissão local
restrita. Migrações `0001`–`0004` adicionam autores por exportação, cartões VCF e
candidatos de contato, papel da pessoa na conversa e evidências de telefones. O
staging preserva origem, hash, versão, mensagens, ordem, data textual, anexos,
transcrições/segmentos, status e erros. A chave de autor não é unificada entre
exportações só porque o nome se repete.

Os totais auditados foram:

- 61 cópias/exportações de texto e 60 hashes distintos;
- 8.013 linhas incluindo eventos/mensagens de sistema; 7.799 mensagens de pessoas;
- 120 registros de autor: 59 classificados como equipe pelo nome confirmado pela
  responsável, 59 classificados como cliente apenas como contraparte de exportação
  1:1, e dois sem papel atribuído;
- 4.159 mensagens da equipe, 3.583 mensagens de cliente e 57 mensagens cujo autor
  permaneceu sem papel;
- 1.225 associações de anexos foram registradas no staging; os vínculos somente são
  feitos por referência compatível dentro do mesmo conjunto/exportação, sem inferir
  pelo horário ou proximidade de mensagens.

### Telefones e contato WhatsApp

O staging registra telefone com evidência, mas um número no texto não é o mesmo que
um `contact_key` recebido pela integração. O processamento identificou oito vínculos
com um telefone único e evidência local; sete candidatos com múltiplos números ou
conflito ficam pendentes. Telefones em rótulos de autor são evidência da exportação,
mas não foram convertidos automaticamente em chaves de contato da integração.

Cartões de agenda e nomes são candidatos de associação, não prova suficiente por si
sós. Para associar um histórico antigo a uma conversa do WhatsApp, será necessário
confirmar pessoa/telefone e registrar o identificador estável da integração. Essa
ponte e a importação no histórico de produção ainda não foram implementadas nem
executadas.

### Áudio, vídeo e qualidade

O modelo `tiny` de faster-whisper rodou localmente em CPU int8, offline, com FFmpeg.
Foram concluídas 785 transcrições: 738 áudios e 47 vídeos, gerando 4.733 segmentos.
Seis vídeos não possuem faixa de áudio e não podem produzir transcrição de fala.
428 segmentos ficaram abaixo do limiar interno de confiança; isso é um sinal para
revisão, não uma medida de acurácia. Não foi calculado WER contra referência humana.

Transcrever a fala de um vídeo não interpreta suas imagens. O pipeline não infere
produto, pessoa, texto na tela, ambiente ou intenção visual. Falantes dentro do áudio
não foram diarizados. Transcrições e anexos permanecem sujeitos a revisão humana.

### Histórico versus conhecimento

Foram gerados dois resultados privados e distintos:

1. **Histórico reconstruído:** JSON privado com mensagens em sequência, autor,
   referências de anexos, transcrições e avisos de revisão. É preparação para
   continuidade futura por contato, não importação no banco de produção.
2. **Exemplos gerais de atendimento:** cópia derivada com 59 diálogos e 7.721
   mensagens, deduplicada por hash somente nessa saída e repartida em quatro arquivos
   com limite de tamanho. Inclui rótulos equipe/cliente quando comprovados,
   anonimização automática e advertência de que relatos/preços antigos não são regra
   atual. Ainda precisa de revisão humana de privacidade e semântica.

O redator automático mascara padrões comuns e nomes reconhecidos, mas não garante
anonimização. Texto livre, contexto, voz, imagens e anexos exigem revisão. Mensagens
históricas, opiniões, instruções citadas, orçamentos antigos e preços não viram
automaticamente políticas ou fatos atuais. Nenhum dos arquivos foi enviado ao painel
Conhecimento nem a um provedor de embeddings.

## 4. Deploy da VPS

### Pré-condições verificadas

- Antes do deploy, `/opt/orquestra` estava limpo e em
  `6bb38bdd779001c82f1d28827913afaee1466ce5`.
- API, worker, scheduler, web, DB e Redis foram inventariados; API, worker e scheduler
  estavam na mesma imagem antes da mudança.
- `scripts/release.py` em modo de conferência buscou `origin/main`, validou o SHA
  final e informou revisão DB `0007_search_connection` e `Alteração de migrations:
  False`.
- Não houve reconstrução ou reinício durante a conferência sem `--apply`.

### Aplicação e evidência depois do deploy

O comando autorizado foi executado com SHA completo e revisão DB observada
imediatamente antes: `scripts/release.py ... --expected-db-revision
0007_search_connection --apply`. O processo:

1. gravou recibo privado em `~/orchestra-releases/20261106T024352Z/receipt.json`;
2. criou backup operacional criptografado sob
   `~/orchestra-preservacao/publicacao-20261105T214148Z/operational-backups`;
3. preservou tags de rollback para imagens antigas;
4. fez checkout detached do SHA publicado, executou build/deploy e recriou o proxy;
5. manteve `OUTBOUND_ENABLED=false` nos novos contêineres.

Após a operação, o estado observado foi:

| Serviço | Estado observado | Imagem/revisão |
|---|---|---|
| API | saudável | imagem `sha256:8d83f4567bcb26883c3b419e5198d248ab2f390538014e8d5ee5742fe663dbff`, revisão `edccf4617181a4b58ff81bd3c809887e10355712` |
| Worker | saudável | mesma imagem/revisão da API |
| Scheduler | saudável | mesma imagem/revisão da API |
| PostgreSQL | saudável | revisão Alembic `0007_search_connection` |
| Redis | saudável | sem alteração de schema |
| Caddy | em execução | proxy recriado pelo release helper |

`https://app.salex.tech/health` respondeu sucesso. `mysalesagent.tech` e
`www.mysalesagent.tech` retornaram HTTP 307; apenas o código de resposta foi
verificado, não o destino final do redirect nem os fluxos do outro site. Login,
gestão de usuários, UI, conexões de provedores, callbacks reais e atendimento com
mensagens não foram homologados por esta publicação.

O recibo termina em `started_external_checks_pending`, que é o estado padrão do
helper após iniciar serviços. A checagem HTTPS de saúde e o estado saudável dos
serviços foram feitos em seguida, mas o recibo não foi editado manualmente.

### Backup e reversão

O backup criptografado foi criado, mas não foi verificada cópia para armazenamento
externo nem um restore de ensaio. Antes de depender dele para recuperação, copiar
arquivo e checksums para armazenamento externo e manter a passphrase separada. Não
colocar a chave/passphrase no Git, neste handoff ou em logs.

Não houve migration do banco de aplicação; a revisão continua `0007`. Isso reduz o
risco de reversão de schema, mas não elimina os riscos de regressão de código. O
recibo e as tags antigas orientam rollback. Não executar `git reset`, limpar imagens,
remover volumes nem reverter o banco automaticamente. Planejar janela e conferir
API/worker/scheduler juntos; código antigo pode não compreender o scheduler atual.

## 5. Verificações e limitações

| Verificação | Resultado | Limite |
|---|---|---|
| Testes direcionados de ingestão e pipeline | 19 passaram localmente | Fixtures sintéticas; não verificam qualidade humana de transcrição |
| Suíte local completa | Não coletou no Python global 3.9 | O código requer Python 3.10+; use Python 3.12 |
| GitHub Actions `Validate` no SHA final | `success` | CI não homologa serviços externos ou mensagens reais |
| Shell, sintaxe JS, compile Python do pipeline, Compose e `git diff --check` | passaram localmente | Não substituem testes de aceitação em navegador/provedores |
| Release helper, sem apply | aprovado; checkout limpo e revisão 0007 | Só leitura operacional |
| Deploy e saúde HTTPS | API/worker/scheduler saudáveis; health endpoint responde | Fluxos funcionais, contas/provedores e os redirects dos sites adicionais seguem sem homologação |
| Imagens de conversa e áudio transcrito | processados localmente | Imagens não interpretadas; transcrições abaixo do limiar precisam de revisão |

Não usar a falha de coleta local de Python 3.9 como falha do código Python 3.12:
os tipos `T | None` do runtime exigem 3.10 ou superior. A execução oficial Python
3.12 do GitHub Actions terminou com sucesso neste SHA.

## 6. Próximas ações recomendadas

1. Copiar backup cifrado e checksums para fora da VPS e registrar localização segura;
   considerar um restore ensaiado em ambiente isolado.
2. Validar redirects dos domínios adicionais e confirmar a operação dos sites que
   compartilham Caddy, sem alterar seus blocos de proxy.
3. Fazer smoke test autenticado de login, criação/edição de usuários, empresas,
   atribuição de agente, conexões e navegação usando dados de teste autorizados.
4. Manter saída automática suspensa até aprovação e plano de piloto. Não habilitar
   outbound somente porque o build e healthcheck passaram.
5. Revisar localmente o corpus privado: PII residual, papel de autores, fidelidade de
   transcrição, atualidade de afirmações comerciais e consistência empresa/fonte.
6. Após a revisão do corpus, propor pacote versionado e aprovado por empresa. A
   importação no histórico ativo e a indexação de conhecimento são projetos
   separados, exigem mapeamento de contato/tenant e autorização própria.
7. Para qualquer próximo deploy, abrir nova branch da `origin/main`, PR, CI verde,
   revisão do SHA e conferência sem `--apply` na VPS antes de autorização de apply.

## 7. Privacidade e manutenção deste handoff

Este arquivo documenta arquitetura, contagens agregadas, SHAs, estados e caminhos de
recibos/backup. Não registrar nomes de clientes, números, trechos de mensagens,
transcrições, conteúdo de VCF, tokens, chaves, passphrases ou valores de `.env`.
Atualizar o handoff quando houver mudança de estado; preservar os números como
histórico datado, sem tratá-los como estado atual após nova ingestão ou deploy.
