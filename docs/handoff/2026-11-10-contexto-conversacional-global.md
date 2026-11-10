# Handoff — continuidade conversacional global e segurança de visitas

**Data:** 10/11/2026
**Branch:** `feat/enrico-context-booking`
**Base inicial:** `46bd99cb140ac7dc006de04f1345529a5afa6e21` (`feat/humanized-whatsapp-delivery`)
**Estado inicial:** worktree temporário isolado; checkout principal não foi alterado. GitHub, VPS e produção não foram consultados.

## Objetivo e escopo

Implementar no núcleo comum mecanismos de continuidade e linguagem natural, aproveitando dados confiáveis, reduzindo perguntas repetidas, confirmando o canal de retorno e identificando a pessoa que receberá a equipe. Impedir declaração de visita confirmada sem evidência operacional. As regras de continuidade são globais; especialidade, catálogo, tom e objetivo permanecem no perfil/prompt do agente. Sem deploy, commit ou chamadas reais a provedores.

## Implementação

- `backend/app/conversation/behavior.py`: extrai campos explícitos para resumo limitado em `Conversation.context_state`, preserva proveniência e timestamps, confirma contexto de respostas curtas, escolhe a próxima pergunta e detecta tentativas de confirmação indevida. Redige telefones antes de compor contexto/modelo.
- `backend/app/tasks.py`: se a conversa precede essa implementação e não tem resumo estruturado, reconstrói um snapshot inicial dos últimos 200 registros recentes, sem usar nomes de perfil ou texto de agente como fatos do cliente.
- `backend/app/tasks.py` e `backend/app/schemas.py`: entrega em blocos agora é política global, sem depender de `ConversationProfile.enabled` nem de `humanized_delivery`; os parâmetros legados seguem aceitos mas não controlam o envio. Respostas longas usam três blocos no máximo, 300 caracteres por bloco e intervalo de 2 s.
- `backend/app/zapi_payload.py`: aceita telefone somente de `phone` numérico de conversa direta; rejeita grupo, LID e aliases de participantes.
- `backend/app/tasks.py`: atualiza o resumo no processamento da mensagem, injeta-o junto ao histórico, substitui perguntas já respondidas, exige confirmação do recebedor e de canal de retorno, e usa `InterventionRequest` existente para pedir validação humana. Qualificação de visitas é uma capacidade separada `visit_booking_enabled` no perfil do agente, desativada por padrão. Sem integração de agenda, a visita fica em `awaiting_confirmation`; o cliente é informado da pendência, inclusive se o alerta não saiu.
- `backend/app/conversation/service.py`: mantém o resumo ao pausar/assumir/retomar.
- `backend/app/interventions.py`: inclui os fatos estruturados úteis no resumo da equipe e expõe telefone de retorno somente depois de autorizado.
- Testes unitários Z-API/WAME e integração sintética verificam o fluxo, variantes de nome do recebedor, detecção de alegações comuns de confirmação e ausência de qualificação de visita em agentes sem essa capacidade.
- Documentação canônica atualizada em `docs/ai/MESSAGE_FLOW.md`, `CURRENT_STATE.md`, `KNOWN_RISKS.md`, `DECISIONS.md` e neste índice.

Não foram criadas tabelas, endpoints, migrations ou filas. Foi adicionado um booleano no JSON do perfil para ativar o fluxo de visitas somente nos agentes que o oferecem. O material de nome/produto do Enrico não foi copiado para regras globais; continua sendo responsabilidade do perfil da Climatiza Brasil.

## Decisões e riscos

- O histórico de mensagens continua sendo o registro conversacional; o resumo estruturado complementa esse histórico e expira segundo `context_minutes`.
- Nome de perfil não comprova identidade. Se o interlocutor não receber a equipe, só um nome informado pelo cliente é salvo para o recebedor; não é considerado decisor.
- Telefone direto do provedor não é consentimento para callback. O cliente confirma o WhatsApp atual ou fornece outro número. Grupo/LID não é telefone pessoal confirmado.
- Não existe integração de calendário. Preferência de data/hora nunca cria uma reserva e o código não marca `confirmed` com base em saída do modelo.
- Extração determinística pode deixar campos ausentes em formulações ambíguas. “Próxima quinta” preserva a frase, mas não se transforma em data absoluta porque não há fuso de negócio por tenant. É necessário avaliar com mensagens de homologação autorizadas antes de ampliar operação.
- A proteção de falsas confirmações cobre paráfrases conhecidas, mas continua heurística; não é uma verificação semântica completa.
- O fluxo usa o sistema atual de intervenção. Grupo não validado ou alerta sem envio deixa a solicitação pendente; nenhuma alegação de alerta enviado é feita.

## Verificações executadas

- Unitários, Python 3.12 em container local: `pytest -q -p no:cacheprovider tests --ignore=tests/integration` — **154 passed**.
- Integração, Python 3.12 e PostgreSQL 16/pgvector descartável em tmpfs, `MEDIA_DIR=/tmp/orchestra-enrico-media`: `pytest -q -p no:cacheprovider tests/integration` — **58 passed, 2 skipped**. Os skips são `test_migration_consolidation.py` sem baseline histórica original.
- O teste de integração da conversa da igreja falhou inicialmente porque o fake não despachava a pergunta antes da resposta do cliente. O teste foi corrigido para simular a entrega e depois passou isoladamente (**1 passed**); a suíte completa de integração passou após essa correção.
- Testes usam nomes/telefones sintéticos e mocks; não houve chamadas reais a LLM, WAME ou Z-API.
- O teste de backfill cobre uma amostra sintética recente; conversas com mais de 200 mensagens não recebem reconstrução integral e dependem do histórico/contexto vigente.
- A extração de datas preserva alternativas como “amanhã ou quinta” para perguntar qual opção o cliente prefere; isso não consulta disponibilidade da equipe.
- UI Chrome não repetida: `playwright-core` não está instalado no ambiente Node disponível, e não instalei dependências. `node --check frontend/app.js` e `node --check tests/ui/conversation-panel.cjs` passaram; são verificações sintáticas, não teste de interface.
- Não executados: CI remoto, homologação com clientes, agenda real, grupo real, VPS ou produção.
- Sem migration. A validação final do diff deve ser repetida após a última atualização documental.

## Próximas ações

1. Revisar a extração com mensagens de homologação autorizadas e exemplos sintéticos adicionais de ambiguidades em português.
2. Homologar em canal/contatos de teste autorizados antes de merge ou deploy.
3. Caso exista agenda futura, desenhar contrato operacional verificável; até lá, visita permanece aguardando confirmação humana.

## Estado Git

No encerramento da implementação e antes da autorização posterior de publicação, as alterações estavam sem stage/commit na branch `feat/enrico-context-booking`; a `main` remota observada estava em `40272d0`, e o checkout principal permanecia na branch de auditoria documental com seus arquivos locais não rastreados preservados. O resultado da autorização posterior de commit, push e sincronização deve ser verificado no histórico Git, no workflow de CI e no recibo privado do release; este handoff registra a etapa de implementação, não é o recibo de produção.
