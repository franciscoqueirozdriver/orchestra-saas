# Handoff — teste de acesso ao modelo no cadastro

**Data:** 13/11/2026
**Branch de implementação:** `feat/test-llm-connection-on-save`
**Base local:** `main`, SHA `702827502f534c39fc2dd8daeaefbe098b40accf`
**Escopo:** testar a conexão de geração após salvar e permitir repetir o teste em
uma conexão já cadastrada. Não muda modelo padrão, principal/fallback dos agentes,
configuração de busca ou comportamento de WhatsApp.

## Implementação

- `POST /api/llm/connections/{id}/test` usa a conexão salva, verifica autorização
  administrativa e tenant por `_get`, envia um prompt técnico fixo com limite de
  64 tokens e devolve somente resultado, categoria segura, código HTTP e duração.
- A rota não persiste `ModelRun`, cooldown, resposta ou estado da conexão. Também
  não limpa pausas nem muda principal, fallback ou embeddings. Erros remotos brutos,
  chaves e texto de resposta não são devolvidos.
- A tela salva a conexão e em seguida testa o modelo. Se o teste falhar, a
  configuração continua salva e o motivo aparece no modal. A lista tem ação
  **Testar modelo** para conexões existentes, com resultado persistente na linha e
  toast. O teste pode consumir quota/custo do fornecedor.
- Não há migration.

## Correção da sessão de login da plataforma

A solicitação adicional esclareceu que o problema era a sessão do painel, não as
credenciais dos provedores de IA. O código define JWT de acesso de 30 minutos por
padrão (`backend/app/config.py`), e o frontend original guardava o token em
`sessionStorage` sem renová-lo. A rota `GET /api/auth/me` já valida o usuário ativo
e retorna um novo token (`backend/app/routes_auth.py`).

`frontend/app.js` agora renova a sessão antes da expiração enquanto a aba está
visível e houve atividade recente; se uma API retornar 401, tenta renovar e repete
essa requisição uma única vez. Se `/auth/me` confirmar 401, a tela volta ao login.
Falhas transitórias de rede não encerram a sessão local. A renovação não funciona
depois que o JWT expirou completamente; após inatividade prolongada ou mudança da
chave JWT, será necessário entrar novamente. Nenhuma migration ou alteração de
backend é necessária.

## Verificações

- Suíte completa em container Python 3.12 e PostgreSQL/pgvector descartável:
  **311 passed, 2 skipped**. Os dois skips exigem baseline de migration original.
- `tests/ui/provider-connections.cjs` em Chrome headless: aprovado; cobriu teste
  automático no salvamento, falha visível, ação para conexão existente, proteção de
  chave em edição e isolamento de chamadas externas do navegador.
- `node --check frontend/llm-ui.js` e `node --check tests/ui/provider-connections.cjs`:
  aprovados.
- `tests/ui/session-renewal.cjs` em Chrome headless com API sintética: aprovado;
  comprovou renovação preventiva antes de expirar e repetição única após 401 sem
  devolver o usuário ao login. Também cobriu a preservação da empresa selecionada
  para `platform_admin`.
- Os testes UI sintéticos `provider-connections.cjs`, `conversation-panel.cjs` e
  `knowledge-storage.cjs` também passaram após as alterações desta branch.
- A suíte de backend havia passado em Python 3.12/PostgreSQL descartável antes da
  correção de sessão (311 aprovados, 2 skips por baseline histórica). Uma tentativa
  posterior usando o Python padrão do host, versão 3.9, falhou na coleta por ser
  incompatível com a sintaxe Python 3.10+ do projeto; não executou os testes. A
  correção de sessão altera apenas o frontend e tem cobertura de navegador acima.
- `git diff --check`: aprovado na revisão final.
- Nenhum fornecedor real foi chamado nesta implementação; os contratos foram
  simulados. Nenhuma mensagem WhatsApp foi enviada.

## Riscos e publicação

O teste é uma chamada externa síncrona e pode levar até o timeout do cliente; pode
consumir quota/custo. A falha não bloqueia a gravação da configuração, evitando
perder a possibilidade de editar credenciais/modelo. O teste não prova qualidade de
resposta nem disponibilidade futura. O endpoint não cria uma tentativa do histórico
de atendimento e deve continuar separado do fluxo de mensagens.

## Publicação

- PR #12 foi integrada primeiro em `09bc61e96f004ade9dd790784469c4a08b17e70b`;
  PR #13 foi então integrada em `33c92680c5df22978b0f33ba34a15060b3ac0493`.
- Os checks `test`, `ui` e `migrations` passaram para a versão integrada. A suíte
  Python 3.12/PostgreSQL descartável reportou 311 aprovados e 2 skips antes da última
  alteração somente de frontend; os testes de UI passaram no SHA integrado.
- VPS `/opt/orquestra`: checkout limpo no SHA `33c92680c5df22978b0f33ba34a15060b3ac0493`.
  Revisão Alembic permaneceu `0012_conversation_memory`; nenhuma migration foi
  executada. API, worker e scheduler compartilham a imagem
  `sha256:dbfa96a05539f69346569fdc5782b46c8b2c5b1fac711ea533579078a192f7cd`, com
  label do SHA alvo. Web, API e serviços dependentes ficaram saudáveis; worker
  respondeu ao ping Celery, Redis respondeu `PONG`, `/health` retornou sucesso e a
  página pública HTTP 200. O código servido contém a rotina `renewSession`.
- A saída global foi observada como `false`. Nenhuma mensagem WhatsApp foi enviada.
- O release helper criou backup operacional cifrado em
  `/home/orquestra/orchestra-preservacao/publicacao-20261105T214148Z/operational-backups`;
  criou recibo privado em `/home/orquestra/orchestra-releases/20261113T181644Z`.
  O helper guardou a imagem anterior para rollback; o digest anterior foi
  `sha256:34365f779e7f9905125d5ca7e4036c59c4e222e6b7c2c9d80f406ce1bd233fc4`.
- A renovação foi validada com navegador/API sintéticos e a presença do bundle foi
  observada em produção. Uma sessão real não foi testada porque não foram fornecidas
  credenciais de usuário; peça para a pessoa testar a plataforma. Após mais de 30
  minutos sem atividade, token expirado ou rotação de chave JWT, novo login ainda é
  esperado.

A proposta de padrão global herdado ao criar agente, com personalização por agente e
pesquisa dos modelos por tarefa, permanece como trabalho separado; nada nesta entrega
altera modelos padrão, principais/fallbacks ou configuração da ferramenta.
