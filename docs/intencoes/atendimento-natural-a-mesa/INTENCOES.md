# Intenções — trazer o atendimento natural do A Mesa para o Orquestra

Data: 03/11/2026. Status: proposta original; C02 recebeu uma implementação inicial local
na branch `feat/humanized-whatsapp-delivery` em 10/11/2026. Não representa merge,
deploy ou homologação. As demais intenções continuam exigindo verificação individual.
Responsabilidade: evolução do atendimento conversacional, preservando isolamento entre empresas.

## Decisão e resultado esperado

Aproveitar o comportamento conversacional amadurecido no A Mesa e adaptá-lo ao backend Python/FastAPI/Celery do Orquestra. Não portar a aplicação inteira, nem converter o SaaS em uma aplicação específica de igreja. A pessoa deve conseguir escrever em fragmentos, enviar áudio, corrigir o pedido, mudar de assunto e solicitar um humano sem perder o contexto nem receber mensagens repetidas.

Naturalidade significa compreender e atender com clareza. Não significa fingir ser uma pessoa: se perguntado, o assistente deve informar que é automatizado. Não reproduzir a regra antiga que trata toda identificação como assistente virtual como um erro de estilo.

## Bases e evidências

- Orquestra: commit `f6d0e2a`, modelos em `backend/app/models.py`, tarefas em `backend/app/tasks.py`.
- A Mesa atual examinado: `82100a9`, incluindo existência de alterações locais ainda não commitadas em relatórios. Essas alterações NÃO são a base dos snapshots.
- Base histórica escolhida para consulta: `dd19753` (15/09/2026), antes das intervenções de outubro. É uma referência de código, não uma declaração de versão perfeita ou validada em produção.
- `d8bfbdf`: humanização inicial, em 27/08; `74cb4b5`/`9dbba42`: ampliação; `400fa98`: fallback e pipeline; `449fed5`: correções de loops, catálogo, cancelamento e duplicação; `ac23e89`: interpretação de capacidades e reformulação antes de encaminhar ao humano.
- Conferir `referencias-a-mesa/manifesto.json`: caminho original, revisão completa e SHA-256 de cada snapshot. Uma fixture teve telefone removido; o manifesto registra a sanitização e também o hash original. Arquivos TypeScript têm dependências do A Mesa e NÃO são módulos executáveis do Orquestra.
- Não copiar configurações por telefone/nome de líderes, dados de membros, chaves, Vault, payloads reais ou logs privados. Não presumir que o código local corresponde às Edge Functions implantadas; o webhook stub deprecated não serve como fonte de deploy.

## Escopo de transferência

| ID | Intenção e origem no A Mesa | Destino proposto no Orquestra | Entrega observável |
|---|---|---|---|
| C01 | Pausas e composing: `humanize.ts`, `whatsapp-processar-fila/index.ts` | `conversation/pacing.py`, adaptador Z-API | Presença opcional, pausa curta limitada; falha de presença não bloqueia o texto |
| C02 | Divisão por parágrafos/frases: `chunkRespostaWhatsApp.ts` | `conversation/chunking.py`, `outbox_parts` | Bolhas ordenadas, sem cortar texto em 4.000 caracteres; revalidação antes de cada parte |
| C03 | Agrupamento contextual: `mensagemDebounce.ts` | tarefas existentes + política de turno | Mensagens rápidas viram um turno; cancelar e chamar humano são imediatos; há teto de espera |
| C04 | Estado, retomada e mudança de assunto: `conversationEscape.ts`, `mudancaAssuntoConversa.ts`, `conversaIdleGate.ts` | `conversation/state.py`, roteador e estado persistido | Pergunta lateral respondida sem perder o fluxo; confirmação só para ambiguidade/efeito relevante |
| C05 | Histórico com intenção e argumentos: `consultaContextoGerencial.ts` | `conversation/context.py`, `conversation_turns` | “E os outros?” preserva filtro/assunto; contexto com validade e resumo de resultado |
| C06 | Cancelamento: `whatsappCore.ts`, handlers de receber | revisão atual + epoch de cancelamento e partes | “Cancela” invalida trabalho anterior ainda não enviado; não apaga histórico |
| C07 | Humano: `humanTakeover.ts`, `autonomyGate.ts` | `conversation/handoff.py`, API e painel | Operador assume/retoma; bot não disputa atendimento; promessa de encaminhamento exige registro real |
| C08 | Tom, personalização e perfis: prompts em `whatsapp-receber`, `ministerioPack.ts` | `agents.persona_config`, serviço de contexto | Nome de preferência e tom por empresa/agente, sem listas fixas de telefones |
| C09 | Qualidade da saída: `outputGuard.ts`, `groundingNomes.ts`, `enfileirarRespostaBot.ts` | `conversation/output_guard.py` | Limita excesso de markdown/emojis, preserva sentido, verifica alegações com evidência e não cria fallback repetitivo |
| C10 | Áudio: `processarAudioRecebido` em `whatsapp-receber/index.ts` | `media/transcription.py`, worker e adaptador | Transcrição vira mensagem do turno; baixa com limites; avisa quando não conseguiu ouvir |
| C11 | Ferramentas: `toolDispatcher.ts`, catálogo, `executarCapacidadeBot.ts` | `tools/registry.py`, schemas e política | Consultas autorizadas com dados reais; nenhum dado de negócio inventado; ações exigem autorização e, quando necessário, confirmação |
| C12 | Gateway resiliente: `aiGateway.ts` | extensão de `llm_client.py`, configuração de provedores | Fallback somente em erros transitórios e com consentimento/configuração da empresa; ferramenta não executada duas vezes |
| C13 | Recuperação após erro: `feedbackRespostaBot.ts`, `escalacaoResposta.ts`, `perguntasNaoRespondidas.ts` | feedback, casos de qualidade e painel | “Não foi isso” recupera o pedido anterior, pede no máximo uma reformulação por episódio e registra lacuna |
| C14 | Memória e conhecimento: contexto + `conhecimentoIgrejaRag.ts` | memória existente + aprovação/proveniência | Preferência validada reaproveitada; correção humana não vira verdade global automaticamente |
| C15 | Privacidade, consentimento e operação: `piiMask.ts`, `consentService.ts`, `campaignGates.ts`, `limitesDiariosWhatsApp.ts`, `filaPacing.ts` | política por empresa/contato, métricas e fila | Opt-out, limites, horário e kill switch; mensagens transacionais e campanhas com regras distintas |
| C16 | Evidência e avaliação: testes de debounce, saída, router e cancelamento do A Mesa | testes Python e corpus conversacional | Regressões de sentido, duplicação, loops, retomada e mistura de tenants impedem liberação |

C01–C16 definem o escopo, não funcionalidades já entregues. RAG e memória já existentes serão ampliados; não criar uma segunda base paralela. Algumas capacidades acima são generalizações dos mecanismos do A Mesa e precisam ser implementadas no Orquestra, não copiadas literalmente.

## Fora desta transferência

Não importar pessoas, igreja, cultos, ministérios, regras pastorais, relatórios de Mesa, estudos/PDFs religiosos ou filtros de cadastro do A Mesa. Não portar automaticamente atualizações cadastrais nem aprovações específicas da igreja. Usar esses fluxos apenas como exemplos de ferramentas e coleta de dados autorizadas.

Não incluir agora faturamento SaaS, autoinscrição, CRM/Calendar específico, voz sintetizada, visão de imagens/vídeos ou agentes independentes cooperando. Ficam como extensões futuras. Cadastro de múltiplos agentes deve evoluir primeiro para seleção explícita por instância ou conversa, com fallback documentado; não manter a seleção silenciosa do primeiro agente como regra final.

## O que existe hoje e deve ser preservado

Orquestra já tem filtros tenant, segredos cifrados, webhook deduplicado, locks Redis, revisão de conversa, outbox única por revisão, PostgreSQL/pgvector, RAG, histórico recente e checkpoints LangGraph. Preservar esses mecanismos durante a adaptação.

O RAG deve usar perguntas do turno completo e evidência com fonte. O histórico tem que distinguir mensagem do usuário, transcrição, mensagem de operador, resultado de ferramenta e texto citado. Não elevar documento/transcrição a instrução de sistema. Resumos não substituem o registro original.

## Pipeline pretendido

1. Validar webhook e persistir evento deduplicado dentro do tenant/instância.
2. Normalizar texto/mídia. Áudio é processado com idempotência e limites; URL temporária não pode ser perdida pela minimização atual do payload.
3. Incrementar revisão/turno de entrada com lock; comandos de cancelar, opt-out e humano passam antes do debounce e da IA.
4. Agrupar fragmentos por conversa. Separar último inbound do último outbound: o `last_message_at` atual mistura ambos.
5. Carregar estado, atribuição de agente, contexto recente, memórias aprovadas, consentimento e política de operação.
6. Rotear para resposta direta, consulta autorizada, fluxo, correção ou humano. Um classificador ajuda a interpretar, não concede permissão.
7. Executar consultas/ferramentas com schema, limite, evidência e idempotência. Ações de escrita entram em aprovação quando aplicável.
8. Gerar texto com instruções de tom e resultado real. Adaptar naturalidade ao assunto; não quebrar toda frase nem acrescentar pergunta artificial a toda resposta.
9. Validar saída, suprimir repetição indevida e verificar revisão, cancelamento, humano, consentimento, configuração e agente.
10. Criar um outbox pai por revisão. Persistir partes ordenadas; o dispatcher revalida cada parte e publica de forma serial por conversa.
11. Registrar aceite externo separado de entrega/leitura. Timeout ambíguo vira `unknown`; reconciliar antes de repetir, sem prometer exactly-once na API externa.
12. Atualizar contexto, auditoria e métricas. Fallback de IA deve preservar as mesmas regras e não repetir efeitos.

A corrida entre validação final e envio externo não pode ser eliminada só por verificar revisão: serializar e registrar a decisão no banco, testar concorrência e documentar a janela residual.

## Contratos de código e interface

A pasta `codigo-proposto/` contém uma referência Python executável de políticas puras, NÃO integrada à API. A implementação final deve dividir responsabilidades e adicionar persistência, autorização e adaptadores. Não promover esse protótipo diretamente para produção.

Rotas novas pretendidas, sempre por tenant resolvido no backend:

- `PUT /api/agents/{id}/conversation-policy`: perfil, tom, limites e recursos habilitados.
- `PUT /api/zapi/instances/{id}/default-agent`: atribuição de agente da mesma empresa.
- `POST /api/conversations/{id}/takeover` e `/resume`: operador autorizado assume/retoma.
- `POST /api/conversations/{id}/cancel`: invalida pendências anteriores; autorização adequada ao canal/painel.
- `POST /api/conversations/{id}/messages`: mensagem humana registrada com autoria, revisões e outbox.
- `POST /api/conversations/{id}/feedback`: vínculo com pergunta/resposta e caso de qualidade.
- CRUD/revisão de memória e `GET/PATCH /api/quality/cases/{id}`.
- Configuração de ferramentas e provedores sem devolver segredos; callback de entrega autenticado separado do received callback.

Painel: mostrar agente responsável, modo IA/humano, motivo de pausa, fila/estado de entrega, lacunas e memórias pendentes. Configuração de estilo tem exemplos de resposta. Mensagem de encaminhamento não pode sugerir fila/atendente inexistente. Nenhum endpoint existe apenas por estar listado aqui.

## Migrações e compatibilidade

`migracoes-propostas/001_estado_e_politicas.sql`, `002_turnos_e_entrega.sql` e `003_qualidade_ferramentas_e_midia.sql` são drafts PostgreSQL específicos do schema atual do Orquestra. Os SQL originais do A Mesa ficam em referências para estudar debounce/lacunas, não para executar neste banco.

Antes de promover: revisar IDs VARCHAR(36), constraints de tenant, permissões, defaults, planos de consulta e volume real; converter em revisões Alembic com upgrade/downgrade explícitos e models sincronizados. NÃO continuar o padrão da migração inicial que usa os metadados vivos (`create_all`) para descrever versões futuras.

Os drafts usam índices/constraints comuns e transação. Em tabela grande, medir lock e decidir revisão separada para índices CONCURRENTLY, com autocommit Alembic; não executar CONCURRENTLY dentro da transação destes drafts.

Backfill: política conservadora, recursos novos desabilitados, estado IA aberto como antes, `last_inbound_at` a partir de mensagens incoming; agente padrão só quando há um candidato inequívoco. Não ativar auto-resposta ao migrar. Sem backfill automático de memórias como aprovadas; manter leitura legada atrás de flag até revisão. Não transformar histórico antigo em autorização ou consentimento.

Implementar retenção/exclusão por empresa para turnos, transcrições, mídia, qualidade, consentimento e checkpoints. Logs não contêm prompt completo, token nem URL temporária. RLS não é simulada nestes drafts: a aplicação compartilha usuário de banco; isolamento precisa de constraints + autorização testada. Avaliar RLS em projeto próprio.

## Sequência de entrega

| Fase | Escopo | Condição para avançar |
|---|---|---|
| P0 | Congelar baseline e corpus; comparar revisões históricas | Casos do A Mesa reproduzidos, distinção entre bug histórico e regra intencional |
| P1 | C01–C03, C06 e partes de C09; outbox por partes e controles | Sem mensagem duplicada/obsoleta em testes de concorrência; rollback por flag |
| P2 | C04–C08 e atribuição; turnos e takeover | Interrupção, retomada e atendimento humano funcionam sem loops |
| P3 | C10–C12; mídia e ferramentas somente leitura inicialmente | Áudio seguro, fallback validado e ferramentas isoladas por tenant |
| P4 | C13–C16, memórias revisadas, painel e avaliações | Corpus e carga aprovados, piloto com conversas reais consentidas |

Não habilitar ferramentas com escrita antes de idempotência, permissões e aprovação. Controles de consentimento/kill switch e observabilidade mínimos entram antes de qualquer piloto, mesmo que o painel completo venha em P4.

## Regressões a não transportar

- Gate “continuar/nova” repetido indefinidamente: não mais que uma clarificação por episódio; depois rota segura/humano disponível.
- “Não. Quero outra coisa”: interpretar a negação E o novo pedido, sem descartar o restante.
- Matchers amplos de domínio: não decidir intenção só por “qual + mesa”, “cadastro” ou saudação inicial.
- Não recriar sessões de relatório para toda conversa; fluxos estruturados são uma capacidade opcional.
- Não deduplicar globalmente por texto: distinguir replay do mesmo turno de pergunta legítima repetida depois.
- Não cortar listas, nomes e números para cumprir limite estilístico; usar partes/anexo com evidência.
- Não usar regex de nome capitalizado como prova suficiente de alucinação; comparar com fontes e intenção.
- Não falhar silenciosamente em erros de fila/gateway nem prometer humano sem registrar o atendimento.
- Não importar roteamento por telefones e nomes reais do A Mesa.
- Não produzir duas camadas de divisão (1.500 caracteres no enqueue e 500 no envio) sem contrato único.
- Não bloquear toda resposta que mencione que é IA: ser transparente quando perguntado.

## Validação, implantação e reversão

Ver `validacao/CENARIOS.md`. Testes de funções puras são só início; é obrigatório testar PostgreSQL/Redis, contratos Z-API simulados, estados do painel e um piloto autorizado. Não usar destinatários de produção em testes automáticos.

Snapshot cifrado e teste de restauração antes da migração. Ordem: schema aditivo → código compatível com flags desligadas → backfill revisado → piloto por tenant → ampliação. Implementação via revisão/commit separado; sem deploy por consequência desta documentação.

Rollback inicial por tenant: desabilitar recursos novos, parar dispatcher novo e reconciliar partes em dispatching/unknown antes de retomar o antigo. Nunca permitir dois dispatchers enviando a mesma resposta. Reverter código só quando o legado continuar compatível com dados novos; preservar tabelas para auditoria. Downgrade destrutivo apenas após exportação, retenção e confirmação operacional.

## Situação desta entrega documental

- [x] Intenções, histórico, escopo e limites documentados.
- [x] Snapshots históricos de código/testes/SQL com hashes.
- [x] Proposta Python de política de turno, chunking, pacing e invalidação.
- [x] Três drafts SQL para revisão e posterior conversão em Alembic.
- [x] Cenários de aceitação e roteiro de rollout/rollback.
- [ ] Implementação integrada, migrações Alembic e backfill executável.
- [ ] Homologação de presença, áudio, ferramentas, entrega e naturalidade com usuários.


## Compatibilidade após a revisão da PR #1 (05/11/2026)

A cadeia executável da branch agora inclui 0002/0003 e 0004. Os drafts desta pasta
continuam referências da baseline f6d0e2a, não scripts para aplicar. Antes da futura
implementação C01–C16, reconciliar `zapi_instances.agent_id`, `sending_enabled`,
`conversations.opted_out/consent_status/last_incoming_at`, `outbox_messages`,
`llm_configs` múltiplas, `model_runs` e callback_token_encrypted. Não criar colunas
paralelas para os mesmos conceitos. O scheduler e a serialização de envio já foram
implementados na revisão; isso não conclui chunking, memória aprovada ou a integração
Instagram. Consulte docs/consolidacao/2026-11-05-revisao-pr1.md.
