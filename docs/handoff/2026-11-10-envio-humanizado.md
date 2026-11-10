# Handoff — envio humanizado em blocos

Data: 10/11/2026
Estado inicial: checkout principal em `docs/continuity-audit-20261109`, SHA
`6cd1abee696c41c7b80113101f60f4440c066714`; os arquivos não rastreados `Kit Marca/`
e `docs/conhecimento/base-atendimento-climatiza-brasil.md` foram preservados. A
implementação foi isolada no worktree `/tmp/orchestra-humanized-whatsapp`, branch
`feat/humanized-whatsapp-delivery`, criada a partir desse SHA. O branch principal não
foi alterado.

## Objetivo e escopo

Adicionar fragmentação conversacional determinística e opt-in ao diBBerDesk, usando o
outbox e as partes já existentes. Sem alteração do A Mesa, migration, commit, push,
merge, produção ou deploy.

## Alterações realizadas

- `backend/app/conversation/behavior.py`: novo `split_reply_conversational`, com alvo
  180, máximo de 300 caracteres e até três partes por padrão. Preserva o texto por
  concatenação, respeita frases/parágrafos e protege URLs, valores monetários e padrões
  comuns de telefones. Se não couber nos limites, levanta `ValueError`; o caminho atual
  encaminha a resposta ao fluxo de intervenção sem truncá-la.
- `backend/app/schemas.py`: opção `humanized_delivery` desativada por padrão, limites
  globais de alvo (100–180)/tamanho (180–300)/quantidade (1–3) e intervalo seguro de
  1–5 segundos (padrão 2).
  Perfis legados mantêm o comportamento anterior até ativação explícita.
- `backend/app/tasks.py`: seleciona o novo segmentador somente com núcleo conversacional
  habilitado e flag nova ativa; mantém `split_reply` para perfis legados. O worker
  detecta a preempção transacional registrada no webhook e não duplica a revisão.
- `backend/app/conversation/behavior.py`: com a opção ativa, as instruções da primeira
  geração pedem resposta completa e objetiva que caiba nos limites configurados. Não há
  segunda chamada para reescrever respostas longas.
- `backend/app/outbox.py` e `backend/app/conversation/service.py`: mantêm despacho
  durável e acrescentam logs sem texto de mensagem para partes aceitas, estado incerto,
  duração, provedor e cancelamentos de partes pendentes.
- `backend/app/routes_zapi.py`: `_accept_event` usa o mesmo lock advisory por tenant do
  dispatcher; evento deduplicado e invalidação de conversa são confirmados juntos. A
  task Celery é enfileirada somente após a liberação do lock. Reentrega de callback
  pendente reaproveita o marcador `_preempted_conversation_id` e não repete a revisão.
- `frontend/app.js` e `frontend/styles.css`: opção e parâmetros configuráveis no perfil
  do agente; explicação do toggle associada via `aria-describedby`, rótulo explícito e
  contraste melhorado no texto de ajuda. Composing permanece indisponível nos
  adaptadores atuais.
- Testes unitários, integração sintética e UI atualizados para segmentação, limites,
  provedores simulados, interrupção após processamento de nova entrada/takeover e
  `unknown` no meio de sequência. Foi adicionado teste de integração que comprova o
  escalonamento acima do limite sem enviar partes da resposta original.
- Atualizados `docs/ai/CURRENT_STATE.md`, `DECISIONS.md`, `HANDOFF_INDEX.md`,
  `MESSAGE_FLOW.md` e o status original de C02 em `docs/intencoes/`.

## Decisões e limites

- Não criar fila nem migration; `outbox_parts` continua sendo o mecanismo único.
- Uma resposta acima de três partes seguras gera intervenção, não um bloco longo ou
  conteúdo descartado. O cliente recebe a mensagem genérica do fluxo de intervenção;
  esse resultado evita resposta parcial, mas pode ser comercialmente ruim se ocorrer
  com frequência. As instruções do modelo agora pedem concisão na primeira geração;
  não há repetição automática de inferência nem garantia semântica de que o modelo
  conservará todos os detalhes.
- Com o callback duravelmente aceito e contato resolvido sem ambiguidade, evento,
  incremento de revisão e cancelamento das partes pendentes são atômicos. Como ingress
  e dispatcher usam o mesmo lock de tenant, a parte pendente não inicia com a revisão
  anterior após esse commit. Reentrega não repete a invalidação e o worker não duplica o
  incremento. Enquanto o evento marcado ainda não foi processado, `respond_to_conversation`
  retorna `inbound_event_pending`, evitando geração baseada em histórico anterior; a
  recuperação do evento continua sendo o caminho para concluir o processamento. Se o
  dispatcher adquirir o lock primeiro, uma chamada externa pode iniciar
  antes que o webhook seja aceito; ela não pode ser cancelada retroativamente. Contato
  ambíguo não é associado por inferência e não recebe essa preempção até resolução.
- O estado `unknown` continua sem retry automático. WAME e Z-API seguem sem composing
  no código local; nenhuma API de presença foi inventada.
- Não há homologação de fornecedor nem evidência de comportamento em produção.

## Verificações executadas

- `git diff --check`: passou.
- `node --check frontend/app.js`: passou.
- `node --check tests/ui/conversation-panel.cjs`: passou.
- `python3 -m py_compile backend/app/conversation/behavior.py`: passou no Python 3.9
  disponível (arquivo não usa sintaxe incompatível nesse módulo).
- Parse AST de sete arquivos Python com Python 3.9: passou; isso verifica sintaxe, não
  execução/importação no runtime do projeto.
- `pytest -q -p no:cacheprovider tests --ignore=tests/integration`: **149 passaram**
  (Python 3.12 em container local, rede desabilitada, checkout somente leitura).
- `pytest -q -p no:cacheprovider tests/integration`: **57 passaram** (container local,
  PostgreSQL descartável identificado e isolado, `MEDIA_DIR` no `/tmp` do container).
  A primeira execução teve três erros de setup porque o checkout somente leitura
  impedia criar `data/media`; após redirecionar `MEDIA_DIR`, toda a suíte passou.
- Reexecução após o fechamento da janela de ingresso: **149 unitários e 57 de integração
  passaram** novamente. A integração inclui o teste de webhook já persistido enquanto o
  processamento assíncrono está pendente e a parte seguinte pronta para despacho; também
  confirma que a geração responde `inbound_event_pending` até o processamento.
- Após acrescentar uma asserção explícita de que o evento está persistido com
  `processed=False` antes do despacho da parte, o teste determinístico isolado passou:
  **1 passed, 54 deselected**. O PostgreSQL descartável teve a credencial anterior
  restaurada e foi parado.
- Testes novos de integração: webhook durável com Celery pendente preempta a próxima
  parte; reentrega não duplica a revisão; takeover `fromMe` preempta no ingresso; callback
  concorrente espera o despacho externo já iniciado. O teste principal foi executado
  contra o código base `6cd1abe` e falhou como esperado: o despacho retornou `accepted`
  em vez de `ignored`, enviando a parte seguinte. Com a correção passou.
- Exemplos fictícios executados diretamente no segmentador: resposta de 50 caracteres
  ficou em uma parte; texto comercial de 249 caracteres virou blocos de 205 e 44
  caracteres, com conteúdo preservado; texto de 250 caracteres permaneceu em uma parte;
  resposta sintética de 863 caracteres recusada com erro de máximo seguro de partes.
- `git diff --check`, `node --check frontend/app.js` e `node --check
  tests/ui/conversation-panel.cjs`: passaram após as mudanças de frontend.
- `node tests/ui/conversation-panel.cjs`: **passou** em Chrome headless com API sintética.
  O teste encontrou um trecho preexistente que aguardava um diálogo JavaScript nativo,
  enquanto a aplicação usa `<dialog>` próprio; o teste foi corrigido para confirmar pelo
  controle visível da aplicação e agora também verifica rótulo/descrição e ativação
  do toggle pela tecla Espaço.
  `playwright-core` foi instalado apenas em `/tmp/orchestra-ui`; nenhuma dependência do
  projeto foi alterada. Não houve chamadas reais a LLM, WAME ou Z-API.

## Revisão frontend com Modern Web Guidance

Skill disponível em `~/.agents/skills/modern-web-guidance`; guias `forms` e
`accessibility` consultados com Node 22. Na tela de perfil, aplicada associação explícita
de rótulo e descrição de ajuda ao checkbox, mantendo controle HTML nativo, validação
server-side nos limites de `ConversationProfile` e foco visível já existente. O texto de
ajuda foi aumentado para 12px e cor `#526574` (contraste calculado de 6,05:1 sobre branco).
Os valores dinâmicos continuam passando por `esc` antes de entrarem no HTML.

Não foi substituído o checkbox por switch customizado: a opção binária nativa tem teclado
e semântica corretos e evita JS adicional. Não foram feitas mudanças de performance,
compatibilidade geral ou segurança fora dos controles tocados: não havia novos listeners,
fetches, APIs de navegador ou dependências de runtime. A revisão de Chrome foi sintética
em um navegador; não representa teste com leitores de tela, dispositivos reais ou outros
navegadores.

## Investigação do excesso de partes e ritmo

Quando o segmentador recusa por exceder três partes, `tasks.respond_to_conversation`
captura o `ValueError` e chama `_escalate_after_automation_failure`: a conversa é
pausada, uma solicitação de intervenção é criada e o sistema enfileira um aviso
genérico ao cliente. A resposta longa não é persistida em partes nem enviada
parcialmente. Esse comportamento é comprovado pelo teste
`test_core_humanized_overflow_pauses_and_escalates_without_partial_reply`.

O prompt agora orienta o modelo a ser conciso na primeira geração, preservando os dados
necessários e sem transformar cada frase em mensagem. Isso reduz a chance de
escalonamento, mas não comprova que um LLM real obedecerá ou manterá todos os fatos.
Uma segunda geração de resumo não foi adicionada por risco de remover preços, números,
URLs ou condições. Se o escalonamento ocorrer em homologação, medir frequência e revisar
o prompt/limite com exemplos antes de considerar uma tentativa adicional.

O intervalo padrão é 2 segundos, configurável entre 1 e 5. O teste confirma agendamento
durável pelo countdown configurado; não mede percepção de naturalidade, latência real,
nem reação do consumidor. Duas transições com três partes levam ao menos cerca de quatro
segundos entre primeiro e último despacho, além de latência do broker e do provedor.

## Pendências e próximos passos

1. A janela entre aceite durável do webhook e processamento assíncrono foi fechada para
   contatos identificados sem ambiguidade; o teste de regressão também foi verificado
   contra o comportamento anterior.
2. A próxima etapa pode ser homologação controlada, com números de teste autorizados,
   primeiro WAME e Z-API separadamente. Nenhum fornecedor foi chamado nesta sessão.
3. Inspecionar `git diff` e status do worktree antes de eventual commit. Commit, push,
   merge e deploy ainda não foram autorizados.

## Estado Git final da sessão

Branch `feat/humanized-whatsapp-delivery`, base `6cd1abee696c41c7b80113101f60f4440c066714`;
alterações não commitadas nos arquivos listados acima. Sem staged, commit, push, merge
ou deploy. O checkout principal continua na branch de documentação e mantém seus dois
arquivos locais não rastreados.
