# Desenvolvimento local → GitHub → publicação na VPS

A pasta local é o ambiente de desenvolvimento; GitHub é a fonte compartilhada e
revisada. `/opt/orquestra` é checkout de publicação, não workspace de programação.
Esta documentação não autoriza executar publicação: a consolidação de 05/11/2026
publica somente uma branch. Leia as pendências em `consolidacao/2026-11-05.md`.

## Rotina local

```bash
cd /home/Alessandra/Documentos/orchestra-saas
git fetch origin
git switch -c feature/nome-da-alteracao origin/main
```

Edite/teste localmente com dados sintéticos, faça diff e revise segredos. Adicione
arquivos por caminho explícito, faça commits e push da branch; abra PR para main.
Exemplo de validação com Python 3.12 e venv próprio:

```bash
python -m pytest -q
python docs/intencoes/atendimento-natural-a-mesa/validacao/verificar_prototipo.py
node --check frontend/app.js
bash -n scripts/*.sh database/init/*.sh
docker compose --env-file .env.example config --quiet
git diff --check
```

A suíte SQL exige banco descartável com nome `orchestra_consolidation_test`; somente
hosts 127.0.0.1 ou `orchestra-consolidation-test-db-20261105` são aceitos. Informe
TEST_DATABASE_URL e ORCHESTRA_BASELINE_ROOT, apontando para a extração do commit
original f6d0e2a. Ela apaga/recria APENAS o schema desse banco de teste; nunca use
DSN de produção. CI tem um job dedicado com pgvector e essa configuração.

As branches não alteram produção. Após revisão e CI aprovado, faça merge pelo
GitHub e registre o SHA completo do commit resultante. Se houver merge commit,
valide esse SHA; não assumir que o SHA do último commit da branch é o SHA de main.
Testes omitidos/skipped devem constar no aceite.

## Primeira passagem após a consolidação

O checkout da VPS continua deliberadamente sujo. O procedimento automático irá
recusá-lo. Não contorne a recusa adicionando arquivos a .gitignore ou rodando reset/
clean. Em uma janela futura aprovada, confira novamente diferenças com o backup
privado e a branch de integração. Se existirem novas alterações, volte à revisão
local antes de qualquer checkout/publicação.

Para preservar em Git local da VPS as 18 mudanças já inventariadas, crie uma branch
de preservação e faça commit com a lista explícita, após revisão de segredos:

```bash
cd /opt/orquestra
git status --short
git switch -c preservation/vps-antes-consolidacao-20261105
git add Caddyfile backend/app/llm_client.py backend/app/models.py backend/app/routes_agents.py backend/app/routes_knowledge.py backend/app/routes_llm.py backend/app/routes_zapi.py backend/app/schemas.py backend/app/tasks.py backend/app/zapi_payload.py backend/migrations/versions/0001_initial.py backend/app/model_router.py backend/app/outbox.py backend/app/policy.py backend/migrations/versions/0002_delivery_controls.py backend/migrations/versions/0003_model_routing.py docs/diagnostico-e-plano-2026-10-30.md docs/implementation-plan.md
git diff --cached --stat
git commit -m "Preserva checkout VPS anterior à publicação consolidada"
git switch main
git status --short
```

Esse commit é preservação excepcional e local; não faça push dele nem merge reverso
automático. O código revisado já estará no GitHub. Os backups fora do repositório
continuam preservados. Não apagar arquivos desconhecidos para “limpar”.

Caddyfile e frontend são bind mounts; reserve janela de manutenção mesmo para a
transição de checkout. Nunca faça essa troca enquanto alguém edita o servidor.
Verifique o site adicional mysalesagent.tech/www após a publicação, pois o mesmo
Caddy o atende. Não remover o bloco por pertencer a outro produto.

Como a versão antiga não tem `scripts/release.py`, use uma cópia do helper revisado
fora do checkout, permitindo capturar corretamente o commit anterior:

```bash
# Substitua pelo SHA completo de main, validado DEPOIS do merge.
RELEASE_SHA='SHA_COMPLETO_VALIDADO'
git fetch --no-tags origin main
mkdir -p "$HOME/orchestra-tools"
chmod 700 "$HOME/orchestra-tools"
git show "$RELEASE_SHA:scripts/release.py" > "$HOME/orchestra-tools/release.py"
chmod 700 "$HOME/orchestra-tools/release.py"
python3 "$HOME/orchestra-tools/release.py" "$RELEASE_SHA" --checkout-root /opt/orquestra
```

A invocação sem `--apply` só confere Git, imagens e revisão Alembic. Recusa destino
fora de origin/main e regressão em relação ao HEAD. Não constrói, não reinicia e
não aplica migrations. Não rode esse helper nesta etapa de consolidação.

## Publicação futura explicitamente aprovada

Antes: concluir bloqueios do relatório, aprovar mapeamento de agentes/configurações,
validar migrations/rollback, preparar passphrase do backup em arquivo protegido e
confirmar que não há tarefas/envios que tornem a manutenção inadequada. Não use
export de segredos no histórico do shell; siga `security-and-operations.md`.

Após conferência sem apply e autorização da janela, use a revisão REAL que foi
consultada imediatamente antes. Exemplo somente para banco ainda em 0001:

```bash
python3 "$HOME/orchestra-tools/release.py" "$RELEASE_SHA" \
  --checkout-root /opt/orquestra \
  --expected-db-revision 0001_initial --allow-schema-change --apply
```

O helper exige checkout limpo, commit completo alcançável de main e HEAD anterior
ancestral do destino. Grava recibo privado com commits/imagens/revisão, exige backup
operacional bem-sucedido, fixa tags das imagens antigas, muda para checkout detached
do SHA e chama deploy. **O deploy aplica Alembic e reinicia aplicação/proxy.**
Portanto --apply só pode ser usado na etapa futura autorizada. Não há sincronização
reversa, merge automático, limpeza de Git nem limpeza de volumes/imagens.

O recibo fica em `~/orchestra-releases/DATA/receipt.json`. Estado final indica
serviços iniciados com checks externos pendentes, não entrega comercial homologada.
Conferir HTTPS de app.salex.tech, mysalesagent.tech/www, saúde, worker, revisão de
banco e fluxos com dados/números de teste autorizados. Não logar tokens ou corpos
com mensagens pessoais. Se falhar, o recibo registra revisão necessária; não faz
rollback de banco automaticamente.

Depois do bootstrap, o próprio `scripts/release.py` pode ser usado do checkout,
sempre com SHA completo. `scripts/deploy.sh` também recusa checkout sujo, mas é
helper de baixo nível; a rotina oficial é release.py.

## Reversão preservada

- **Agora:** não há nada a reverter em produção; main/VPS/serviços continuam como
  antes, e os backups preservam inclusive o WIP que não estava nas imagens.
- **Antes das migrations futuras:** guardar recibo, tags de imagem e backup cifrado
  de dados com .env/chave Fernet preservados separadamente. Não remover imagens
  antigas nem executar prune. Um bundle Git não guarda imagens Docker ou dados.
- **Depois de 0002/0003:** preferir código compatível com schema aditivo e imagens
  antigas fixadas. A base antiga continua exigindo unicidade lógica de conexão IA;
  não retomá-la sem reconciliar conexões múltiplas, vínculos e envios pendentes.
- **Downgrade:** não automático. 0003 recusa múltiplas conexões; snapshots model_runs
  seriam removidos por downgrade e precisam de exportação/retenção previamente
  definidas. Restore de backup exige parada/consistência e pode perder gravações
  posteriores; decisão operacional explícita.
- Restaurar também frontend/Caddyfile da revisão compatível, pois são bind mounts.
  Para pin de imagens, usar override Compose privado apontando `image:` para os IDs/
  tags registrados e `--no-build`; revisar antes quais serviços e entradas de
  migração serão executados. Não reutilizar blindly um deploy que roda upgrade head.

A execução concreta da reversão será revisada para o recibo/revisão/estado real no
momento. Não há promessa de reversão de dados apenas com checkout do código.
