# TODO — produto, implementação e homologação

> **Aviso de atualidade:** checklist legado duplicado em `TODO — produto, implementação e homologação.md`.
> Foi escrito antes das conexões WAME e da intervenção humana por grupo; suas caixas
> não são um retrato confirmado do commit atual. Para estado e riscos atuais, consulte
> [`docs/ai/CURRENT_STATE.md`](docs/ai/CURRENT_STATE.md) e
> [`docs/ai/KNOWN_RISKS.md`](docs/ai/KNOWN_RISKS.md). Preserve este registro até
> reconciliar as pendências de produto com a responsável.

## Implementado no código desta versão

- [x] Base SaaS multi-tenant: empresa/tenant, primeiro administrador da plataforma, administrador da empresa, login seguro e seleção explícita de tenant pelo backend.
- [x] Escopo por tenant nas rotas centrais de empresas, agentes, instâncias, conversas, modelos e documentos; processamento assíncrono carrega `tenant_id` do evento persistido.
- [x] Credenciais de APIs cifradas no servidor; Z-API como único transporte WhatsApp.
- [x] Adaptador Z-API central para enviar texto, consultar estado e configurar callback HTTPS; recebimento minimizado, segredo próprio de callback e deduplicação.
- [x] Registro de eventos/mensagens, outbox persistente, aceite HTTP distinguido de entrega e erros externos sem ecoar corpo de resposta nos logs.
- [x] Provedores Groq/xAI/OpenAI-compatible para texto; embeddings separados; RAG filtrado por tenant e limite de 1536 dimensões.
- [x] Worker Celery + grafo LangGraph, histórico recente, itens internos de memória e janela de agrupamento configurável para mensagens fragmentadas; check de revisão e deduplicação por revisão antes do efeito externo.
- [x] Painel básico para login, empresas, agentes, instâncias, conversas, documentos e configuração do modelo.
- [x] Compose com Caddy/TLS automático, PostgreSQL/pgvector, usuário de aplicação sem superuser, Redis, API e worker; `.env.example`, bootstrap e scripts de backup/restauração.
- [x] Documentos de arquitetura, implantação, segurança/limitações e referências oficiais.

## Testes locais executados

- [x] `pytest -q`: 17 testes unitários passaram; chamadas HTTP para Z-API e IA são simuladas.
- [x] Sintaxe Python, JavaScript e scripts Shell validados.
- [x] Importação de FastAPI e geração OpenAPI local concluídas.
- [ ] Integração com PostgreSQL/pgvector e Redis reais.
- [ ] Renderização/homologação do Compose com Docker (Docker não estava instalado no sandbox).
- [ ] Homologação real com credenciais e instância de sandbox Z-API.
- [ ] Implantação na VPS Hostinger, emissão/renovação TLS e teste de reinício.
- [ ] Backup off-site e restauração integral em ambiente isolado.

## Pendências de produto antes de ampliar piloto/comercializar

### SaaS, LGPD e acesso
- [ ] Testes adversariais cross-tenant completos em todas as rotas, jobs, outbox, memória e checkpoints; avaliar RLS PostgreSQL.
- [ ] Gestão de usuários por empresa, convites, recuperação/rotação de senha, MFA, auditoria e permissões granulares.
- [ ] Consentimento, opt-out, blocklist, retenção/exclusão, portabilidade e evidência de finalidade/processamento conforme LGPD.
- [ ] Planos, medição de uso, limites por tenant, cobrança e provisionamento self-service.

### Conversação e Z-API
- [ ] Validar debounce, ordem de fragmentos, interrupção/obsolescência e concorrência em um teste de integração real.
- [ ] Endpoints/callbacks de estado de entrega, tela de outbox e reconciliação de eventos pendentes no Redis.
- [ ] Rotação/reconfiguração segura de callback sem recriar instância.
- [ ] Recepção e envio real de áudio, imagem, vídeo, documentos e localização; transcrição e voz, todos por Z-API.
- [ ] Controles de frequência por número, janela de envio, alertas de risco e parada operacional.

### Agentes, memória e ferramentas
- [ ] UX para memória individual, curadoria/versionamento de conhecimento, correções humanas e aprendizado aprovado.
- [ ] Ferramentas autorizadas por tenant: Groq Tools/Responses, xAI Agent Tools, MCP remoto, Calendar, CRM/ERP e aprovações humanas; nenhum efeito externo deve ser habilitado sem allowlist e autorização backend.
- [ ] Arquitetura multiagente especializada; hoje há um agente elegível por tenant no fluxo de resposta.
- [ ] Avaliação de RAG, proteção contra prompt injection e testes de proveniência/relevância.

### Operação e qualidade
- [ ] Container build/Compose, SQL de inicialização PostgreSQL, migrations, Caddy ACME e limites de memória validados com Docker/serviços reais.
- [ ] Backup e restauração realmente ensaiados; criptografia e cópia off-site/monitoramento implementados no ambiente operacional.
- [ ] Métricas, alertas, logs de auditoria redigidos, retenção de eventos e procedimentos de incidentes.
- [ ] Teste de carga/concorrência, desconexão de worker/broker e falhas/timeout ambíguo da Z-API.
- [ ] Revisão externa de segurança, LGPD, política Z-API/WhatsApp e termos/retensão dos provedores de IA.

> Não marcar os critérios de aceitação originais como concluídos apenas por haver código. A conexão real, webhook real, envio/recebimento, RAG com endpoint configurado, backup/restauração e VPS precisam de evidência de homologação. O status deste TODO separa implementação local de validação em produção.
