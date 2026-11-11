# Fluxo de mensagens WhatsApp

Mapa baseado no código local em `40272d0`, com a melhoria de envio humanizado registrada
abaixo na branch `feat/humanized-whatsapp-delivery`. Descreve implementação local,
não funcionamento homologado na VPS. As rotas mantêm o prefixo legado `zapi`, mas a
entrada reconhece os dois adaptadores.

1. **Entrada e autenticação do callback.** `POST /api/webhooks/zapi/{instance_id}/{callback_token}` valida tamanho, instância ativa e hash do segredo atual ou do anterior ainda válido. Z-API fornece o formato nativo; WAME fornece envelope Meta, convertido por `wame_payload.py`.
2. **Minimização, preempção e fila durável.** Sob o lock advisory do tenant compartilhado com o outbox, o backend deduplica o callback, grava o evento e, se o contato corresponder sem ambiguidade a uma conversa existente, incrementa sua revisão e cancela partes automáticas pendentes na mesma transação. Só depois do commit e da liberação do lock o evento é despachado ao Celery. Se o despacho falhar, evento e invalidação permanecem duráveis para recuperação. Veja `_accept_event` e `_preempt_conversation_for_event` em `routes_zapi.py`, `invalidate` em `conversation/service.py` e `tenant_guard` em `locks.py`.
3. **Processamento de entrada.** `process_webhook_event` usa lock por empresa, descarta eventos de grupo e remove seu payload, consome comandos privados `ASSUMINDO`, ignora ecos correlacionados à outbox e resolve conversas/aliases dentro da empresa e instância. Mensagens são persistidas antes da resposta. Uma mensagem manual não correlacionada (`fromMe`) registra intervenção humana e pausa a automação. Veja `tasks.py`, `interventions.py` e `models.py`.
4. **Política e agendamento da resposta.** Opt-out, estado da conversa, agente atribuído, revisão e controles de envio são conferidos. Entrada de cliente agenda o worker com a janela de agrupamento configurada. Grupos, conversa pausada ou opt-out não seguem para geração automática.
5. **Contexto e geração.** O worker monta contexto com histórico permitido, memória aprovada e trechos de documentos indexados do mesmo tenant. LangGraph usa checkpoint PostgreSQL; o roteador pode tentar conexões LLM alternativas com o mesmo snapshot cifrado. Falha de geração ou pedido não resolvido pode abrir intervenção, conforme política implementada.
6. **Envio.** Respostas humanas e automáticas entram na outbox. O dispatcher revalida empresa, política, agente/revisão e limite de frequência, persiste `dispatching` antes do efeito externo e usa `transport.for_instance` para chamar Z-API ou WAME. Status HTTP aceito não garante entrega. Timeout, 429, 5xx ou ausência de identificador podem resultar em `unknown`; não há retry cego desses efeitos.
7. **Callbacks e recuperação.** Eventos de status são correlacionados com mensagens enviadas e avançam estados sem regressão. O scheduler e as tarefas de recuperação redespacham eventos duráveis pendentes e outbox recuperável; envio interrompido em estado incerto não é reenviado automaticamente.

## Continuidade conversacional e dados de visita — implementação local na branch

O worker mantém um resumo estruturado e temporário dentro de `Conversation.context_state`, ao lado do histórico normal de `Message`. A extração registra fatos explícitos com origem, ID da mensagem e horário, para preservar tipo de ambiente, objetivo, cidade, endereço, preferência de data/horário e urgência. A entrada nova atualiza esse resumo durante o processamento do evento; fatos anteriores mais novos não são substituídos por callbacks atrasados. A ação de assumir/retomar preserva o resumo. Para uma conversa existente sem esse resumo, a primeira geração o reconstrói dos últimos 200 registros de mensagem; não faz backfill ilimitado e respeita expiração já aplicada.

Quando `visit_booking_enabled` está ativo, o backend monta o contexto para a chamada de IA com histórico recente, estado comercial do banco, perfil do agente e trechos de conhecimento aprovados/indexados da empresa. O modelo não consulta o banco diretamente e não recebe acesso a ferramentas. Ele gera a resposta natural daquele turno e devolve também uma interpretação semântica estruturada das confirmações e do próximo dado que perguntou. Não há tabela de palavras ou frases de resposta gravadas para reconhecer “sim”, “claro” ou equivalentes. O backend valida o envelope e só aplica valores permitidos quando a respectiva confirmação foi solicitada; uma saída inválida falha fechada e encaminha para intervenção. As mensagens ao cliente continuam sendo texto produzido pelo modelo, não são substituídas por perguntas comerciais fixas.

O telefone de retorno pode vir somente do campo `phone` numérico do evento direto, nunca de LID, alias de participante ou grupo. Esse metadado fica como não confirmado até consentimento contextual do cliente interpretado pelo modelo. Quando necessário, o modelo pode confirmar se o canal atual serve para retorno; se o cliente recusar, pode pedir outro número. Dígitos de contato são ocultados do contexto enviado ao modelo e das consultas de embeddings. Um alternativo é incluído ao contexto da equipe somente depois de autorizado.

A necessidade de identificar quem receberá a equipe é fornecida como estado ao modelo. Ele considera o histórico para formular a pergunta apenas quando necessária. Se outra pessoa receberá, o sistema pode registrar o nome informado; isso não atribui a ela papel de decisor comercial. Os mecanismos globais de continuidade e linguagem pertencem ao núcleo de conversação; perfil do agente continua sendo a fonte de especialidade, produtos, tom e objetivo comercial. O resumo estruturado complementa o histórico e não armazena respostas prontas.

Preferências do cliente nunca viram reserva confirmada. Quando os dados exigidos estão completos, o backend ainda chama o modelo para responder à mensagem atual e cria a solicitação de intervenção existente; pode alertar o grupo se ele estiver configurado/validado. Se o alerta for confirmado, a resposta contextual recém-gerada pelo modelo é preservada e enfileirada mesmo com a conversa pausada para atendimento humano. Se o alerta não for confirmado, o sistema usa um aviso operacional verdadeiro sobre a falha e mantém o ticket para revisão humana. Sem integração de agenda ou confirmação formal, nenhuma das respostas declara a visita confirmada. A detecção de promessa indevida exige afirmação de compromisso; “encaminhar à equipe para confirmar disponibilidade” não é interpretado como reserva. Não há nova tabela nem migration.

Os testes usam mensagens, números e nomes sintéticos; os envelopes do modelo são simulados e não demonstram que um provedor real seguirá o formato nem interpretará corretamente toda formulação coloquial. Se o modelo não devolver o envelope semântico válido, o fluxo de visita falha fechado para intervenção, em vez de enviar JSON ou presumir consentimento. “Próxima quinta” é preservada como preferência textual; não é convertida para data absoluta sem fuso horário de negócio configurado. Histórico e resumo estruturado são complementares; o resumo expira pela política de contexto configurada.

## Fragmentação humanizada — implementação local na branch

Em toda resposta automática de WhatsApp, `tasks.py` usa `split_reply_conversational`
para agrupar frases e parágrafos sem alterar o texto. A política é global e não depende
do perfil de estilo do agente: respostas curtas ficam inteiras; o máximo é três partes
de 300 caracteres, com alvo de 180 e intervalo durável fixo de 2 segundos. URLs,
valores monetários e padrões comuns de telefone são protegidos contra cortes. Se o texto
não couber com segurança, a geração é encaminhada à intervenção em vez de ser truncada.
Os campos legados `humanized_delivery` e parâmetros de tamanho continuam aceitos pelo
schema por compatibilidade, mas não controlam mais a segmentação.

As partes continuam em `outbox_parts` e são despachadas uma a uma pelo serviço
existente. A entrada e o dispatcher compartilham o lock advisory por tenant. Quando o
webhook é aceito, evento, incremento de revisão e cancelamento das partes pendentes são
confirmados juntos; o payload interno registra qual conversa foi preemptada para que
reentregas e o worker não incrementem a revisão duas vezes. O dispatcher revalida a
revisão, reserva a parte e mantém o lock durante a chamada ao transporte. Assim, após
um webhook correspondente estar duravelmente aceito, uma parte automática antiga ainda
pendente não pode iniciar com a revisão anterior. Se o dispatcher adquirir o lock
primeiro, a chamada externa pode iniciar antes do aceite durável do webhook; esse efeito
já iniciado não pode ser cancelado retroativamente. A resolução ambígua de contato não
preempta uma conversa por inferência. Além disso, `respond_to_conversation` recusa
gerar uma resposta enquanto houver um evento de entrada preemptivo ainda não processado
para aquela conversa; a recuperação durável do webhook pode então concluir a persistência
antes de uma nova geração. A ordem é lock de geração da conversa (quando aplicável),
depois lock do tenant; ingresso, worker do webhook e dispatcher usam somente o lock do
tenant. O lock de sessão é liberado após o commit e antes do despacho ao Celery; o
dispatcher o mantém durante a chamada externa. `unknown` interrompe a sequência e não é
repetido às cegas.

Essa garantia começa no aceite durável, não no recebimento do primeiro byte pelo
servidor. Se o dispatcher vencer a disputa pelo lock, a chamada externa pode já estar
em andamento quando o webhook for aceito. Eventos cujo contato não possa ser associado
com segurança a uma conversa existente não recebem a revisão/preempção antecipada.
Como o lock do tenant permanece ocupado enquanto o transporte responde, uma chamada
lenta também pode atrasar o aceite durável de webhooks dessa empresa; validar esse efeito
sob latência de provedor é parte da homologação controlada.
WAME e Z-API continuam com `composing` desativado nos adaptadores locais; a melhoria
funciona sem indicador de digitação. O prompt global pede resposta completa e concisa
em até três partes; não há uma segunda chamada ao modelo para encurtar. Se exceder o
limite, o fluxo existente de intervenção é acionado. O fluxo comercial de visita é
separado e depende da capacidade `visit_booking_enabled` no perfil do agente, que inicia
desativada; agentes sem essa capacidade não recebem coleta nem encaminhamento de visita.
Não há migration nem homologação de provedor nesta alteração.

## Pontos de privacidade e homologação

- O token de callback fica no caminho da URL: não expor em logs, tickets ou capturas.
- Texto recebido é persistido; mídia comum não é interpretada e aparece como marcador. O normalizador WAME preserva legenda para classificação, mas isso não equivale a processamento do arquivo de mídia.
- Conteúdo de conversa/contexto pode ser enviado ao provedor LLM escolhido. Histórico não se torna conhecimento aprovado automaticamente.
- Testes unitários/integração simulada não homologam callbacks, envio, entrega, criação de grupo ou políticas reais dos fornecedores.

## Código e testes relacionados

- Entrada/validação/deduplicação: `backend/app/routes_zapi.py`, `zapi_payload.py`, `wame_payload.py`.
- Worker, contexto, geração e recuperação: `backend/app/tasks.py`, `model_router.py`, `scheduler.py`.
- Transporte e efeito externo: `backend/app/transport.py`, `zapi_client.py`, `wame_client.py`, `outbox.py`.
- Intervenção: `backend/app/interventions.py`, `backend/app/routes_conversations.py`.
- Estado estruturado, detecção de pergunta repetida e guardas de agenda: `backend/app/conversation/behavior.py`, `backend/app/tasks.py`; número direto: `backend/app/zapi_payload.py`.
- Cobertura: `tests/test_zapi.py`, `tests/test_wame.py`, `tests/integration/test_runtime_safety.py`, `tests/test_scheduler_contract.py`.
