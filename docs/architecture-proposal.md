# Proposta técnica consolidada — plataforma multiempresa de agentes via WhatsApp

**Data da proposta:** 29/10/2026  
**Status:** arquitetura para validação do usuário; não implementada e não homologada com credenciais ou instância Z-API reais.

> **Nota de continuidade (09/11/2026):** este documento é uma proposta histórica,
> não descreve o transporte atual. A afirmação abaixo de exclusividade da Z-API foi
> superada: o código no commit `40272d0` contém adaptadores Z-API e WAME. Consulte
> [`docs/ai/CURRENT_STATE.md`](ai/CURRENT_STATE.md) para o estado do checkout e
> [`docs/ai/DECISIONS.md`](ai/DECISIONS.md) para a precedência documental.

## 1. Objetivo, escopo e premissas

Esta proposta descreve uma plataforma SaaS multiempresa para atendimento conversacional com agentes de IA, memória, recuperação de conhecimento, ferramentas e eventual intervenção humana. A **Z-API permanece o transporte exclusivo de WhatsApp**: toda entrada e saída WhatsApp passa pelo adaptador Z-API do backend. Não se propõe outra API, canal ou provedor de WhatsApp.

O documento usa três qualificadores:

- **FATO**: informação sustentada pelas fontes listadas em `References`.
- **RECOMENDAÇÃO**: decisão arquitetural proposta, ainda sujeita a validação.
- **VALIDAR**: ponto que a documentação consultada não resolveu e que exige teste, confirmação contratual ou decisão do usuário.

A pesquisa fornecida é documental. Não houve chamada real à Z-API, uso de credenciais, teste de webhook, teste de mídia, medição de desempenho, teste de restauração ou verificação de um plano específico da Hostinger. Portanto, nenhum fluxo abaixo deve ser interpretado como integração já disponível.

## 2. Resumo executivo e decisão recomendada

**RECOMENDAÇÃO — avançar para uma prova de conceito controlada com LangGraph como runtime primário de orquestração**, mantendo o provedor de modelo, a persistência, a fila, o armazenamento vetorial, o armazenamento de mídia e a hospedagem desacoplados. LangGraph documenta grafos com etapas determinísticas e agentivas, persistência por checkpoints, execução durável, streaming e human-in-the-loop; também pode ser utilizado sem os demais produtos LangChain [1] [3].

A arquitetura não deve tratar LangGraph, LangChain, LlamaIndex, CrewAI, AutoGen, Letta, Mem0, Haystack, PydanticAI ou Agno como uma plataforma multi-tenant pronta. As fontes caracterizam esses projetos como bibliotecas, runtimes ou componentes de aplicação; o isolamento entre empresas, a API de WhatsApp, filas, autorização, retenção, observabilidade, backup e operação continuam sendo responsabilidades da aplicação, salvo componentes específicos que sejam adicionados e configurados pelo projeto [1] [3] [4] [28] [35] [43] [45] [48].

A decisão inicial proposta é:

1. **Orquestração:** LangGraph, com estado tipado, nós determinísticos, nós de LLM, ferramentas allowlisted, checkpoints persistentes e pontos explícitos de aprovação/handoff.
2. **Integrações de modelos e componentes:** LangChain somente quando uma integração realmente reduzir trabalho e permanecer substituível; não acoplar regras de tenancy ou autorização ao agente [4].
3. **Persistência operacional:** banco relacional durável, com checkpointer persistente compatível com a opção documentada `PostgresSaver`; o tipo, plano e configuração concretos do banco ainda devem ser confirmados [2].
4. **RAG e memória:** serviço de recuperação/memória separado, com filtro obrigatório por `tenant_id` e controles próprios de ciclo de vida. Um armazenamento vetorial específico ainda não é selecionado; a seleção deve ocorrer no PoC a partir de isolamento, retenção, custo e restauração.
5. **Mensageria:** adaptador server-side exclusivo para Z-API, com fila/outbox próprios, idempotência e reconciliação de estados.
6. **Mídia:** armazenamento de objetos privado e temporário, separado do banco, com validação de URL, tipo e tamanho antes de qualquer download ou processamento. O fornecedor informa disponibilidade de mídia recebida por 30 dias; não se deve depender dessa janela como armazenamento permanente [12].
7. **Implantação inicial:** Docker Compose em VPS Hostinger para protótipo ou baixo volume, condicionado a dimensionamento e operação próprios. Uma única VPS será considerada ponto único de falha, não alta disponibilidade [18] [19] [20] [21].

**Conclusão executiva:** a proposta é tecnicamente plausível para validação, mas os critérios de aprovação são isolamento cross-tenant demonstrável, homologação real da Z-API, recuperação testada, governança de dados e operação segura. A arquitetura abaixo é uma proposta para validação do usuário, **não o início de implementação**.

## 3. Arquitetura recomendada

### 3.1 Camadas

A solução deve ser dividida nas seguintes fronteiras:

- **Gateway de entrada e administração:** autenticação de usuários da plataforma, APIs de tenants, instâncias, contatos, documentos, políticas e auditoria. O tenant deve ser derivado de uma identidade ou vínculo confiável no servidor; não do corpo enviado pelo usuário ou pelo modelo.
- **Ingress de webhooks Z-API:** endpoint HTTPS público, com parsing, validação de schema e tamanho, resolução de `instanceId` para tenant no cadastro interno e persistência mínima do evento antes do processamento. A Z-API documenta configuração de webhook por URL HTTPS, mas as páginas examinadas não documentam assinatura criptográfica, HMAC, desafio ou autenticação de origem [12] [13].
- **Fila e event store:** componente durável para desacoplar a recepção do processamento do agente. A escolha concreta da tecnologia é uma decisão de implementação posterior; o requisito é que o evento bruto necessário, sua chave de deduplicação e seu estado sejam recuperáveis.
- **Workers de conversa:** carregam o contexto autorizado, recuperam histórico/memória/RAG do tenant, executam o grafo LangGraph e registram efeitos externos como intenções de saída, não como efeitos implícitos do LLM.
- **Runtime LangGraph:** nós determinísticos para autorização, classificação, política, recuperação e entrega; nós conduzidos por LLM somente onde a flexibilidade for necessária; ferramentas estreitas e tenant-scoped; pontos de aprovação humana para ações sensíveis. A combinação de lógica determinística com decisões de LLM e human-in-the-loop é compatível com o escopo documentado do framework [1].
- **Outbox e adaptador Z-API:** toda mensagem de saída deve nascer como registro de intenção idempotente. O adaptador converte somente para operações documentadas da Z-API e grava os identificadores retornados.
- **Persistência e retenção:** banco relacional para entidades, eventos, estado, outbox e auditoria; armazenamento vetorial para chunks/embeddings com metadados e filtros tenant-aware; storage privado para mídia; cofre ou configuração protegida para segredos.
- **Observabilidade:** métricas, logs estruturados e traces com correlação, redaction de segredos e minimização de conteúdo pessoal. O produto de observabilidade não está selecionado nesta proposta.

### 3.2 Fluxo de mensagem recebida

1. A instância Z-API envia callback ao endpoint HTTPS configurado.
2. O ingress verifica método, tamanho, JSON, campos mínimos e formato esperado para o tipo recebido. O payload é tratado como entrada não confiável.
3. O servidor resolve `instanceId` — e, quando necessário, o contato — no cadastro próprio. O corpo recebido nunca escolhe livremente o `tenant_id`.
4. O evento é salvo com tenant, instância, identificadores disponíveis, tipo, momento, hash ou chave de deduplicação e payload minimizado. O endpoint responde rapidamente conforme a política homologada; não se deve pressupor timeout, retry ou código de confirmação sem testar a Z-API.
5. Um worker retira o evento da fila. A deduplicação impede que o mesmo evento cause múltiplas respostas. A ordenação deve ser aplicada por conversa quando o caso de uso exigir, sem assumir que a Z-API garanta ordem.
6. O worker monta o contexto permitido: histórico necessário, memórias individuais ou coletivas autorizadas, documentos do tenant e políticas vigentes. Mensagens, anexos, transcrições e resultados recuperados são conteúdo não confiável para fins de instrução.
7. O LangGraph executa o fluxo. O grafo pode interromper para handoff humano, solicitar dados, recusar uma ação não autorizada ou produzir uma mensagem de saída.
8. A resposta é validada por regras determinísticas, registrada na outbox e enviada pelo adaptador Z-API. O envio de texto documentado usa `POST /instances/{instanceId}/token/{token}/send-text`, com `phone` e `message`; a resposta de sucesso documentada contém identificadores como `zaapId`, `messageId` e `id` [9].
9. Imagens e áudios somente são enviados quando o tipo, origem, tamanho e política estiverem homologados. A documentação consultada descreve `POST /send-image` e `POST /send-audio`, com URL ou Base64 em seus respectivos campos; os limites e formatos concretos permanecem itens de validação [10] [11].
10. Callbacks posteriores de envio/delivery e status atualizam a mensagem por identificador, sem reexecutar o grafo. A Z-API distingue envio, delivery e status; estados documentados incluem `SENT`, `RECEIVED`, `READ`, `READ_BY_ME` e `PLAYED` [7] [14].

### 3.3 Fluxo de mensagens enviadas e falhas

A resposta HTTP inicial da Z-API não deve ser tratada como confirmação de entrega ou leitura. A documentação descreve enfileiramento e callbacks posteriores [7]. A outbox deve manter estados internos distintos, por exemplo: `created`, `dispatching`, `accepted`, `delivery_pending`, `delivered`, `read`, `failed`, `dead_letter` e `cancelled`. Esses nomes são proposta de domínio, não estados oficiais da Z-API.

Retentativas devem ser limitadas, com backoff, chave idempotente e distinção entre erro transitório e erro definitivo. Como a documentação fornecida não apresenta catálogo exaustivo de erros, política geral de retry ou garantia de ordenação, esses comportamentos precisam ser homologados com uma instância real [7] [9] [12].

### 3.4 Mídia e identificadores

A Z-API documenta callbacks para tipos como texto, imagem, áudio, vídeo, documento, contato e outros; os exemplos incluem campos específicos por mídia [13]. URLs de mídia recebida ficam disponíveis no armazenamento da Z-API por 30 dias [12] [13].

**RECOMENDAÇÃO:** baixar somente mídia necessária, depois de validar esquema, MIME, tamanho, URL e tenant. O fetcher deve usar allowlist de destinos ou outra política contra SSRF; não acessar redes internas, endpoints administrativos ou destinos arbitrários. Guardar o arquivo em storage privado com expiração própria e não registrar Base64 ou conteúdo bruto em logs.

O telefone não deve ser tratado automaticamente como identificador imutável: a documentação Z-API descreve a possibilidade de `phone` ser número ou identificador `@lid`, recomenda `chatLid` como mais estável em determinados cenários e informa que não é possível converter LID em número de telefone [17]. O modelo de dados deve preservar identificadores originais, tipo de identificador e vínculo com a instância, sem usar somente o número como chave global.

### 3.5 UX conversacional, agregação e transparência

A auditoria dos repositórios abaixo fornece padrões de interação que podem orientar uma reimplementação própria. Eles não alteram a decisão de usar **Z-API como transporte exclusivo**, não comprovam comportamento da Z-API e não significam que qualquer código ou ponte de transporte será reutilizado.

- **RECOMENDAÇÃO — agrupar mensagens fragmentadas:** manter um buffer por conversa, reiniciar uma janela configurável de silêncio a cada mensagem, impor um limite máximo de espera e preservar ordem e conteúdo antes de iniciar uma geração. O padrão de batching temporizado foi documentado e testado em um dos projetos auditados [65] [66] [67] e a coalescência antes da geração aparece em outro [83]. A implementação proposta deve operar sobre eventos persistidos recebidos pelos webhooks Z-API, com deduplicação e serialização por conversa; a janela e o limite são decisões do produto.
- **RECOMENDAÇÃO — invalidar geração obsoleta de forma controlada:** associar cada execução a uma revisão/versão da conversa. Nova entrada que altere o contexto deve marcar a execução antiga como obsoleta; cancelar somente quando houver mecanismo seguro, manter mensagens não atendidas na fila e impedir que uma resposta antiga seja enviada depois de uma resposta mais nova. O material auditado demonstra cancelamento e re-enfileiramento em um SDK, mas não comprova garantias transacionais distribuídas [67] [68]. Portanto, a política, a implementação e os testes de corrida permanecem próprios desta proposta.
- **RECOMENDAÇÃO — respostas concisas e previsíveis:** preferir respostas curtas, com uma ideia principal por envio; quando uma resposta precisar ser dividida, usar segmentação limitada, prefixo e intervalo configuráveis, mantendo ordenação, idempotência, tratamento de falha parcial e limites de envio na outbox Z-API. A divisão em bolhas e o teste de prefixo foram observados em material auditado [83] [84]; isso é uma decisão de UX, não uma garantia do canal.
- **RECOMENDAÇÃO — personalidade transparente:** tornar persona, tom, limites e capacidade legíveis e auditáveis, informando que o interlocutor conversa com uma IA quando isso for relevante. Não adotar instruções para ocultar a natureza artificial ou convencer alguém de que o agente é humano, observadas na persona Ava [62] [98]. Persona não concede autorização para escolher tenant, ferramenta, destinatário ou política.
- **RECOMENDAÇÃO — memória com escopo e ciclo de vida:** separar memória de contato, conversa, conhecimento do tenant e regras globais; registrar origem, finalidade, confiança, sensibilidade, validade e expiração; oferecer revisão, correção e exclusão e propagar a decisão para vetores, caches, traces, checkpoints e backups sob controle da plataforma. Os projetos auditados demonstram extração, recuperação e poda simples, mas não governança empresarial completa [60] [69] [85] [99].
- **RECOMENDAÇÃO — participação seletiva:** antes de chamar o LLM, aplicar allowlist, opt-in ou prefixo quando exigido, menção/citação em grupos, horários silenciosos, cooldown, limites, opt-out persistente e handoff humano. Esses mecanismos aparecem como padrões em material auditado [70] [87] [93]; a política final deve ser definida para os eventos e metadados efetivamente fornecidos pela Z-API.
- **VALIDAR:** confirmar em instância real quais identificadores, menções, citações, grupos, callbacks, timestamps e estados estão disponíveis na Z-API para implementar essas políticas. Não presumir ordem, entrega, retry, cancelamento nativo ou suporte a qualquer metadado sem homologação.

## 4. Stack selecionada e justificativa

### 4.1 Componentes escolhidos para o PoC

**Runtime de orquestração — LangGraph.** É o componente principal escolhido porque sua documentação cobre grafos stateful e long-running, combinação de etapas determinísticas e agentivas, checkpoints, execução durável e intervenção humana [1] [2]. O repositório indica licença MIT [6] e a pesquisa fornecida observou atividade recente na branch principal até 12/10/2026; isso é evidência de manutenção, não SLA, compatibilidade futura ou suporte garantido [5].

**Integrações — LangChain, de modo opcional.** LangChain oferece interfaces e integrações para modelos, embeddings, ferramentas, vetores e retrievers; a própria documentação orienta LangGraph para orquestração mais customizada [4]. A proposta não deixa LangChain controlar tenancy, autorização ou efeitos externos. A licença MIT do repositório foi identificada [27], mas licenças de modelos, conectores e serviços escolhidos devem ser avaliadas separadamente.

**Estado e banco relacional — banco durável compatível com PostgresSaver.** A documentação de persistência diferencia checkpointer, que guarda checkpoints por thread, de store, que guarda dados de aplicação e memória de longo prazo; aponta `PostgresSaver` para persistência de produção e SQLite como alternativa de desenvolvimento [2]. A escolha concreta de provedor, topologia, criptografia, retenção, RLS e backup ainda precisa ser validada.

**Fila, outbox e armazenamento vetorial — serviços próprios desacoplados.** Não há evidência nas fontes de que LangGraph forneça sozinho fila, garantia de exactly-once, RAG multi-tenant ou armazenamento vetorial pronto. Portanto, a proposta seleciona interfaces e requisitos, não um fornecedor específico: fila durável para eventos/jobs, outbox transacional para efeitos, vector store com filtro/namespace por tenant e storage privado para mídia. A implementação deve manter esses componentes substituíveis.

**Provedor de LLM e embeddings — não fixado.** A seleção deve considerar localização dos dados, contrato, custo, latência, retenção e qualidade. Nenhuma fonte fornecida autoriza prometer um modelo ou processamento local. Self-hosting dos componentes da aplicação não significa automaticamente que prompts, embeddings ou anexos deixarão de ser enviados a um provedor externo.

**Transporte — Z-API exclusivamente.** O adaptador usa apenas os endpoints e callbacks encontrados na documentação fornecida. As credenciais ficam no backend, nunca no frontend; o padrão da API coloca `instanceId` e token no caminho, e o `Client-Token` pode ser exigido no header quando ativado [8].

**Implantação — Docker Compose em VPS Hostinger para PoC.** A Hostinger documenta SSH, templates Docker/Docker Manager, firewall, snapshots/backups e monitoramento; disponibilidade e condições dependem do plano e da configuração concreta [18] [19] [20] [21]. Compose é uma forma proposta de empacotamento, não uma garantia de alta disponibilidade.

### 4.2 Stack de aplicação proposta para o PoC

**Backend e workers:** Python com FastAPI para APIs administrativas e callbacks HTTPS, com processos separados para workers assíncronos. Essa escolha mantém o runtime LangGraph e o processamento conversacional no mesmo ecossistema. É uma recomendação de stack, não resultado de benchmark.

**Banco e busca semântica:** PostgreSQL como fonte de verdade para tenants, conversas, eventos, outbox, auditoria, políticas e checkpointer. Para o PoC, usar pgvector no mesmo cluster para embeddings e busca semântica, com `tenant_id` obrigatório, ACL e testes de isolamento em cada consulta. RLS pode ser avaliado como defesa adicional, mas nunca substitui autorização da aplicação. Isso reduz componentes no piloto; se desempenho, isolamento ou escala não atenderem aos testes, reavaliar um vector store separado.

**Fila:** Redis com Celery para execução assíncrona inicial; PostgreSQL permanece a fonte durável dos eventos e da outbox. A fila Redis deve funcionar como mecanismo de despacho, com varredura/reconciliação de itens pendentes no banco para recuperação após falhas. Configurar persistência, limites e monitoramento conforme a operação aprovada; não tratar Redis isoladamente como registro definitivo da mensagem.

**Painel:** Next.js, React e TypeScript para dashboard e central de conversas, consumindo somente APIs autenticadas do backend. A interface não recebe credenciais Z-API nem decide autorização cross-tenant; toda permissão é revalidada no servidor.

**Rede e implantação:** Docker Compose em Hostinger VPS, com Nginx como proxy HTTPS, serviços internos em rede privada, portas mínimas abertas, backups criptografados fora do host e restauração ensaiada. Docker Compose atende ao PoC, mas não oferece alta disponibilidade por si só.

**Mídia:** storage privado com expiração e controle de acesso. O destino concreto e sua residência de dados ficam pendentes de decisão; não assumir que o filesystem da VPS, um bucket externo ou o armazenamento temporário da Z-API atende sozinho à retenção e à recuperação exigidas.

### 4.3 O que deliberadamente não foi selecionado como fundação

Não se seleciona uma plataforma “all-in-one” para esconder as fronteiras de tenant. Memória, RAG, filas, autorização, segredos, webhook e entrega devem ser componentes explícitos e testáveis. Os projetos alternativos são sintetizados na seção seguinte.

## 5. Síntese crítica dos projetos open source pesquisados

### LangGraph — selecionado

**FATOS:** framework de baixo nível para agentes e workflows stateful, long-running, com lógica determinística e agentiva, persistência, execução durável e human-in-the-loop [1] [3]. Checkpoints por thread e stores de dados de aplicação são conceitos distintos; armazenamento em memória perde dados no reinício, e retenção precisa ser planejada [2]. O repositório e a licença MIT foram identificados [3] [6]; a pesquisa observou commits até 12/10/2026 [5].

**AVALIAÇÃO:** melhor aderência ao núcleo de coordenação de conversas, handoff e retomada. Não entrega por si só isolamento multi-tenant, API Z-API, fila, RAG, autenticação, hosting ou conformidade. Será usado atrás da camada de tenancy e efeitos transacionais.

### LangChain — complementar

**FATOS:** framework/ecossistema com interfaces e integrações para modelos, embeddings, ferramentas, vetores e retrievers; a orientação oficial distingue orquestração avançada de LangGraph [4]. O repositório publica licença MIT [27].

**AVALIAÇÃO:** útil como conjunto de adaptadores componíveis, mas não deve virar fronteira de segurança nem banco de memória. Usar somente integrações necessárias e fixar versões.

### LlamaIndex — alternativa para RAG/memória

**FATOS:** o repositório descreve conectores, índices, recuperação, agentes e pipelines; a documentação de memória apresenta histórico curto, blocos de longo prazo, vector store e possibilidade de banco remoto, além de distinguir memória de `Context` do workflow [28] [29]. A licença é MIT [30], e a pesquisa observou commits até 01/10/2026 [31]. O README também informa mudança de foco empresarial para LlamaParse, liteparse e benchmarking, mantendo o framework OSS disponível [28].

**AVALIAÇÃO:** candidato opcional para camada de ingestão/recuperação, não base de tenancy ou execução durável. O uso só será aprovado se o filtro por tenant, exclusão, serialização, custos e dependências forem comprovados. Não combinar automaticamente LlamaIndex e LangGraph na primeira versão; isso aumentaria superfícies, versões e pontos de falha.

### CrewAI — candidato para PoC, não selecionado

**FATOS:** framework MIT com agents, crews, tools, memory, knowledge e flows; a documentação distingue colaboração autônoma de crews e controle explícito/event-driven de flows [32] [34]. Releases consultadas apresentavam atividade recente, inclusive a série 1.15.33 [33]. Persistência/checkpoint de flows não equivale, por si só, a fila distribuída, exatamente uma vez, HA ou idempotência.

**AVALIAÇÃO:** poderia atender a fluxos controlados, mas a decisão seleciona LangGraph para reduzir alternativas e manter o grafo explícito. Se CrewAI for reconsiderado, agentes devem ter permissões mínimas, enquanto regras de tenant, efeitos Z-API e transações permanecem fora deles.

### Microsoft AutoGen — não recomendado para projeto novo

**FATOS:** o repositório descreve Core, AgentChat, runtimes locais/distribuídos, ferramentas, MCP e execução de código; a memória e RAG são capacidades que exigem configuração de armazenamento e particionamento próprios [35] [36]. O repositório declara “maintenance mode”, sem novos recursos ou melhorias, e recomenda Microsoft Agent Framework para novos projetos. O código é MIT e a documentação usa CC BY 4.0 [35].

**AVALIAÇÃO:** pode ser usado em experimento isolado, mas não deve ser base estratégica nova. Execução de código e MCP ampliam o raio de impacto; não oferecer comandos arbitrários no processo principal.

### Letta — opcional, com diligência adicional

**FATOS:** o repositório antigo direciona o projeto atual para `letta-code` e informa que o servidor V1 foi aposentado [37]. A documentação descreve agentes stateful com estado, mensagens, memória e chamadas de ferramentas persistidos; o self-hosting usa App Server, token, volumes persistentes e pode ter acesso a shell/filesystem do host [38] [39]. A pesquisa não confirmou licença vigente do repositório atual.

**AVALIAÇÃO:** aderente a memória persistente, mas a possibilidade de blocos compartilhados e acesso ao host exige isolamento forte. Não selecionar como fundação sem confirmar licença atual, modelo de segurança, retenção, backup, tenancy e versão operacional.

### Mem0 — memória opcional

**FATOS:** biblioteca e servidor self-hosted via Docker Compose, com operações de adicionar/buscar memória, filtros como `user_id`, dashboard, chaves e audit log segundo a documentação consultada [40] [41] [42]. O repositório declara Apache-2.0 [40]. A configuração exige provedor de LLM e embeddings; self-hosting do serviço não significa processamento totalmente local [41]. As fontes não caracterizam Mem0 como fila, orquestrador ou motor de execução durável.

**AVALIAÇÃO:** possível camada de memória semântica, não substituto de histórico, fila, autorização ou RAG documental geral. O uso será adiado até demonstrar isolamento, correção de memórias, exclusão propagada, custo e transferência de dados.

### Haystack — alternativa RAG/agentes, licença pendente

**FATOS:** framework Python para pipelines modulares, RAG, agentes, ferramentas, memória e execução assíncrona; o componente Agent documenta ferramentas, `state_schema`, hooks, limite de passos e métricas [43] [44]. As fontes fornecidas não confirmaram de maneira suficiente a licença exata nem cadência recente de releases/commits.

**AVALIAÇÃO:** funcionalmente plausível, mas a auditoria de licença, manutenção, persistência e tenancy está pendente. Não selecionar enquanto esses itens não forem confirmados.

### PydanticAI — alternativa tipada

**FATOS:** SDK Python para agentes tipados, saídas validadas, dependências e ferramentas derivadas de assinaturas [45]. O repositório publica licença MIT [46]. Execução durável é uma integração com engines externas, como Temporal, DBOS, Prefect, Restate, Lambda, Kitaru e outras; não decorre de um processo simples em VPS [47].

**AVALIAÇÃO:** excelente alternativa para contratos tipados e validação, mas usar simultaneamente PydanticAI e LangGraph como dois runtimes centrais não é recomendado no PoC. Pode substituir LangGraph em uma decisão posterior se a necessidade principal passar a ser tipagem e uma engine de execução durável externa.

### Agno — candidato alternativo

**FATOS:** o repositório e AgentOS documentam agentes, times, workflows, APIs REST/MCP, armazenamento configurável, execução durável/background, retomada, aprovações, tracing, agendamento e controle de acesso; múltiplas réplicas exigem componentes compartilhados de transporte [48] [50]. A licença informada é Apache-2.0 e a pesquisa observou commits até 29/09/2026 [48] [49]. A telemetria pode ser desligada por `AGNO_TELEMETRY=false`, conforme o repositório [48].

**AVALIAÇÃO:** candidato tecnicamente forte para piloto, mas o desenho seleciona LangGraph por foco explícito em grafos, checkpoints e handoff. Agno pode ser benchmark de substituição, não dependência adicional inicial. Qualquer claim de isolamento interno deve ser testado para cada objeto — sessão, memória, documento, trace, ferramenta e aprovação.

### n8n — não selecionado como fundação

**FATOS:** o repositório se apresenta como plataforma self-hosted de workflows/agentes sob Sustainable Use License e Enterprise License, e não como licença permissiva de software livre [51]. O modo de fila documenta Redis e banco acessíveis pelos workers e não suporta execução distribuída com SQLite [52].

**AVALIAÇÃO:** pode acelerar automações internas, mas a licença e o papel de fronteira de produto multiempresa precisam de revisão específica. Não será a fronteira de isolamento nem o runtime central da proposta.

### Cinco repositórios GitHub auditados — inspiração conversacional, não fundação de produção

**Regra comum — FATO/RECOMENDAÇÃO:** os cinco projetos abaixo foram inspecionados como fontes de padrões de conversação, memória, batching, roteamento, gates e handoff. Nenhum deles é uma base pronta para a arquitetura empresarial desta proposta. Qualquer Baileys, WhatsApp Cloud API/Graph API, Telegram ou outro transporte presente nos projetos é incompatível com a decisão de **Z-API exclusiva** e não será integrado, adaptado, instalado ou copiado. Somente padrões de domínio podem ser reimplementados independentemente atrás do adaptador e dos webhooks Z-API, com contratos, testes e controles próprios.

- **`neural-maze/ava-whatsapp-agent-course` — material didático/demo:** **FATO:** o README o apresenta como curso para construir a agente Ava; os arquivos sustentam padrões de histórico curto, sumarização, memória por fatos, recuperação limitada, roteamento de texto/imagem/áudio e integração de mídia [55] [57] [59] [60] [61] [62]. A implementação concreta usa WhatsApp Cloud API/Graph API, variáveis e endpoints da Meta, portanto é transporte incompatível e não será reutilizada [59]. **RECOMENDAÇÃO:** estudar apenas os padrões conceituais e reimplementá-los sobre Z-API. **FATO sobre licença/manutenção:** README e `LICENSE` concordam com MIT; a página consultada mostra atividade até 20/10/2025, sem provar manutenção contínua, SLA, testes de produção ou suporte empresarial [56] [63]. Dependências, modelos, provedores e assets exigem revisão própria.

- **`abdelrhmanHasaan/wa-agent-sdk` — SDK beta com mecanismos úteis, mas transporte proibido:** **FATO:** README, documentação e código descrevem batching por conversa com janela de silêncio e limite máximo, cancelamento de flush em andamento, re-enfileiramento, memória limitada, gates de participação, personas e hooks [64] [65] [66] [67] [68] [69] [70]. O transporte/ponte é Baileys, declarado no pacote Node e na documentação [71] [72], logo não pode ser integrado nem copiado para esta proposta. **RECOMENDAÇÃO:** reimplementar do zero, usando webhooks Z-API, somente a lógica de batching, invalidação controlada, gates e roteamento que sobreviver à validação. **FATO sobre licença/manutenção:** pyproject e `LICENSE` declaram MIT, mas o copyright coletivo “WaAgent SDK Contributors” e a classificação Beta justificam validar titularidade e direitos antes de qualquer reutilização; commits visíveis em 24–25/08/2026 são apenas sinal de atividade, não prova de suporte ou prontidão [71] [73] [74].

- **`nathanhoulamy/luna-ai` — chatbot estreito/opinionated:** **FATO:** README e código demonstram persona configurável, memória em camadas, allowlists/gatilhos, silêncio/heartbeat, coalescência de mensagens e respostas divididas em bolhas [75] [77] [83] [84] [85] [86] [87]. O transporte WhatsApp usa Baileys, QR e sessão local; Telegram é outro transporte observado; não há adaptador Z-API nas fontes consultadas [78] [80] [81] [88]. Nenhum desses transportes será incorporado. **RECOMENDAÇÃO:** aproveitar apenas os padrões conversacionais, reimplementados com Z-API e governança multi-tenant. **FATO sobre licença/manutenção:** `LICENSE` contém MIT com copyright “Groovy Kiwi” 2026; a divergência nominal em relação ao proprietário do repositório exige validação de titularidade. Datas públicas de criação/atualização/push em março de 2026 são sinais limitados, não prova de manutenção contínua ou adequação empresarial [76] [79].

- **`pnoboesam/whatsapp-agent` — demonstração end-to-end com Cloud API:** **FATO:** README e código mostram backend FastAPI, LangChain/LangGraph, checkpointer, RAG, ferramentas de leads/handoff, deduplicação e estado por conversa [89] [90] [91] [92] [93]. O adaptador implementa Meta WhatsApp Cloud/Graph API e webhook Meta, em conflito direto com Z-API; não será integrado, adaptado ou copiado [91] [92]. **RECOMENDAÇÃO:** estudar separação entre webhook, grafo, ferramentas, handoff e avaliação e reimplementar essas fronteiras usando somente Z-API. **FATO sobre licença/manutenção:** a licença não foi confirmada nas fontes abertas e não há base suficiente para afirmar atividade recente; não copiar código até esclarecer direitos [94] [95].

- **`SomanAbbasi/Whatsapp-Agent` — projeto baseado em curso, útil como referência seletiva:** **FATO:** README e código apresentam persona, histórico curto, memória de longo prazo simples, áudio, imagem, sumarização e grafo de orquestração [96] [97] [98] [99] [101]. O webhook processa Cloud API/Graph API e não implementa agregação de fragmentos nem invalidação de geração em curso; esse transporte é incompatível e não será usado [97] [102]. **RECOMENDAÇÃO:** reimplementar sobre webhooks Z-API somente os padrões agnósticos de orquestração, memória governada e roteamento, sem transportar componentes Meta. **FATO sobre licença/manutenção:** a licença própria e os direitos de reutilização não foram confirmados; a atividade consultada também não forneceu evidência suficiente para datas ou frequência. Não copiar código sem esclarecimento jurídico [100] [104] [105].

**Conclusão da síntese:** esses projetos ajudam a formular uma UX de batching, respostas concisas, personas transparentes, memória limitada e gates de participação, mas não mudam a stack, o cronograma ou a decisão de transporte. A produção continua dependente de implementação própria, validação dos webhooks Z-API, fila/outbox, isolamento multi-tenant, governança de memória, autorização, observabilidade e homologação; não há código implementado nem homologação decorrente desta análise.

## 6. Estrutura de dados multi-tenant

A estrutura abaixo é uma **proposta de domínio**, não um esquema já implementado.

### 6.1 Relacional

Todas as entidades de negócio devem ter `tenant_id` obrigatório, salvo tabelas globais explicitamente aprovadas. O vínculo de tenant deve ser validado no servidor e, quando possível, aplicado também na camada de persistência.

Entidades principais:

- `tenants`: empresa, estado, plano, política de retenção e configurações não secretas.
- `tenant_members` e `roles`: usuários, papéis, escopos administrativos e trilha de alterações.
- `zapi_instances`: tenant, `instance_id`, estado operacional e referência ao segredo; o token nunca é armazenado em claro em logs.
- `contacts`: tenant, instância, identificador original, tipo de identificador, `chatLid` quando disponível, atributos mínimos e status de privacidade.
- `conversations`: tenant, instância, contato/grupo, chave interna, estado do fluxo e referência ao thread do agente. `thread_id` não autoriza acesso sozinho.
- `messages`: tenant, conversa, direção, identificadores Z-API, tipo, conteúdo minimizado, mídia, timestamps e estado interno.
- `webhook_events`: tenant resolvido, instância, tipo de callback, identificador/event key, payload minimizado, hash, recebimento, processamento e resultado.
- `outbox_messages`: intenção de envio, conteúdo aprovado, chave idempotente, tentativa, estado, retorno da API e próxima tentativa.
- `message_status_events`: eventos de delivery/status, status normalizado, momento e deduplicação.
- `graph_runs` e `graph_checkpoints`: tenant, conversa, execução, versão do grafo, estado resumido, checkpoint e retenção. Checkpoints devem ter expurgo; a documentação alerta que crescimento contínuo precisa de política de retenção [2].
- `documents`, `document_versions`, `chunks` e `access_grants`: corpus, versão, origem, finalidade, retenção, ACL e estado de indexação.
- `memory_items`: memória individual ou coletiva, sujeito/escopo, origem, confiança, validade, aprovação, versão e expiração.
- `human_tasks` e `approvals`: ação pendente, responsável, prazo, escopo, decisão e evidência.
- `policy_versions`: regras publicadas, versão, autor, aprovação, data de vigência e rollback.
- `learning_proposals`: hipótese extraída de exemplos, evidência, avaliação, decisão e versão publicada, nunca alteração automática.
- `audit_events`: ator, tenant, objeto, ação, resultado e correlação, sem conteúdo de conversa ou segredos por padrão.
- `quotas` e `usage_records`: limites e consumo por tenant, instância e período.

**RECOMENDAÇÃO:** usar chaves compostas ou índices que sempre incluam `tenant_id` para objetos compartilhados. A autorização deve ser repetida em cada acesso, inclusive jobs assíncronos, ferramentas administrativas, callbacks, traces e downloads. IDs imprevisíveis não substituem autorização por objeto; a OWASP destaca BOLA como risco central [24] [26].

### 6.2 Vetores e recuperação

Cada chunk deve carregar, no mínimo, metadados de tenant, documento, versão, finalidade, ACL, origem, data de expiração e estado de exclusão. A ingestão deve rejeitar documento sem tenant válido. A recuperação deve receber o tenant resolvido pelo backend, aplicar filtro/namespace antes da busca e filtrar novamente antes de compor o prompt.

Não permitir que texto do usuário, saída do modelo ou parâmetro livre escolha `tenant_id`, coleção, índice, credencial ou corpus. Para clientes de maior criticidade, avaliar namespace ou armazenamento físico separado. Embeddings, chunks, resultados derivados e traces são dados sujeitos à retenção e à exclusão; não são “anônimos” por padrão.

As fontes deixam claro que frameworks de agentes/RAG não entregam automaticamente isolamento multi-tenant. A segregação, a ACL e a eliminação devem ser implementadas e testadas pela aplicação [1] [28] [43].

## 7. Memória individual, coletiva e privacidade

### 7.1 Memória individual

A memória individual pode guardar fatos úteis sobre um contato ou conversa, mas somente quando houver finalidade definida, necessidade e prazo. Deve incluir origem, data, confiança, versão, justificativa, escopo e expiração. Conteúdo bruto de mensagens não deve virar memória permanente automaticamente.

Antes de recuperar uma memória, validar tenant, instância, contato, finalidade e papel do solicitante. Antes de gravar, aplicar classificação de sensibilidade, minimização e política de retenção. O titular ou cliente deve ter um caminho para revisão, correção e exclusão, com propagação para banco, vetor, cache, traces, backups conforme a política aprovada.

Memória em RAM ou armazenamento in-memory não é persistência de produção: no caso de LangGraph, a documentação alerta que MemorySaver/InMemorySaver perde dados no reinício [2]. Memórias fornecidas por LlamaIndex, Letta ou Mem0 também não devem ser tratadas como garantia automática de retenção, isolamento ou execução da conversa [29] [39] [41].

### 7.2 Memória coletiva

A memória coletiva de uma empresa deve ser um corpus curado e versionado, com ACL e finalidade explícita. Pode conter políticas, respostas aprovadas, produtos ou procedimentos, mas não deve misturar contatos de clientes diferentes sem base, autorização e revisão.

**RECOMENDAÇÃO:** separar pelo menos: memória do contato, memória da conversa, conhecimento interno do tenant e regras globais da plataforma. Regras globais não podem ser editadas pelo agente. Conteúdo de um tenant só pode virar conhecimento global após processo formal, anonimização quando aplicável e aprovação responsável.

### 7.3 Aprendizado validado sem autoalteração de regras

O sistema pode coletar candidatos a melhoria — por exemplo, respostas corrigidas, intenções mal classificadas, documentos que faltaram ou decisões humanas — em `learning_proposals`. O processo proposto é:

1. coletar exemplos com minimização e referência de consentimento/finalidade;
2. agrupar e avaliar qualidade, segurança, custo e risco de vazamento;
3. gerar proposta versionada, sem alterar prompt, ferramenta, ACL ou política;
4. submeter a revisão humana autorizada;
5. publicar uma versão imutável com changelog e rollback;
6. executar canário ou conjunto de testes negativos, inclusive cross-tenant;
7. monitorar regressões e retirar a versão se necessário.

O agente nunca deve criar ou ampliar sua própria permissão, alterar regras de cobrança, mudar o tenant, publicar conhecimento global, selecionar credencial ou reconfigurar webhook. A OWASP caracteriza prompt injection e agency excessiva como riscos que exigem privilégio mínimo, validação determinística, autorização downstream e aprovação humana para ações de impacto [53] [54].

## 8. Integração Z-API: escopo documentado e limites

### 8.1 Operações cobertas pelas fontes

A documentação consultada descreve a base `https://api.z-api.io` e o padrão `/instances/{instanceId}/token/{token}/{recurso}`. Quando ativado, o `Client-Token` é enviado no header; a Z-API recomenda chamadas server-side para não expor credenciais [7] [8].

A proposta usa somente os seguintes recursos documentados:

- **Texto:** `POST /send-text`, com `phone` e `message` obrigatórios; resposta de sucesso com `zaapId` e `messageId` [9].
- **Imagem:** `POST /send-image`, com imagem por URL ou Base64 e opções documentadas na página específica [10].
- **Áudio:** `POST /send-audio`, com `phone` e `audio`, por link ou Base64, com opções documentadas como processamento em segundo plano; limites e formatos devem ser homologados [11].
- **Webhook recebido:** configuração por `PUT /update-webhook-received`, com valor contendo URL HTTPS [12].
- **Delivery e status:** callbacks separados para envio/delivery e status; os estados de mensagem publicados incluem `SENT`, `RECEIVED`, `READ`, `READ_BY_ME` e `PLAYED` [7] [14].
- **Saúde da instância:** endpoints documentados de estado/configuração informam conectividade e outros atributos; status inclui `connected`, `smartphoneConnected` e `error` [15] [16].

Nenhum endpoint não listado acima deve ser inventado no desenho. A documentação consultada também não é tratada como catálogo completo de erros. Os códigos 405 e 415 são mencionados em páginas de envio/configuração para método incorreto ou `Content-Type` JSON ausente/incorreto [9] [12].

### 8.2 Segredos

`instanceId`, token de instância e `Client-Token` devem ser tratados como segredos. O token aparece no caminho da URL e pode vazar em logs de proxy, aplicação, traces ou monitoramento. Guardar referências a segredos em cofre ou configuração protegida, restringir leitura por tenant/instância, rotacionar quando possível e mascarar URLs, headers e payloads.

Não enviar credenciais ao frontend, ao LLM, ao prompt, ao vetor, à memória ou ao log. A documentação da Z-API alerta que quem obtém as credenciais pode enviar mensagens em nome da conta e recomenda chamadas do servidor [8].

### 8.3 Webhook como entrada não confiável

A exigência de HTTPS protege o transporte, mas **não equivale a autenticação criptográfica do remetente**. Nas páginas consultadas não foi localizada assinatura HMAC, segredo universal, lista de IPs, challenge, nonce ou garantia geral de retry/ordenação. Essa é uma lacuna documental, não prova de inexistência em toda a oferta Z-API.

Até confirmação do fornecedor, o endpoint deve:

- validar método, tamanho, schema, tipos e campos permitidos;
- resolver `instanceId` contra cadastro próprio e tenant esperado;
- rejeitar instância desativada ou não vinculada;
- usar chave de deduplicação por identificador disponível e hash do evento;
- aplicar rate limiting, limites de concorrência e proteção contra replay;
- persistir antes de iniciar processamento custoso;
- não confiar em `tenant_id`, ferramenta, URL ou instrução enviada no payload;
- não presumir que `Client-Token` chega nos callbacks, pois isso não foi documentado;
- confirmar com a Z-API o mecanismo suportado de autenticação, retry, timeout e ordenação.

Uma URL não previsível, se compatível com o produto, pode ser defesa auxiliar; não deve ser apresentada como autenticação forte.

### 8.4 Itens de homologação obrigatória

Antes de qualquer go-live, testar com instância e credenciais reais: autenticação com e sem `Client-Token` quando aplicável; texto, imagem, áudio, Base64 e URL; MIME/tamanho; mensagens de grupo; LID; callback recebido; mensagens próprias; delivery; todos os status; duplicatas; atraso e falha; desconexão/reconexão; expiração de mídia; timeout; rate limit; erro 405/415; comportamento de retry; rotação de segredo; e encerramento da instância.

A homologação também deve confirmar se a sessão baseada no WhatsApp Web, a conectividade do smartphone e as políticas do serviço atendem ao produto. A documentação descreve esses elementos, mas não oferece garantia de disponibilidade ou SLA [7] [16].

## 9. Implantação em VPS Hostinger

### 9.1 Topologia inicial

**RECOMENDAÇÃO — para PoC ou baixo volume**, usar Docker Compose com:

- serviço HTTPS de entrada e API;
- worker do ingress e worker de conversa;
- banco relacional;
- fila/event store ou componente equivalente;
- serviço de armazenamento vetorial, se escolhido;
- storage de mídia privado;
- agente de métricas/logs;
- job de retenção e expurgo.

A separação de serviços no Compose melhora operação e atualização, mas não cria isolamento de tenant nem alta disponibilidade. Banco, fila, painel e serviços internos devem permanecer em rede privada; somente portas necessárias devem ser expostas.

A Hostinger documenta acesso por SSH, templates e Docker Manager condicionados ao template/plano, firewall e área de backups/snapshots [18] [20] [21]. A orientação de segurança recomenda chaves SSH, restrição de root, firewall e monitoramento de logs [19].

### 9.2 Dimensionamento e premissas

Não é possível fixar CPU, RAM, IOPS, número de instâncias ou volume de mensagens sem dados de carga. O guia Hostinger consultado cita pelo menos 2 GB de RAM para uma experiência mais fluida em instalação Docker, mas isso **não é sizing de produção multiempresa** [18].

O PoC deve registrar: número de tenants e instâncias; mensagens por minuto no pico; concorrência de workers; tamanho e duração de áudio; percentual de mensagens com mídia; tokens por conversa; latência alvo; retenção; tamanho do corpus; frequência de indexação; chamadas externas; uso de memória; crescimento de checkpoints; e custo por modelo/embedding.

A partir desses dados, executar teste de carga com vizinho ruidoso, falhas, fila crescente, banco cheio, storage cheio, indisponibilidade do modelo e callbacks duplicados. Uma VPS única concentra host, disco, rede, banco, fila e aplicação no mesmo domínio de falha.

### 9.3 Backup, restore e continuidade

FATO — a Hostinger documenta backups/snapshots, mas disponibilidade, frequência, retenção e preço dependem do plano e da configuração; há páginas que distinguem backup semanal e opção diária [20]. Snapshot é estado pontual e restauração pode sobrescrever o estado atual.

**RECOMENDAÇÃO:** manter cópia independente e criptografada do banco, eventos, documentos, metadados vetoriais, configurações e referências de segredos. Nunca depender somente do snapshot do VPS. Testar restauração em ambiente separado, medir RPO/RTO aprovados e documentar o procedimento. Backup sem restauração ensaiada não é critério de continuidade.

### 9.4 Observabilidade

Métricas mínimas propostas:

- eventos recebidos, rejeitados, duplicados e atrasados;
- profundidade e idade da fila;
- duração e erro por nó do grafo;
- chamadas de modelo, tokens e custo por tenant;
- acerto/latência de recuperação;
- outbox pendente, retry, dead-letter e callback por estado;
- `connected`, `smartphoneConnected` e erros de instância;
- uso de CPU, memória, disco, storage e rede;
- falhas de backup e último restore testado;
- violações de autorização e tentativas cross-tenant.

Logs devem conter correlação, tenant interno e IDs operacionais minimizados, mas não tokens, conteúdo completo, Base64, prompt integral ou anexos por padrão. Traces e checkpoints têm retenção própria e devem ser incluídos no inventário de dados pessoais.

## 10. Segurança e LGPD

### 10.1 Isolamento multiempresa

A OWASP identifica como riscos multi-tenant o vazamento cross-tenant, IDOR, isolamento insuficiente em banco/cache/storage/compute, vizinho ruidoso, escalada de privilégio, injeção de contexto e falhas de onboarding/offboarding [26]. A OWASP API Top 10 também destaca autorização quebrada por objeto/função, autenticação, consumo irrestrito, SSRF, configuração insegura e consumo inseguro de APIs [24].

Controles obrigatórios propostos:

- derivar tenant da identidade autenticada ou do vínculo `instanceId` no servidor;
- impor autorização em cada objeto, ferramenta, job, documento, memória, arquivo, trace e endpoint administrativo;
- nunca aceitar `tenant_id` livre do payload, usuário ou modelo;
- incluir tenant nas chaves de banco, cache, fila, storage e índice;
- usar negação por padrão e roles mínimas;
- separar credenciais Z-API por tenant/instância;
- limitar concorrência, tamanho, custo, tokens, downloads e chamadas por tenant;
- validar URL de mídia e egress para reduzir SSRF;
- proteger painel e APIs administrativas com autenticação forte e auditoria;
- testar acesso cruzado com contas, IDs, retries, cache, memória, vetor e backups.

### 10.2 Prompt injection e agência excessiva

Mensagens WhatsApp, documentos, mídias transcritas e resultados RAG devem ser marcados como dados não confiáveis. Prompt injection pode ser direta ou indireta; RAG não elimina o risco. A OWASP recomenda privilégio mínimo, ferramentas estreitas, validação determinística de saída, autorização em sistemas downstream, aprovação humana para ações sensíveis e testes adversariais [53] [54].

O modelo não escolhe tenant, credencial, destinatário, namespace, regra, URL arbitrária ou ferramenta fora da allowlist. O backend verifica novamente argumentos e autorização antes do efeito externo. Envio de mensagem, alteração de cadastro, exclusão, publicação de conhecimento e operação administrativa devem ter política própria e, quando aplicável, confirmação humana.

### 10.3 LGPD e governança

A LGPD trata dados pessoais e estabelece princípios como finalidade, adequação, necessidade, transparência, segurança, prevenção e responsabilização; também prevê responsabilidades dos agentes e medidas técnicas e administrativas de segurança [22]. Conversas, telefones ou LIDs, anexos, transcrições, prompts, embeddings, logs, checkpoints e identificadores de mensagem podem conter dados pessoais.

**RECOMENDAÇÃO:** para cada empresa, documentar finalidade, base aplicável, categorias de dados, papéis de controlador/operador, fornecedores e transferências, retenção, descarte, atendimento de titulares, acesso administrativo e resposta a incidentes. A ANPD disponibiliza guia e checklist de segurança para agentes de pequeno porte, que podem orientar controles, mas não substituem análise jurídica [23].

Aplicar minimização: não guardar mensagens completas quando um resumo aprovado for suficiente; não enviar anexos a modelos sem necessidade; separar conteúdo de metadados; criptografar trânsito e repouso quando suportado; restringir acesso; rotacionar segredos; registrar operações relevantes sem excesso de conteúdo; e propagar exclusões a índices, memória, cache, traces e cópias sob controle da plataforma.

Esta seção é orientação arquitetural e não aconselhamento jurídico. Papeis, bases legais, retenção, transferências internacionais, contratos e comunicações de incidentes devem ser revisados por assessoria competente antes da produção.

## 11. Plano de fases e critérios de aceite

### 11.1 Cronograma preliminar

**Estimativa indicativa: 13–20 semanas**, considerando uma equipe pequena com cerca de duas pessoas de desenvolvimento em tempo integral e apoio parcial de produto/infraestrutura. A estimativa não inclui atrasos de contratação, acesso à instância, aprovações legais nem retrabalho provocado por critérios de aceite. Como as fases são sequenciais e bloqueadas por validação, cada falha de gate desloca as etapas seguintes.

- Fase 0 — arquitetura e threat model: **1–2 semanas**.
- Fase 1 — integração inicial Z-API e homologação de texto/webhook: **2–3 semanas**.
- Fase 2 — conversa persistente com LangGraph: **2–3 semanas**.
- Fase 3 — memória, documentos, vetores e testes de isolamento: **3–4 semanas**.
- Fase 4 — mídia e estados de entrega: **2–3 semanas**.
- Fase 5 — hardening, carga, backup/restore e operação: **2–3 semanas**.
- Fase 6 — piloto limitado e decisão go/no-go: **1–2 semanas**.

O cronograma deve ser reestimado após a Fase 0, quando volume, equipe, provedores, requisitos de privacidade, plano Hostinger e comportamento real da Z-API estiverem definidos.

### Fase 0 — decisões e threat model

**Entregáveis:** mapa de tenants/instâncias/contatos; matriz de dados; papéis LGPD; seleção de modelo; contrato e limites Z-API; plano Hostinger; threat model; política de retenção; critérios de RPO/RTO; decisão sobre vector store.

**Aceite:** nenhuma lacuna crítica sem proprietário; credenciais de homologação autorizadas; confirmação de que a Z-API será o único transporte; aprovação do modelo de isolamento e do processo de aprendizado validado.

### Fase 1 — esqueleto de integração Z-API

**Escopo:** adaptador server-side, endpoint HTTPS, configuração dos webhooks documentados, armazenamento de eventos, parsing, validação, segredos, logs redigidos e outbox simulada.

**Aceite:** chamada de texto em homologação; callback recebido; correlação por IDs; deduplicação; rejeição de payload inválido; nenhum segredo em log; confirmação experimental dos estados e erros documentados.

### Fase 2 — conversa mínima com LangGraph

**Escopo:** thread/checkpoint persistente, histórico mínimo, fluxo determinístico, nó LLM limitado, resposta de texto, handoff e retenção.

**Aceite:** retomada após reinício; erro de worker sem perda indevida; checkpoint isolado por tenant/conversa; aprovação humana bloqueia efeito até decisão; regras não podem ser alteradas pelo agente.

### Fase 3 — memória, documentos e vetores

**Escopo:** ingestão, versionamento, filtro tenant, memória individual, corpus coletivo, expiração, exclusão e avaliação de recuperação.

**Aceite:** testes negativos não retornam documento, memória ou vetor de outro tenant; exclusão remove todas as cópias sob controle; documentos maliciosos não alteram política; métricas de precisão/latência/custo atingem metas acordadas.

### Fase 4 — mídia e estados de entrega

**Escopo:** áudio/imagem documentados, download seguro, storage privado, expiração, callbacks de delivery/status e reconciliação.

**Aceite:** formatos e limites aprovados em instância real; URL externa não permite SSRF; mídia necessária é importada dentro da janela documentada de 30 dias; duplicatas e reordenação não causam mensagens repetidas; estados internos distinguem aceitação, processamento, delivery e leitura.

### Fase 5 — segurança, carga e operação

**Escopo:** hardening de VPS, firewall, SSH, backups externos, restore, métricas, alertas, rate limits, teste de vizinho ruidoso, incident response e revisão LGPD.

**Aceite:** restore reproduz ambiente em prazo aprovado; carga e falha não causam cross-tenant; alertas funcionam; portas internas não estão públicas; tokens não aparecem em logs; documentação operacional está revisada.

### Fase 6 — piloto limitado e go/no-go

**Escopo:** poucos tenants autorizados, dados controlados, acompanhamento diário, canário de política e revisão de custos.

**Go-live somente se:** homologação Z-API concluída; isolamento automatizado aprovado; backup/restore comprovados; limites e custos conhecidos; contrato e tratamento de dados revisados; plano de desconexão/reconexão aprovado; suporte e plantão definidos; e o usuário aprovar explicitamente a passagem de PoC para produção.

## 12. Riscos e decisões a validar antes do desenvolvimento

### Riscos principais

1. **Vazamento cross-tenant:** checkpoint, vetor, memória, cache, fila, arquivo, trace ou ferramenta sem escopo correto.
2. **Webhook não autenticado:** HTTPS foi documentado, mas assinatura ou autenticação de origem não foi confirmada.
3. **Credencial exposta:** token no caminho da URL pode aparecer em logs, proxies ou traces.
4. **Duplicidade e perda:** retries, ordem, timeout e exatamente uma vez não foram garantidos pela documentação consultada.
5. **Dependência WhatsApp/Z-API:** sessão, desconexão, políticas e limites podem afetar o serviço.
6. **Mídia externa:** expiração em 30 dias, SSRF, malware, tamanho e codec desconhecidos sem homologação.
7. **Agência do LLM:** prompt injection, ferramenta excessiva, alteração indevida e envio ao destinatário errado.
8. **Retenção excessiva:** mensagens, prompts, embeddings, checkpoints e traces podem ultrapassar finalidade.
9. **VPS única:** falha de host, disco, rede, configuração ou atualização pode interromper banco, fila e aplicação.
10. **Backups insuficientes:** snapshot ou backup do provedor pode não atender RPO/RTO nem sobreviver a comprometimento da conta.
11. **Licença e manutenção:** componentes têm licenças e maturidades diferentes; AutoGen está em maintenance mode; Letta atual exige confirmação de licença; Haystack exige auditoria; n8n usa licenças fair-code específicas.
12. **Custo e latência:** modelos, embeddings, transcrição, mídia e retries podem gerar custo variável não resolvido pela pesquisa.

### Decisões que o usuário deve validar

- Aceitar LangGraph como runtime principal ou preferir benchmark formal contra Agno/PydanticAI.
- Definir provedor de LLM/embeddings e se dados podem sair do ambiente próprio.
- Definir vector store e nível de isolamento físico/lógico exigido por tenant.
- Definir retenção de mensagens, mídia, memória, checkpoints, logs e backups.
- Confirmar mecanismo de autenticação de webhook, retry, timeout, ordem e limites com Z-API.
- Confirmar comportamento de áudio, imagem, LID, grupos e desconexão em instância real.
- Definir RPO/RTO, região, plano e backup Hostinger, além de orçamento operacional.
- Aprovar papéis LGPD, contratos, bases/finalidades e procedimento de titulares/incidentes.
- Definir quais ações sempre exigem aprovação humana.
- Definir se o painel administrativo terá suporte a operações cross-tenant e quais controles as cercarão.
- Definir política de aprendizado e autoridade para publicar mudanças.
- Definir volume inicial, pico, latência, número de tenants e estratégia de escala além de uma VPS.

## 13. Conclusão

A combinação proposta — **LangGraph como orquestrador, aplicação própria multi-tenant, persistência durável, memória/RAG com escopo explícito, fila/outbox, adaptador Z-API exclusivo e Docker Compose em VPS Hostinger para PoC** — é tecnicamente coerente com os fatos documentados e preserva substituibilidade dos componentes.

Ela não é uma plataforma pronta. O maior risco está nas fronteiras entre empresas e nos efeitos externos: qualquer thread, consulta vetorial, memória, ferramenta, callback, arquivo, segredo ou referência de mensagem deve resolver e autorizar o tenant no servidor. O segundo grande risco é operacional: Z-API, sessão WhatsApp, callbacks e limites precisam de homologação real; uma VPS simples não equivale a HA, DR testado ou SLA.

A recomendação é **aprovar somente a validação arquitetural e o PoC controlado**, não o go-live. O usuário deve revisar e aceitar esta arquitetura antes de qualquer implementação. Nenhum código, credencial, conexão real ou integração funcional foi criado como parte deste relatório.

## References

[1]: https://docs.langchain.com/oss/python/langgraph/overview "LangGraph overview — documentação oficial LangChain"

[2]: https://docs.langchain.com/oss/python/langgraph/persistence "LangGraph persistence — documentação oficial LangChain"

[3]: https://github.com/langchain-ai/langgraph "Repositório oficial LangGraph"

[4]: https://github.com/langchain-ai/langchain "LangChain — repositório oficial"

[5]: https://github.com/langchain-ai/langgraph/commits/main/ "Histórico de commits LangGraph"

[6]: https://github.com/langchain-ai/langgraph/blob/main/LICENSE "LangGraph — licença MIT"

[7]: https://developer.z-api.io/en/quickstart/introduction "Z-API — introdução/fluxo de envio"

[8]: https://developer.z-api.io/security/client-token "Z-API — token de segurança da conta"

[9]: https://developer.z-api.io/message/send-message-text "Z-API — enviar texto simples"

[10]: https://developer.z-api.io/message/send-message-image "Z-API — enviar imagem"

[11]: https://developer.z-api.io/message/send-message-audio "Z-API — enviar áudio"

[12]: https://developer.z-api.io/en/webhooks/on-message-received "Z-API — webhook de mensagem recebida"

[13]: https://developer.z-api.io/webhooks/on-message-received-examples "Z-API — exemplos de callback de mensagens recebidas"

[14]: https://developer.z-api.io/en/webhooks/on-whatsapp-message-status-changes "Z-API — status de mensagem"

[15]: https://developer.z-api.io/instance/me "Z-API — dados da instância"

[16]: https://developer.z-api.io/instance/status "Z-API — status da instância"

[17]: https://developer.z-api.io/en/tips/lid "Z-API — identificadores LID"

[18]: https://www.hostinger.com/tutorials/how-to-install-docker-on-ubuntu "Hostinger — como instalar Docker no Ubuntu/VPS"

[19]: https://www.hostinger.com/tutorials/vps-security/ "Hostinger — dicas de segurança para VPS"

[20]: https://www.hostinger.com/support/5726606-how-to-use-the-vps-dashboard-in-hostinger/ "Hostinger — painel VPS, Docker Manager e backups"

[21]: https://www.hostinger.com/support/8172641-how-to-use-a-managed-vps-firewall-at-hostinger/ "Hostinger — firewall gerenciado de VPS"

[22]: https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-publicacaooriginal-156212-pl.html "Lei nº 13.709/2018 — LGPD, Câmara dos Deputados"

[23]: https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia-orientativo-sobre-seguranca-da-informacao-para-agentes-de-tratamento-de-pequeno-porte "ANPD — guia de segurança da informação"

[24]: https://owasp.org/API-Security/editions/2023/en/0x11-t10/ "OWASP API Security Top 10 — 2023"

[25]: https://cheatsheetseries.owasp.org/cheatsheets/Webhook_Security_Cheat_Sheet.html "OWASP — Webhook Security Cheat Sheet"

[26]: https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html "OWASP — Multi-Tenant Application Security Cheat Sheet"

[27]: https://github.com/langchain-ai/langchain/blob/master/LICENSE "LangChain — licença MIT"

[28]: https://github.com/run-llama/llama_index "LlamaIndex — repositório oficial"

[29]: https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/memory/ "LlamaIndex — Memory"

[30]: https://github.com/run-llama/llama_index/blob/main/LICENSE "LlamaIndex — licença MIT"

[31]: https://github.com/run-llama/llama_index/commits/main/ "LlamaIndex — histórico de commits"

[32]: https://github.com/crewaiinc/crewai "CrewAI — repositório oficial"

[33]: https://github.com/crewaiinc/crewAI/releases "CrewAI — releases oficiais"

[34]: https://docs.crewai.com/en/concepts/overview "CrewAI — documentação de conceitos"

[35]: https://github.com/microsoft/autogen "Microsoft AutoGen — repositório oficial"

[36]: https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/memory.html "AutoGen — Memory and RAG"

[37]: https://github.com/letta-ai/letta "Letta — repositório anterior e redirecionamento"

[38]: https://docs.letta.com/self-hosting/ "Letta — self-hosting"

[39]: https://docs.letta.com/v1-sdk/concepts/stateful-agents/ "Letta — stateful agents"

[40]: https://github.com/mem0ai/mem0 "Mem0 — repositório oficial"

[41]: https://docs.mem0.ai/open-source/setup "Mem0 — open source setup"

[42]: https://docs.mem0.ai/open-source/overview "Mem0 — open source overview"

[43]: https://github.com/deepset-ai/haystack "Haystack — repositório oficial"

[44]: https://docs.haystack.deepset.ai/docs/agent "Haystack — Agent component"

[45]: https://github.com/pydantic/pydantic-ai "PydanticAI — repositório oficial"

[46]: https://github.com/pydantic/pydantic-ai/blob/main/LICENSE "PydanticAI — licença MIT"

[47]: https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/ "PydanticAI — Durable Execution"

[48]: https://github.com/agno-agi/agno "Agno — repositório oficial"

[49]: https://github.com/agno-agi/agno/commits/main/ "Agno — commits oficiais"

[50]: https://docs.agno.com/agent-os/introduction "Agno — documentação AgentOS"

[51]: https://github.com/n8n-io/n8n "n8n — repositório oficial"

[52]: https://docs.n8n.io/hosting/scaling/queue-mode/ "n8n — queue mode"

[53]: https://genai.owasp.org/llmrisk/llm01-prompt-injection/ "OWASP GenAI — LLM01:2025 Prompt Injection"

[54]: https://genai.owasp.org/llmrisk/llm062025-excessive-agency/ "OWASP GenAI — LLM06:2025 Excessive Agency"
[55]: https://github.com/neural-maze/ava-whatsapp-agent-course "Repositório neural-maze/ava-whatsapp-agent-course — README e overview"

[56]: https://github.com/neural-maze/ava-whatsapp-agent-course/blob/main/LICENSE "ava-whatsapp-agent-course — LICENSE"

[57]: https://github.com/neural-maze/ava-whatsapp-agent-course/blob/main/docs/GETTING_STARTED.md "ava-whatsapp-agent-course — GETTING_STARTED.md"

[58]: https://github.com/neural-maze/ava-whatsapp-agent-course/blob/main/pyproject.toml "ava-whatsapp-agent-course — pyproject.toml"

[59]: https://github.com/neural-maze/ava-whatsapp-agent-course/blob/main/src/ai_companion/interfaces/whatsapp/whatsapp_response.py "ava-whatsapp-agent-course — whatsapp_response.py"

[60]: https://github.com/neural-maze/ava-whatsapp-agent-course/blob/main/src/ai_companion/graph/nodes.py "ava-whatsapp-agent-course — nodes.py"

[61]: https://github.com/neural-maze/ava-whatsapp-agent-course/blob/main/src/ai_companion/graph/graph.py "ava-whatsapp-agent-course — graph.py"

[62]: https://github.com/neural-maze/ava-whatsapp-agent-course/blob/main/src/ai_companion/core/prompts.py "ava-whatsapp-agent-course — prompts.py"

[63]: https://github.com/neural-maze/ava-whatsapp-agent-course/commits/main "ava-whatsapp-agent-course — histórico de commits da branch main"

[64]: https://github.com/abdelrhmanHasaan/wa-agent-sdk "Repositório abdelrhmanHasaan/wa-agent-sdk"

[65]: https://github.com/abdelrhmanHasaan/wa-agent-sdk/blob/main/README.md "wa-agent-sdk — README.md"

[66]: https://github.com/abdelrhmanHasaan/wa-agent-sdk/blob/main/Doc.md "wa-agent-sdk — Doc.md"

[67]: https://github.com/abdelrhmanHasaan/wa-agent-sdk/blob/main/src/wa_agent_sdk/batching.py "wa-agent-sdk — batching.py"

[68]: https://github.com/abdelrhmanHasaan/wa-agent-sdk/blob/main/src/wa_agent_sdk/client.py "wa-agent-sdk — client.py"

[69]: https://github.com/abdelrhmanHasaan/wa-agent-sdk/blob/main/src/wa_agent_sdk/memory.py "wa-agent-sdk — memory.py"

[70]: https://github.com/abdelrhmanHasaan/wa-agent-sdk/blob/main/src/wa_agent_sdk/safety.py "wa-agent-sdk — safety.py"

[71]: https://github.com/abdelrhmanHasaan/wa-agent-sdk/blob/main/pyproject.toml "wa-agent-sdk — pyproject.toml"

[72]: https://github.com/abdelrhmanHasaan/wa-agent-sdk/blob/main/src/wa_agent_sdk/node_bridge/package.json "wa-agent-sdk — package.json da ponte Node"

[73]: https://github.com/abdelrhmanHasaan/wa-agent-sdk/blob/main/LICENSE "wa-agent-sdk — LICENSE"

[74]: https://github.com/abdelrhmanHasaan/wa-agent-sdk/commits/main/ "wa-agent-sdk — histórico de commits da branch main"

[75]: https://github.com/nathanhoulamy/luna-ai "Repositório nathanhoulamy/luna-ai"

[76]: https://api.github.com/repos/nathanhoulamy/luna-ai "GitHub REST API — metadados de nathanhoulamy/luna-ai"

[77]: https://raw.githubusercontent.com/nathanhoulamy/luna-ai/main/README.md "luna-ai — README.md bruto da branch main"

[78]: https://raw.githubusercontent.com/nathanhoulamy/luna-ai/main/package.json "luna-ai — package.json"

[79]: https://raw.githubusercontent.com/nathanhoulamy/luna-ai/main/LICENSE "luna-ai — LICENSE"

[80]: https://raw.githubusercontent.com/nathanhoulamy/luna-ai/main/src/transports.ts "luna-ai — src/transports.ts"

[81]: https://raw.githubusercontent.com/nathanhoulamy/luna-ai/main/src/baileys.ts "luna-ai — src/baileys.ts"

[82]: https://raw.githubusercontent.com/nathanhoulamy/luna-ai/main/src/chat/runtime.ts "luna-ai — src/chat/runtime.ts"

[83]: https://raw.githubusercontent.com/nathanhoulamy/luna-ai/main/tests/coalescing.test.ts "luna-ai — tests/coalescing.test.ts"

[84]: https://raw.githubusercontent.com/nathanhoulamy/luna-ai/main/src/reply.ts "luna-ai — src/reply.ts"

[85]: https://raw.githubusercontent.com/nathanhoulamy/luna-ai/main/src/memory.ts "luna-ai — src/memory.ts"

[86]: https://raw.githubusercontent.com/nathanhoulamy/luna-ai/main/examples/bot/persona.md "luna-ai — examples/bot/persona.md"

[87]: https://raw.githubusercontent.com/nathanhoulamy/luna-ai/main/examples/bot/heartbeat.md "luna-ai — examples/bot/heartbeat.md"

[88]: https://api.github.com/repos/groovykiwi/luna-ai/git/trees/main?recursive=1 "Árvore Git do projeto luna-ai"

[89]: https://github.com/pnoboesam/whatsapp-agent "Repositório pnoboesam/whatsapp-agent"

[90]: https://github.com/pnoboesam/whatsapp-agent/blob/main/pyproject.toml "whatsapp-agent — pyproject.toml"

[91]: https://github.com/pnoboesam/whatsapp-agent/blob/main/app/api/routes/whatsapp.py "whatsapp-agent — rota WhatsApp"

[92]: https://github.com/pnoboesam/whatsapp-agent/blob/main/app/services/whatsapp.py "whatsapp-agent — serviço de envio WhatsApp"

[93]: https://github.com/pnoboesam/whatsapp-agent/blob/main/app/agent/agent.py "whatsapp-agent — implementação central do agente"

[94]: https://github.com/pnoboesam/whatsapp-agent/tree/main/app/api/routes "whatsapp-agent — listagem app/api/routes"

[95]: https://github.com/pnoboesam/whatsapp-agent/blob/main/LICENSE "whatsapp-agent — tentativa de arquivo LICENSE"

[96]: https://raw.githubusercontent.com/SomanAbbasi/Whatsapp-Agent/main/README.md "SomanAbbasi/Whatsapp-Agent — README"

[97]: https://raw.githubusercontent.com/SomanAbbasi/Whatsapp-Agent/main/src/interfaces/whatsapp_response.py "SomanAbbasi/Whatsapp-Agent — whatsapp_response.py"

[98]: https://raw.githubusercontent.com/SomanAbbasi/Whatsapp-Agent/main/src/ai_companion/core/prompts.py "SomanAbbasi/Whatsapp-Agent — prompts.py"

[99]: https://raw.githubusercontent.com/SomanAbbasi/Whatsapp-Agent/main/src/ai_companion/modules/memory/long_term/memory_manager.py "SomanAbbasi/Whatsapp-Agent — memory_manager.py"

[100]: https://raw.githubusercontent.com/SomanAbbasi/Whatsapp-Agent/main/pyproject.toml "SomanAbbasi/Whatsapp-Agent — pyproject.toml"

[101]: https://raw.githubusercontent.com/SomanAbbasi/Whatsapp-Agent/main/src/ai_companion/graph/graph.py "SomanAbbasi/Whatsapp-Agent — graph.py"

[102]: https://raw.githubusercontent.com/SomanAbbasi/Whatsapp-Agent/main/src/interfaces/webhook_endpoint.py "SomanAbbasi/Whatsapp-Agent — webhook_endpoint.py"

[103]: https://github.com/SomanAbbasi/Whatsapp-Agent/tree/main/src/ai_companion/graph "SomanAbbasi/Whatsapp-Agent — diretório graph"

[104]: https://github.com/SomanAbbasi/Whatsapp-Agent/activity "SomanAbbasi/Whatsapp-Agent — atividade do repositório"

[105]: https://github.com/SomanAbbasi/Whatsapp-Agent/blob/main/LICENSE "SomanAbbasi/Whatsapp-Agent — caminho LICENSE"
