# Handoff — interpretação contextual e continuidade do Enrico

Data: 11/11/2026
Branch: `fix/enrico-live-visit-followups`
Base local: `18643f183b1d8fb11689587c9fbb157f61e0f852`
Estado inicial: dois caminhos privados não rastreados foram preservados, sem inspeção ou stage: `Kit Marca/` e `docs/conhecimento/base-atendimento-climatiza-brasil.md`.

## Objetivo e diagnóstico

Corrigir a interpretação de confirmações curtas no fluxo de visitas e evitar que o código substitua respostas do modelo por resumos/perguntas repetitivas. O webhook atual persiste fatos no estado estruturado, mas antes esta revisão decidia “sim/não” por listas fixas no backend; por isso “Claro” não atualizava o consentimento. Também havia templates determinísticos em `next_opportunity_question` e `_safe_visit_followup`, que podiam repetir endereço, cidade e solicitação.

O backend não dá acesso SQL direto ao provedor. `tasks._build_context` lê histórico, estado, perfil e conhecimento do tenant e inclui essas informações no prompt. A IA lê esse contexto, redige a mensagem natural para o turno e, em fluxos de visita, devolve um envelope JSON com interpretação semântica restrita.

## Alterações

- `backend/app/conversation/behavior.py`: removeu transições de consentimento/recebedor por lista de palavras e as perguntas pré-escritas. Adicionou contrato, parser allowlist e aplicação da semântica apenas quando existe pergunta pendente. O contexto também comunica campos pendentes sem armazenar frases de resposta.
- `backend/app/tasks.py`: injeta o contrato estruturado somente quando `visit_booking_enabled` está ativo; aplica atualizações com lock e revalida revisão/estado antes de persistir; quando a saída é inválida, não envia JSON cru. A resposta de visita gerada pela IA não é substituída por perguntas prontas. Resposta que afirma visita sem evidência continua acionando a intervenção. O resumo de equipe evita duplicar a cidade quando ela já consta no endereço.
- `tests/test_conversation_behavior.py`: teste para “Claro” permanecer ambíguo no parser determinístico e ser confirmado somente após interpretação semântica; teste de resposta inválida e proteção de pergunta contra falso positivo de confirmação.
- `tests/integration/test_runtime_safety.py`: atualiza fluxo sintético de recebedor com envelopes de interpretação; adiciona teste contextual de canal, que persiste consentimento e deixa visita `awaiting_confirmation` sem afirmar reserva.
- `docs/ai/MESSAGE_FLOW.md`, `CURRENT_STATE.md`, `KNOWN_RISKS.md`, `DECISIONS.md` e este índice registram arquitetura, evidências e limites.

Sem migration, tabela nova, alteração de perfil comercial, chamada externa a LLM, mensagem WhatsApp ou mudança de produção.

## Validação

- `python3 -m py_compile backend/app/conversation/behavior.py backend/app/tasks.py tests/test_conversation_behavior.py tests/integration/test_runtime_safety.py`: passou com Python 3.9 do host para sintaxe desses arquivos.
- Unitários em Python 3.12, container efêmero, checkout somente leitura e Git marcado `safe.directory`: **148 passaram**, excluído `test_release_guard.py`.
- Tentativa da suíte unitária completa com Git instalado no container: **152 passaram, 3 falharam**. Uma falha ocorre porque o checkout montado como `/workspace` está somente leitura e não consta como `safe.directory`; duas falhas preexistentes nos testes do `deploy.sh` ocorrem porque o fixture não cria `.env`, requerido pelo próprio script antes de chegar ao Docker falso.
- Integração completa, Python 3.12, PostgreSQL 16/pgvector efêmero em tmpfs, `MEDIA_DIR` em `/tmp`, provedores mockados: **59 passaram, 2 pulados** por ausência da baseline histórica de migrations.
- `git diff --check`: passou após as alterações de código/documentação.
- Não houve teste com Gemini ou outro provedor real; o modelo e o envelope foram simulados. Não foi possível consultar metadados do ModelRun de produção por falha de autenticação da chave SSH carregada. Nenhum conteúdo de conversa foi consultado nessa tentativa.

## Riscos e pendências

- A extração de fatos explícitos (datas, local, telefone) ainda é determinística. Confirmações curtas e recebedor dependem da interpretação semântica do provedor.
- Provedores podem ignorar ou truncar o envelope; a saída inválida falha fechada para intervenção e pode aumentar pausas. Isso precisa de teste autorizado com o modelo habilitado antes de ampliar o uso.
- Não existe agenda integrada. Mesmo com dados completos, preferência não significa reserva; a visita aguarda validação humana.
- A conversa real que gerou o ticket de intervenção permanece pausada e exige claim/ação humana para retomar. Esta alteração local não a reabre.

## Próxima ação

Homologar em uma conversa de teste consentida com o provedor efetivamente selecionado; conferir se o modelo responde no envelope, interpreta “Claro” pelo contexto e não repete perguntas. O commit está em `origin/main`, mas ainda precisa do release controlado para a VPS. O último SHA de aplicação confirmado na VPS é `1f7d1a8333518f0b41d96d72676fd78cd759a8cb`; uma nova verificação falhou porque o agente SSH recusou assinar com a chave carregada. Retomar o deploy somente quando o checkout remoto, a fila e o procedimento de rollback puderem ser conferidos. Não declarar a visita confirmada sem validação operacional humana.

## Git final

Commit de implementação `929561e327163d4a9bb11abc9a0f418f3542a462` foi enviado a `origin/main`, e `main` local foi avançada para esse commit; um follow-up documental registra o bloqueio do deploy. A branch `fix/enrico-live-visit-followups` permanece no commit de implementação. Worktree limpo para arquivos rastreados; permanecem fora dos commits `Kit Marca/` e `docs/conhecimento/base-atendimento-climatiza-brasil.md`. VPS sem sincronização confirmada e sem deploy.

## Continuação — resposta do modelo e encaminhamento de visita

Data: 11/11/2026

O responsável esclareceu que o diálogo deve ser interpretado pelo modelo com o
histórico recente, o perfil do agente e o conhecimento recuperado da empresa; não deve
depender de frases-resposta gravadas. Revisei `_build_context` e o fluxo de
`respond_to_conversation`: o backend envia esse contexto à inferência, o modelo escreve
a resposta da mensagem atual e só depois a aplicação aplica campos semânticos
allowlist. Nenhuma tabela de frases foi criada.

Os testes revelaram duas questões no fluxo de conclusão: quando os dados da visita
ficavam completos, o atendimento podia pular a geração da resposta do turno; e o
detector de promessas classificava uma frase de encaminhamento para confirmar
disponibilidade como compromisso de visita. A correção chama o modelo antes de abrir a
intervenção. Com alerta de equipe confirmado, a resposta contextual recém-gerada é
enfileirada como mensagem do assistente através do outbox, que permite o envio sob
estado `human` para mensagem sem revisão automática. Se o alerta não for confirmado,
o sistema usa aviso operacional que explica a falha. Preferência continua
`awaiting_confirmation`; nenhuma visita é confirmada.

O detector exige uma formulação de compromisso operacional no contexto de data/horário.
Teste unitário cobre tanto “nossa equipe fará a visita amanhã às 10h” (bloqueado) como
“vou encaminhar sua solicitação à equipe para confirmar a disponibilidade” (permitido).
O teste de integração simula a interpretação do modelo e o alerta, verifica que a
resposta do modelo chega ao outbox e a despacha com transporte falso depois da pausa
humana.

## Validação desta continuação

- `tests --ignore=tests/integration --ignore=tests/test_release_guard.py`: **148
  passaram** em Python 3.12. Os seis testes do módulo de guard de release foram
  intencionalmente excluídos desta execução.
- `tests/integration`: **59 passaram, 2 pulados** em PostgreSQL 16/pgvector descartável
  em tmpfs e `MEDIA_DIR=/tmp/orchestra-enrico-media`. Os dois skips continuam sendo
  testes da baseline histórica de migrations indisponível.
- Integrações LLM/WhatsApp mockadas; nenhuma chamada real, migration produtiva ou
  mudança na VPS.
- Sem migration.
- `git diff --check`: executado após a alteração do código; a documentação desta
  continuação ainda estava em edição no momento do registro.

## Git e publicação desta continuação

Commit `34168c0` (`Preserva resposta contextual ao encaminhar visita`) criado na
`main` e enviado com sucesso a `origin/main`. Arquivos de código e testes incluídos:
`backend/app/conversation/behavior.py`, `backend/app/tasks.py`,
`tests/integration/test_runtime_safety.py` e `tests/test_conversation_behavior.py`.
Os documentos canônicos e este handoff registram a continuação em commit separado.
O último estado confirmado da VPS continua sendo o descrito acima; SSH não conseguiu
autenticar, portanto não houve sync nem deploy. Os caminhos privados
`Kit Marca/` e `docs/conhecimento/base-atendimento-climatiza-brasil.md` permanecem
fora do Git.
