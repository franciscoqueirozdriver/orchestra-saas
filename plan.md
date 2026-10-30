# Plano de produto e arquitetura — Orquestra

**Nome de trabalho. Estado:** MVP alfa implementado localmente; ainda sem deploy/homologação real. A proposta e a pesquisa comparativa anteriores estão em [`docs/architecture-proposal.md`](docs/architecture-proposal.md).

## Objetivo e premissas

Construir um SaaS multiempresa de agentes conversacionais via WhatsApp, com memória/contexto, base empresarial, intervenção humana e futuras ferramentas. **Z-API é a única integração autorizada para envio e recebimento de WhatsApp.** Outros serviços podem processar IA, documentos ou voz, mas não substituir o transporte Z-API.

O código desta entrega é uma base operacional, não uma declaração de que todos os critérios de produto estão concluídos. Nenhuma credencial real foi incluída e nenhuma instância Z-API, VPS ou provedor de IA foi homologado.

## Arquitetura atual

| Camada | Escolha | Função e limite atual |
|---|---|---|
| Painel | HTML/CSS/JavaScript estático | Painel autenticado, sem build Node no runtime; navegação e chamadas à API same-origin. |
| API | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic Settings | Autenticação, tenant context, cadastro, operação e integrações. |
| Banco | PostgreSQL 16 + pgvector | Fonte durável; usuário de runtime sem superuser. Vetores com 1536 dimensões. |
| Fila | Redis 7 + Celery | Webhooks e resposta assíncrona; eventos permanecem no PostgreSQL. |
| Orquestração | LangGraph + `PostgresSaver` | Grafo textual inicial/checkpoint por tenant e conversa; não é ainda arquitetura de múltiplos agentes. |
| WhatsApp | Adaptador próprio Z-API | Callback recebido, status de instância, atualização de webhook e envio de texto. Mídia fica como marcador não processado. |
| IA | Groq Chat Completions, xAI Responses e endpoint OpenAI-compatible | Texto apenas nesta versão. Tools, MCP e ações externas estão desabilitados/não implementados. Embeddings configuráveis separadamente. |
| Entrada web/TLS | Caddy 2 | SPA, proxy interno, ACME/TLS e cabeçalhos; API, banco e Redis sem portas expostas. |
| Implantação | Docker Compose em VPS única | KVM 2 informado: 2 vCPU, 8 GB RAM e 100 GB NVMe. Limites de containers próximos a 5,2 GiB antes de overhead. |

## Modelo SaaS inicial

Entidades principais: `Tenant`, `User`, `Agent`, `ZapiInstance`, `LLMConfig`, `Conversation`, `Message`, `WebhookEvent`, `KnowledgeDocument`, `KnowledgeChunk`, `MemoryItem` e `OutboxMessage`. Os registros de domínio levam `tenant_id`, e rotas/tarefas filtram pela empresa. Um administrador da plataforma provisiona empresas; o tenant do usuário comum vem do token/sessão e não de um `tenant_id` arbitrário enviado pelo cliente. Administrador de plataforma precisa selecionar empresa ativa para operar.

A separação é implementada em consultas e dependências da aplicação; esta versão **não** usa PostgreSQL RLS. Exige suíte de testes adversariais cross-tenant e avaliação de RLS antes de dados de alta sensibilidade. Cobrança, limites de plano, convites e autoinscrição não estão implementados.

## Fluxo conversacional atual

1. A Z-API chama endpoint HTTPS contendo segredo próprio; segredo é armazenado como hash e evento é validado, minimizado e deduplicado.
2. O webhook é persistido no PostgreSQL e enfileirado no Redis/Celery. O worker grava mensagem e incrementa a revisão da conversa.
3. A resposta é postergada por janela curta configurável (3 s padrão); mensagens fragmentadas que chegam durante a janela invalidam tarefas antigas. Há lock por conversa, outbox persistente e chave única por revisão.
4. Se agente com `auto_reply_enabled`, instância e modelo estiverem configurados, um grafo LangGraph usa histórico recente, contexto de memória registrado e trechos do RAG escopados ao tenant.
5. Antes do efeito externo, revisão, agente, configuração IA e instância são conferidos de novo. A resposta é enviada exclusivamente por Z-API e o status registrado como aceite da API — não confirmação de entrega.

Respostas automáticas iniciam desativadas. O modelo não executa ferramentas. Conteúdo de documentos/mensagens é tratado como dado não confiável, mas guardrails não substituem autorização e políticas operacionais.

## Estratégia de memória, conhecimento e aprendizado

- **Histórico recente:** persistido por conversa; o grafo utiliza as mensagens mais recentes para continuidade.
- **Memória individual:** existe armazenamento interno vinculado a tenant/contato e leitura contextual; faltam telas, CRUD, consentimento/retention e aprovação da equipe.
- **RAG empresarial:** ingestão de documentos pelo painel, chunking/embeddings e busca vetorial com filtro tenant/modelo. Conteúdo recuperado é apresentado como dado, com proveniência do documento.
- **Aprendizado contínuo:** não ativo. Próxima fase deve registrar correções como propostas versionadas, com revisão humana antes de publicação; o agente nunca deve mudar sozinho regra comercial crítica.

## Integração Z-API

Toda comunicação WhatsApp é centralizada em `backend/app/zapi_client.py`; modelos e rotas não constroem chamadas diretas a outros provedores WhatsApp. A versão usa os contratos oficiais documentados para `send-text`, `status` e `update-webhook-received`. O webhook suporta persistência de evento e texto, classificação de mídia para marcador e deduplicação; não baixa arquivos nem trata callbacks de entrega. Fontes e payloads estão em [`docs/providers-and-hosting.md`](docs/providers-and-hosting.md).

## Segurança e operação

- Argon2 + JWT curto; limite de login distribuído Redis.
- Chaves de APIs cifradas Fernet no servidor. Perda da chave mestra impede decifrar registros já gravados.
- Usuário DB da API sem superuser; segredos de superuser não são passados aos containers API/worker.
- Callback por token próprio, schema JSON, tamanho limitado, minimização/sem URL de mídia gravada e idempotência.
- Validadores de URL impedem esquemas HTTP, portas customizadas, hosts locais/reservados e resolução DNS não pública em destinos de IA.
- CSP/TLS Caddy, acesso/logs minimizados e limites Docker/filas conservadores.
- Backup encrypted local com script e retenção; cópia off-site e restauração real continuam responsabilidade do operador até serem automatizadas/testadas.

Consentimento/opt-out, bloqueio, limites de envio WhatsApp, retenção e exclusão LGPD, auditoria completa, RLS, alertas e resposta a incidentes ainda são pendências de produto.

## Design do painel

**Movimento:** painel operacional editorial, combinando navegação compacta com espaço amplo de trabalho.

**Princípios:** leitura rápida; estado operacional evidente; privacidade visível por tenant; estado de envio não afirma entrega sem confirmação; credenciais sempre mascaradas.

**Paleta/layout:** navegação em marinho profundo, fundos claros quentes, verde-azulado para estado seguro e âmbar/vermelho para alertas; sidebar compacta, cabeçalho contextual, tabelas e painel de conversa dividido.

**Voz:** direta e calma. Exemplos: “A instância está conectada.” “A resposta automática permanece desligada até você habilitá-la.” Marca tipográfica “Orquestra” é provisória/configurável.

## Fases e gates seguintes

1. **Base e instalação:** já existe código; gate é executar Compose em Ubuntu, migrações, bootstrap e TLS real.
2. **Z-API texto:** homologar instância, status, callback, deduplicação, envio, respostas automáticas desativadas/ativadas e falhas de rede.
3. **RAG e memória:** testar provedores/modelos de embeddings, privacidade, relevância e curadoria de memória entre contatos/tenants.
4. **Proteção operacional:** implementar consentimento, opt-out, blocklist, rate limit de envio, alertas e retenção antes de expandir piloto.
5. **Ferramentas:** desenhar registry/allowlist por tenant, integração MCP/Groq/xAI, aprovações humanas, políticas de argumentos e sandbox; iniciar somente com ações de leitura.
6. **Multimídia e canais suportados:** transcrição e envio/recebimento de mídia, sempre sob Z-API, com testes oficiais específicos.
7. **SaaS comercial e escala:** billing, observabilidade, backup off-site, RLS opcional, testes de carga, redundância e revisão externa de segurança/LGPD.

Não avançar para efeitos externos ou lançamento comercial sem gates e evidência de homologação. O detalhamento dos itens pendentes está em [`TODO.md`](TODO.md).
