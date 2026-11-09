# Fluxo de mensagens WhatsApp

Mapa do código local em `40272d0`. Ele descreve implementação, não funcionamento
homologado na VPS. As rotas mantêm o prefixo legado `zapi`, mas a entrada reconhece
os dois adaptadores.

1. **Entrada e autenticação do callback.** `POST /api/webhooks/zapi/{instance_id}/{callback_token}` valida tamanho, instância ativa e hash do segredo atual ou do anterior ainda válido. Z-API fornece o formato nativo; WAME fornece envelope Meta, convertido por `wame_payload.py`.
2. **Minimização e fila durável.** O backend reduz o payload aos campos necessários, cria evento idempotente em `webhook_events`, confirma a transação e então o despacha ao Celery. Se o despacho falhar, o evento permanece para recuperação. Veja `routes_zapi.py` e `zapi_payload.py`.
3. **Processamento de entrada.** `process_webhook_event` usa lock por empresa, descarta eventos de grupo e remove seu payload, consome comandos privados `ASSUMINDO`, ignora ecos correlacionados à outbox e resolve conversas/aliases dentro da empresa e instância. Mensagens são persistidas antes da resposta. Uma mensagem manual não correlacionada (`fromMe`) registra intervenção humana e pausa a automação. Veja `tasks.py`, `interventions.py` e `models.py`.
4. **Política e agendamento da resposta.** Opt-out, estado da conversa, agente atribuído, revisão e controles de envio são conferidos. Entrada de cliente agenda o worker com a janela de agrupamento configurada. Grupos, conversa pausada ou opt-out não seguem para geração automática.
5. **Contexto e geração.** O worker monta contexto com histórico permitido, memória aprovada e trechos de documentos indexados do mesmo tenant. LangGraph usa checkpoint PostgreSQL; o roteador pode tentar conexões LLM alternativas com o mesmo snapshot cifrado. Falha de geração ou pedido não resolvido pode abrir intervenção, conforme política implementada.
6. **Envio.** Respostas humanas e automáticas entram na outbox. O dispatcher revalida empresa, política, agente/revisão e limite de frequência, persiste `dispatching` antes do efeito externo e usa `transport.for_instance` para chamar Z-API ou WAME. Status HTTP aceito não garante entrega. Timeout, 429, 5xx ou ausência de identificador podem resultar em `unknown`; não há retry cego desses efeitos.
7. **Callbacks e recuperação.** Eventos de status são correlacionados com mensagens enviadas e avançam estados sem regressão. O scheduler e as tarefas de recuperação redespacham eventos duráveis pendentes e outbox recuperável; envio interrompido em estado incerto não é reenviado automaticamente.

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
- Cobertura: `tests/test_zapi.py`, `tests/test_wame.py`, `tests/integration/test_runtime_safety.py`, `tests/test_scheduler_contract.py`.
