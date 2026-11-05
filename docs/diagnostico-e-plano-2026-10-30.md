# Diagnóstico e plano de execução — 30/10/2026

Status: proposta para validação da arquitetura. Esta auditoria não alterou a aplicação, não aplicou migrações, não fez deploy e não enviou mensagens. Z-API permanece como transporte exclusivo do WhatsApp.

## Evidências verificadas

- Docker Compose: API, PostgreSQL/pgvector e Redis saudáveis; web e worker em execução. Worker respondeu ao ping Celery; `/health` retornou `ok: true`.
- Consulta GET real à Z-API: `connected=true`, `smartphoneConnected=true`.
- Banco: 1 empresa, 2 usuários, 1 instância, 10 conversas, 33 mensagens (32 recebidas e 1 saída aceita), 43 eventos ReceivedCallback processados e 1 outbox aceita.
- Nenhum agente, configuração de IA, documento, chunk ou item de memória cadastrado.
- Aceitação da saída não comprova entrega/leitura. Os eventos persistidos são evidência histórica; a auditoria não realizou um novo teste de ponta a ponta com um contato.
- Banco implantado na migração `0001_initial`; arquivos locais incluem `0002_delivery_controls` e `0003_model_routing`.
- Hashes de routes_zapi.py, tasks.py e models.py diferem entre checkout e API em execução; outbox.py e model_router.py não existem na imagem da API. API e worker usam imagens de IDs diferentes; compatibilidade entre seus contratos ainda precisa de auditoria.
- Há mudanças locais não commitadas. Preservá-las e revisar o diff antes de qualquer implementação.
- 20 testes unitários passaram sobre o checkout, usando imagem Python existente, dependências locais, rede desativada e mounts somente leitura. Isso não comprova integração real de IA, RAG, ferramentas nem migrações.
- Nenhuma tabela com RLS habilitada no schema consultado. Existe escopo por tenant na aplicação, mas falta defesa adicional no banco e teste abrangente contra acesso cruzado.
- Sem crontab do usuário orquestra; não foi comprovado backup automático externo ou restauração recente. Outros agendadores do host não foram auditados.

## Estado funcional

| Área | Estado observado | Trabalho necessário |
|---|---|---|
| Infraestrutura | Stack executando | Readiness, release reproduzível, backup externo, alertas, teste de restauração e TLS público |
| Autenticação | Argon2/JWT e perfis básicos | Gestão completa de usuários, sessões revogáveis, recuperação de acesso e matriz de permissões |
| Painel | HTML/CSS/JS integrado à API | Completar operação, formulários de vínculos/políticas, indicadores reais, ferramentas, auditoria e curadoria |
| Z-API texto | Adaptador central, webhook e histórico | Homologação ponta a ponta, ciclo completo de conexão e gestão segura de credenciais |
| Status/conexão | Processadores novos no checkout | Revisar contrato, configurar callbacks remotos, correlacionar eventos e homologar |
| Filas e proteção | Outbox/políticas novas no checkout | Testar concorrência, rate limit, interrupção, retentativas e recuperação; iniciar Beat |
| IA | Cliente textual e grafo simples; fallback novo local | Configuração real, adaptadores por capacidade, ferramentas, orçamento e avaliação |
| Memória | Histórico e estrutura MemoryItem | Identidade estável, extração, edição, proveniência, expiração, consentimento e exclusão |
| RAG | Extração PDF/Word/Excel e pgvector no código | Ingestão assíncrona, OCR, versões, fontes, relevância, isolamento e avaliação real |
| Áudio e mídia | Tipos reconhecidos como marcadores | Preservar metadados úteis, download seguro, armazenamento privado, STT/TTS e envio Z-API |
| Aprendizado | Sem workflow completo | Propostas, aprovação humana, publicação versionada, regressão e rollback |
| Calendar/comercial | Ausentes | OAuth, ações idempotentes, catálogo, regras e orçamentos determinísticos |
| Multiagentes | Cadastro previsto; grafo de resposta com um nó | Roteador, especialistas, limites e contexto unificado |

## Arquitetura recomendada

Manter monólito modular Python 3.12/FastAPI, SQLAlchemy e Alembic. PostgreSQL/pgvector será a fonte de verdade; Redis/Celery para trabalho assíncrono e locks, com Celery Beat separado. LangGraph coordenará contexto, recuperação, ferramentas, especialistas e supervisão humana. Caddy já atende proxy/TLS; manter evita migração sem benefício demonstrado.

Fluxo: WhatsApp → Z-API → webhook HTTPS → inbox transacional PostgreSQL → workers → identificação/consentimento → agrupamento de fragmentos → memória/RAG → roteamento de modelo e ferramentas → política determinística → outbox → Z-API → callbacks de envio/status.

O painel acessa apenas a API própria. Ações do modelo passam por registro de ferramentas, escopo por empresa, validação de argumentos e autorização. Conteúdo de documentos e mensagens é dado não confiável; não pode modificar permissões ou regras críticas.

Manter inicialmente o frontend existente; evoluir por módulos com TypeScript, testes de navegador e componentes acessíveis. Adoção de React é uma decisão opcional baseada na complexidade da central de conversas, não condição para o backend funcionar. Compilação poderá ocorrer em CI; produção deve ser totalmente auto-hospedada.

## Projetos open source e decisão

Avaliação qualitativa de adequação, sem benchmark comparativo executado. Versões, licenças transitivas e avisos devem ser registrados por release.

| Projeto | Licença observada | Decisão e custo operacional |
|---|---|---|
| [LangGraph](https://github.com/langchain-ai/langgraph) | MIT | Manter: execução com estado, checkpoints e intervenção humana; já integra a stack |
| [LangChain](https://github.com/langchain-ai/langchain) | MIT | Usar integrações pontuais; evitar duplicar a camada de domínio |
| [LlamaIndex](https://github.com/run-llama/llama_index) | MIT | Avaliar conectores/parsers quando superarem a ingestão atual; README sinaliza foco atual em parsing e extração |
| [CrewAI](https://github.com/crewAIInc/crewAI) | MIT | Alternativa para equipes de agentes; não adicionar outro orquestrador agora; medir chamadas e latência antes de adoção |
| [AutoGen](https://github.com/microsoft/autogen) | MIT para código; CC-BY-4.0 para documentação | Não selecionar para produção nova: repositório anuncia transição para arquivamento e recomenda avaliar Microsoft Agent Framework |
| [Letta](https://github.com/letta-ai/letta) | Apache-2.0 | Referência para memória; projeto aponta fonte ativa em letta-code e servidor V1 aposentado; não adicionar runtime sem avaliação |
| [Mem0](https://github.com/mem0ai/mem0) | Apache-2.0 | Prova de conceito opcional: comparar qualidade, custo de extração, exclusão e isolamento com memória própria em PostgreSQL |
| [Haystack](https://github.com/deepset-ai/haystack) | Apache-2.0 | Alternativa de pipelines RAG; manter uma única orquestração para reduzir operação |

Os projetos têm ecossistemas estabelecidos, mas atividade e compatibilidade devem ser avaliadas no commit selecionado. Não há fundamento para prometer qual será mais rápido ou barato sem corpus e carga reais. A principal despesa variável será inferência, embeddings, voz e armazenamento, não apenas o framework.

## Banco e isolamento

Preservar tenants, users, agents, zapi_instances, llm_configs, conversations, messages, webhook_events, knowledge_documents, knowledge_chunks, memory_items e outbox_messages. Revisar migrações locais e incluir model_runs após validação.

Adicionar gradualmente:

- Identidade: contacts e contact_identifiers, com vínculo verificável entre telefone e LID, sem fundir contatos por similaridade.
- Mídia: message_attachments, processing_jobs e metadados de retenção.
- Memória: conversation_summaries, memory_versions e evidências das fontes.
- Conhecimento: knowledge_sources, document_versions, ingestion_jobs e escopo de acesso por agente.
- Aprendizado: learning_proposals, reviews, evaluations e publicação/rollback.
- Operação: consent_events, suppression_entries, audit_events e delivery_events.
- Ferramentas: tool_definitions, tool_connections, tool_executions, calendar_connections e appointments.
- Comercial: products, price_lists, price_rules, quotes e quote_items, com valores monetários decimais e regras versionadas.
- Acesso: memberships, roles, permissions e sessões revogáveis.

Toda entidade empresarial leva tenant_id. Usar constraints que impeçam referências cruzadas, índices compostos, RLS com usuário de runtime sem bypass e contexto transacional seguro. Separar usuário de migração do usuário de aplicação. Testar reutilização de conexões do pool para impedir vazamento de contexto.

Embeddings atuais têm dimensão fixa 1536. Registrar modelo, dimensão e versão do índice; mudar o modelo exige reindexação controlada e impede misturar espaços vetoriais incompatíveis, mesmo com igual dimensão.

## Memória, RAG e aprendizado

Memória individual combina histórico, resumo incremental e fatos estruturados, com fonte, data, confiança, validade e possibilidade de correção/exclusão. Contexto recuperado sempre restrito à empresa e contato autorizados.

Memória coletiva significa conhecimento empresarial curado dentro de uma empresa. Nunca compartilhar dados de clientes entre empresas. Antes de publicação: remover dados pessoais desnecessários, verificar origem e conflitos, obter aprovação e executar avaliação de regressão.

Pipeline RAG: upload/URL autorizada → validação → extração/OCR quando necessário → chunks com página/planilha → embeddings → busca textual e vetorial → reranking opcional → resposta fundamentada. Ausência de evidência deve gerar esclarecimento ou encaminhamento humano. Preços e disponibilidade devem vir de ferramentas estruturadas com dados atuais.

Aprendizado: feedback → proposta → revisão → versão aprovada → testes → publicação → monitoramento → rollback. Não alterar automaticamente regras críticas nem tratar respostas anteriores do modelo como fonte oficial.

## Contrato Z-API

Fontes oficiais: [índice](https://developer.z-api.io/llms.txt), [Client-Token](https://developer.z-api.io/security/client-token), [texto](https://developer.z-api.io/message/send-text), [recebimento](https://developer.z-api.io/webhooks/on-message-received), [delivery](https://developer.z-api.io/webhooks/on-message-send), [status de mensagem](https://developer.z-api.io/webhooks/on-whatsapp-message-status-changes), [todos os webhooks](https://developer.z-api.io/webhooks/update-every-webhooks), [status da instância](https://developer.z-api.io/instance/status).

O adaptador atual usa ID/token na URL e Client-Token no header. Remover segredos de URLs em erros, traces e logs. Client-Token de chamadas à API não deve ser presumido como assinatura de webhook. O segredo de callback atual é um controle próprio da aplicação; completar proteção com rotação, limites, validação de instância e verificação dos mecanismos documentados disponíveis.

Métodos conferidos para expansão de callbacks: PUT update-every-webhooks e PUT update-webhook-message-status, com objeto contendo value. O código atual configura apenas recebimento. O contrato vigente distingue aceitação na fila, delivery e status; não apresentar accepted como delivered.

Antes de codificar cada endpoint de mídia/conexão: conferir método, URL, campos, limites, resposta e erros na página oficial e criar teste de contrato. Fazer inventário integral do índice e matriz de recursos usados; a consulta desta auditoria não equivale a declarar lidas e homologadas as 250 páginas.

Downloads devem preservar os campos de mídia necessários, respeitar expiração e aplicar limites de tamanho/duração, validação de MIME, bloqueio de redes privadas e controle de redirects. Áudio: evento Z-API → download seguro → STT → agente → texto ou TTS → envio Z-API. Localização exige coordenadas estruturadas, não apenas legenda.

Outbox com idempotência local e correlação por IDs; timeout após envio pode ter efeito remoto desconhecido. Não reenviar cegamente; reconciliar ou encaminhar para revisão. Não prometer exactly-once do provedor sem contrato que o assegure.

Opt-out, consentimento documentado, limites por empresa/instância/contato, pausa humana, circuit breaker e auditoria devem operar fora do controle do modelo. A janela de 24 horas presente no código é uma política interna, não prova de exigência ou garantia aplicável à Z-API.

## Provedores de IA

Interface por capacidades: chat, streaming opcional, saída estruturada, ferramentas, embeddings, STT e TTS. Validar adaptadores Gemini, DeepSeek, OpenAI, Anthropic e endpoints de modelos abertos; compatibilidade textual não comprova suporte a ferramentas. Preservar Groq/xAI existentes quando configurados.

Modelo principal, auxiliares e contingência por agente/tarefa, mantendo o mesmo snapshot de contexto nas tentativas. Separar credenciais de chat, embeddings e voz. Falha de autenticação/quota dispara fallback elegível e alerta; nenhuma ferramenta com efeito externo pode ser repetida apenas por troca de modelo. Definir orçamento por empresa e avaliação com conversas em português antes de selecionar modelo econômico. Gratuidade não deve ser requisito operacional da produção.

## Implantação na VPS

Manter Docker Compose com db, redis, api, worker e web; acrescentar beat, tarefas de backup e monitoramento leve. Modelos externos no início. Dimensionamento depende de teste de carga; limites no Compose não comprovam capacidade real.

Separar staging e produção; CI executa testes unitários, integração PostgreSQL/Redis, migrações desde o schema realmente implantado, frontend e checagem de segredos/dependências. Gerar imagem imutável por commit e usar a mesma release em API/worker/beat. Backup antes de migração e rollback compatível com schema, sem excluir volumes.

Validar DNS/TLS externamente, firewall, persistência após reboot, readiness e limites de recursos. Backups cifrados de PostgreSQL e anexos, cópia externa e chaves separadas; programar restauração em ambiente isolado. Proposta inicial a validar: RPO de 24 horas e RTO de 4 horas.

## Plano e cronograma estimado

Referência de esforço: um desenvolvedor sênior em dedicação integral com apoio de QA/infra. Faixas estimadas, não compromisso de data. Dependem da revisão das mudanças locais, corpus, volume e acesso aos provedores. Reservar 20–30% para homologação e ajustes.

| Fase | Duração base | Entregas e critério de passagem |
|---|---|---|
| 1 — Base e estabilização | 1–2 semanas | Revisar diff; release/migrações reproduzíveis; API/worker alinhados; Beat; usuários e isolamento; backup/restauração. Aceite: staging sobe do zero e migra cópia do schema atual sem perda; testes de tenant e rollback passam |
| 2 — Z-API completa | 2–3 semanas | Conexão, credenciais, webhooks, texto/mídia/localização, histórico, outbox, status e controles. Aceite: duas instâncias reais, contato autorizado, recepção/saída/entrega, duplicação, desconexão e falhas testadas |
| 3 — IA, memória e RAG | 3–4 semanas | Adaptadores, fallback, fragmentos, STT/TTS, memória curada e ingestão com fontes. Aceite: conversa posterior recupera fatos, consulta documentos corretos, trata ausência de fonte e não vaza dados |
| 4 — Aprendizado validado | 1–2 semanas | Propostas, revisão, versões, avaliação e rollback. Aceite: correção só entra na base após aprovação e permanece rastreável |
| 5 — Ferramentas e especialistas | 2–3 semanas | Calendar real, catálogo, descontos, orçamentos, registro de ferramentas e roteamento por especialista. Aceite: agendar/reagendar/cancelar sem duplicação e orçamento respeitando regras |
| 6 — Homologação e operação | 2–3 semanas | Segurança/LGPD, carga, métricas, alertas, manuais, recuperação e piloto. Aceite: matriz dos 12 critérios comprovada e restauração funcional |

Total base: 11–17 semanas; com reserva de 20–30%, aproximadamente 14–22 semanas. Backend, painel, migrações, testes e manual integram cada fase; segurança básica começa na fase 1. Não passar ao próximo estágio sem o aceite crítico do anterior.

## Aceite final e dependências

Registrar evidências para cada requisito: conexão real; webhook real; envio e confirmação; contatos telefone/LID; histórico após reinício; memória em nova conversa; RAG com fonte; IA real e fallback; ferramenta externa real; duas instâncias isoladas; credenciais protegidas e acesso negado entre empresas; VPS com TLS, recuperação e backup restaurado.

Para homologação: domínio/DNS, segunda instância Z-API, contatos de teste autorizados, chaves de IA/embeddings/voz, conta Google de teste e documentos/tabelas representativos. Configurar segredos por canal seguro, sem colocá-los neste documento ou no repositório. Volume esperado, horários de operação e responsáveis pela aprovação do conhecimento ainda precisam ser definidos antes do dimensionamento e dos objetivos de qualidade.

A próxima ação proposta é validar esta arquitetura e então executar a fase 1. A documentação anterior registra intenção de implementação; isso não substitui a validação solicitada pelo usuário nesta revisão.
