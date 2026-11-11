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
