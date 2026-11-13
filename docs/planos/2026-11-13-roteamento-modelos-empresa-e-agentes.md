# Plano — modelos padrão da empresa e personalização por agente

**Status:** proposta para revisão; não implementada.
**Base observada:** `main` / `origin/main`, `c6b29a4c38af02fca8ee5a5c74eeb29acbfea0e6`.
**Escopo:** principal e alternativas para geração. Embeddings, prompts, WhatsApp e produção não serão alterados nesta etapa.

## Decisão de produto

- O usuário continua escolhendo a conexão padrão da empresa pelo controle **Definir padrão** já existente em Modelo IA. Nenhum agente ou sistema escolhe automaticamente um modelo por marca, benchmark, tipo de mensagem ou perfil comercial.
- Conexões, modelos e credenciais continuam cadastrados uma única vez em **Configurações de modelos**. A ordem padrão da empresa também fica nessa área e usa as conexões existentes: a conexão escolhida em **Definir padrão** é a principal; o usuário ordena as demais como alternativas. Não haverá outro catálogo nem credenciais duplicadas na tela do agente.
- Cada conexão terá o campo editável **Habilidades do modelo**, com capacidades técnicas conhecidas, como saída estruturada, ferramentas ou entrada de imagem. O sistema pode sugerir dados documentados ao reconhecer o identificador exato do modelo; o usuário pode revisá-los. Capacidades publicadas não são prova de qualidade comercial.
- Na criação, o backend copia principal e alternativas para os campos do agente. O usuário pode mudar principal e ordem no próprio agente. Depois da criação, o agente tem sua própria configuração; mudanças nos padrões da empresa não reescrevem agentes existentes.
- A tela do agente mostra somente conexões existentes e sua ordem; não exibe nem duplica chaves, URLs ou protocolos.
- O Gemini atual continua sendo o padrão enquanto o usuário não escolher outra conexão. Esta proposta não muda seleção, configuração ou dados de produção.

## Evidência no checkout

| Arquivo/código | Comportamento observado |
|---|---|
| `backend/app/models.py` (`Tenant`, `Agent`, `LLMConfig`) | `Tenant` não tem política de rota. `Agent` guarda `llm_config_id` e `fallback_config_ids` JSON. `LLMConfig.is_default` identifica a conexão padrão por tenant. |
| `backend/app/routes_llm.py` (`make_default`, `delete_connection`) | Usuário escolhe o padrão existente. Há proteções para conexões usadas por agentes ou pela busca. |
| `backend/app/routes_agents.py` (`create_agent`, `update_agent`, `_validate_models`) | Criação valida tenant, mas não copia uma cadeia padrão. Edição permite principal e alternativas próprias. |
| `backend/app/model_router.py` (`candidate_configs`) | Usa principal do agente; se nula, resolve `LLMConfig.is_default`; depois tenta as alternativas do agente em ordem, filtrando conexões desativadas. |
| `frontend/llm-ui.js` (`agentFields`, `wireAgentForm`) | Editor já seleciona principal, ordena alternativas e limita a oito. A ação “Definir padrão” existe na lista de conexões. |
| `backend/migrations/versions/0003_model_routing.py` | Revisão histórica criou a conexão padrão e os campos do agente. Não editar migrations antigas. |
| `tests/integration/test_runtime_safety.py` | Cobre fallback ordenado, escopo tenant, conexão desativada, exclusão protegida e teste técnico da conexão. |

O código atual não tem fallback da empresa. O modelo padrão do tenant é uma conexão singular. A busca usa `KnowledgeSearchConfig`/`embedding_config.py`, separada do roteamento de geração; não derivar embeddings da cadeia conversacional.

## Desenho recomendado

1. **Cadastro único:** manter conexões, modelos e credenciais no lugar atual. A tela do agente nunca cria conexões nem manipula segredos.
2. **Principal da empresa:** continuar usando `LLMConfig.is_default` e o controle existente. Não criar outro seletor primário concorrente.
3. **Alternativas padrão da empresa:** persistir uma lista ordenada de IDs em configuração tenant-scoped, editada na mesma área de Configurações de modelos. Validar que cada ID pertence ao tenant, não está repetido e não coincide com a principal. Limite recomendado: oito alternativas, igual ao limite do agente.
4. **Campo de habilidades:** adicionar à conexão um campo de texto multilinha editável “Habilidades do modelo”, sem dados secretos, com um item por linha. Usar prefixos claros para separar `Capacidade documentada:` de `Possível tarefa:`. Assim, suporte técnico conhecido e hipótese de adequação não aparecem como a mesma garantia.
5. **Pré-preenchimento:** sugerir/preencher habilidades somente para os nove IDs/modelos conhecidos neste plano. Não sobrescrever informação existente ou escolha manual. Para conexões arbitrárias, iniciar vazio para o usuário cadastrar. Exibir capacidades técnicas conhecidas com fonte oficial e possíveis tarefas como sugestões a validar. O texto não influencia o roteamento automaticamente.
6. **Criar agente:** copiar principal atual e alternativas padrão no backend, na mesma transação. A UI mostra a cadeia herdada e permite personalizá-la antes de salvar. A API distingue herança de edição deliberada sem depender de interpretação ambígua de campos omitidos por clientes antigos.
7. **Agentes existentes:** preservar configurações explícitas. Agentes com `llm_config_id` nulo hoje herdam `is_default` dinamicamente. Fazer backfill aditivo que materialize a principal atualmente efetiva, sem mudar sua rota nem preencher fallbacks. Agentes sem padrão continuam sem principal. Validar idempotência e downgrade antes de implementar.
8. **Alterações/migration/compatibilidade:** bloquear exclusão de conexão usada no padrão da empresa ou rota; desativação mantém vínculo e alerta que o roteador a ignora. Criar migration Alembic nova e aditiva para alternativas e habilidades, sem editar `0003`; validar IDs no backend e preservar o comportamento de clientes legados. Nenhuma conexão ou modelo será seedado por nome.

### Matriz de efeitos

| Operação | Efeito previsto |
|---|---|
| Usuário define uma conexão padrão | Define principal para novas heranças, sem seleção automática pelo sistema. |
| Usuário ordena alternativas padrão | Define a lista copiada para agentes criados depois. |
| Usuário muda a cadeia no agente | Muda somente aquele agente. |
| Usuário muda os padrões da empresa | Não atualiza agentes já criados. |
| Conexão entra em cooldown, falha ou fica desabilitada | Roteador aplica regras atuais à cadeia persistida; não altera a ordem salva. |
| Busca/embeddings são alterados | Não muda rota de geração nem reindexa documentos. |

## Potencial dos nove modelos cadastrados

Esta avaliação combina especificação oficial e o diagnóstico mínimo datado no handoff `docs/handoff/2026-11-13-configuracao-provedores.md`. Os probes foram uma única resposta sintética curta; não comprovam naturalidade pt-BR, qualidade comercial, cumprimento de contrato ou disponibilidade. Nenhum probe foi repetido nesta tarefa.

| Modelo cadastrado | Habilidades técnicas a pré-preencher no cadastro (conforme fonte oficial) | Adequação candidata e acesso observado / ressalvas |
|---|---|---|
| Gemini `gemini-3.5-flash-lite` | Texto, imagem, vídeo, áudio e PDF; saída estruturada, function calling e raciocínio. [Docs](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) | Candidato a alto volume, extração simples e conversa geral. Probe 12,1 s; é o padrão escolhido pelo usuário, não é SLA/benchmark. |
| Groq `qwen/qwen3.8-27b` | Texto/imagem, JSON Schema, ferramentas e raciocínio com modos instruct/thinking. [Modelo](https://console.groq.com/docs/model/qwen/qwen3.8-27b) · [saídas estruturadas](https://console.groq.com/docs/structured-outputs) | Candidato a diálogo de baixa latência e contratos estruturados. Probe 1,4 s; Groq marca preview; validar estabilidade e pt-BR. |
| OpenRouter `openrouter/free` | Texto/imagem; ferramentas e saída estruturada dependem do modelo gratuito escolhido. [Router](https://openrouter.ai/openrouter/free/apps) | Reserva genérica se aceitar identidade variável. Probe respondeu após aumentar limite do diagnóstico; revisar privacidade dos destinos. |
| Gemini Gemma `gemma-4-31b-it` | Texto, imagem e vídeo por quadros; raciocínio e ferramentas; contexto até 256K. A variante 31B não é listada com áudio. [Model card](https://ai.google.dev/gemma/docs/core/model_card_4) | Candidato experimental a resumo/instrução. Probe HTTP 500; canal thought exige sanitização antes de uso. |
| NVIDIA Mistral Large 4 `mistralai/mistral-large-4-1t-a52b` | Texto/imagem, raciocínio, function calling e saída estruturada; contexto 262K. [NVIDIA NIM](https://build.nvidia.com/mistralai/mistral-large-4-1t-a52b) | Candidato a síntese/contexto complexo. Probe expirou em 45 s; medir latência p95 antes de uso síncrono. |
| NVIDIA Step 5 Preview `stepfun-ai/step-5-preview` | Texto/imagem, raciocínio e ferramentas; contexto 1M; endpoint preview. [NVIDIA NIM](https://build.nvidia.com/stepfun-ai/step-5-preview) | Candidato experimental para contexto longo. Probe expirou em 45 s; rever acesso e termos de dados. |
| NVIDIA DeepSeek Flash `deepseek-ai/deepseek-v4.1-flash` | Texto/imagem, function calling e raciocínio; contexto 1M. [NVIDIA NIM](https://build.nvidia.com/deepseek-ai/deepseek-v4.1-flash) | Candidato a contexto extenso. Probe expirou em 45 s; requer avaliação real de latência e qualidade. |
| NVIDIA Nemotron Lightning `nvidia/nemotron-3.5-lightning-30b-a3b` | Texto, contexto até 1M e foco em workflows longos/agentes. [Model card](https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b/modelcard) | Potencial para classificação/extração; probe HTTP 401. Idiomas oficiais não listam português; validar pt-BR e acesso. |
| NVIDIA GPT OSS 20B `openai/gpt-oss-20b` | Texto, raciocínio configurável, ferramentas e saída estruturada; contexto 128K. [Model card](https://build.nvidia.com/openai/gpt-oss-20b/modelcard) | Candidato a classificação/saída textual estruturada; probe HTTP 401. Não expor chain-of-thought. |

Modelos com imagem/áudio/vídeo não habilitam essas modalidades automaticamente: o fluxo atual entrega prompt e histórico textual pelo `model_router.py`/`llm_client.py`. A aplicação precisaria de um caminho multimodal antes de avaliar essa tarefa. NVIDIA trial e quaisquer destinos do OpenRouter também exigem verificação dos termos/retensão antes de enviar dados pessoais reais.

**Busca não é geração:** `openai/text-embedding-3-small`, OpenRouter e 1536 dimensões ficam fora desta lista de roteamento. Não selecionar modelo de chat para embeddings sem suporte e dimensão verificados.

## Qualificação por função do agente

Não classificar modelos apenas por fabricante, número de parâmetros ou benchmark publicado. Comparar os candidatos com o mesmo conjunto de casos sintéticos por perfil:

- **Conversa/SDR:** português brasileiro, concisão, continuidade, uma pergunta útil por vez, não inventar fatos e conduzir ao próximo passo sem pressão.
- **Conhecimento/FAQ:** responder com base no trecho recuperado, diferenciar desconhecido de fato, não fabricar regra/preço e citar/atribuir quando o produto exige.
- **Classificação/contrato:** schema válido, campos allowlist, baixa taxa de resposta vazia e cumprimento de segurança de visita/intervenção.
- **Agente multimodal:** fica bloqueado até o produto encaminhar conteúdo visual/áudio ao modelo.
- **Operação:** sucesso/falha por categoria, cooldown, latência p50/p95, tokens/custo que fornecedor informa, variação em repetições e tamanho de contexto.

Rubrica inicial proposta: 20–30 casos fictícios por perfil, pelo menos três execuções por caso; nota humana 1–5 para naturalidade, continuidade, correção, concisão e adequação comercial; gates de 100% nos casos críticos de segurança e contrato. Limiares de latência/custo devem ser aprovados pela operação. Essa avaliação informa a escolha manual no painel; não muda fallback automaticamente. O botão atual “Testar modelo” verifica conectividade, não qualidade semântica; manter as duas funções separadas e deixar qualquer bateria explícita para evitar cota inesperada.

## Sequência proposta de implementação

1. Aprovar semântica, limite, UX de alternativas da empresa, backfill de agentes implícitos e comportamento da API legada.
2. Criar migration aditiva de alternativas tenant-scoped; testar upgrade/downgrade, backfill e idempotência em PostgreSQL descartável.
3. Criar operações tenant-scoped de leitura/ordenação; admin-only, validação no backend e proteção de exclusão; testar papéis, tenant cruzado e IDs inválidos.
4. Integrar na criação: copiar a principal escolhida e a ordem global como fotografia do agente; edição subsequente não propaga de volta. Preservar edição existente e fallback legado.
5. Atualizar a UI no lugar único de configuração: em Configurações de modelos, manter cadastro de conexão/credenciais, campo “Habilidades do modelo” e ordenação da rota padrão. Na criação/edição do agente, exibir apenas conexões existentes e sua ordem; indicar “padrão da empresa copiado na criação”.
6. Criar qualificação sintética opcional por tarefa, sem dados pessoais e separada do teste de conectividade. Validar JSON, raciocínio não exposto, naturalidade e custo/latência antes de considerar um modelo elegível; resultados podem ajudar a preencher “Possível tarefa” no campo de habilidades.
7. Executar testes unitários, integração, UI e CI; piloto só depois de autorização própria, inicialmente sem alterar conexão padrão nem configurações de agentes existentes.

## Critérios de aceite e reversão

- O usuário segue definindo a conexão principal com o controle atual; nenhum default é escolhido pelo código.
- Conexões e credenciais são cadastradas uma vez em Configurações de modelos. O agente só herda/reordena referências; não tem campos de credencial.
- “Habilidades do modelo” pertence à conexão e permite preenchimento manual e sugestões documentadas; tarefa recomendada é hipótese e não aciona roteamento automático.
- Alternativas padrão da empresa têm ordem editável e são copiadas pelo backend ao criar agente.
- O usuário altera principal/ordem de um agente sem afetar outros ou padrões da empresa.
- Alterações da empresa não atualizam agentes antigos; backfill preserva a rota efetiva de agentes antigos que herdavam dinamicamente.
- Isolamento tenant e proteções de desativar/excluir ficam no servidor; busca segue independente.
- Criar agente, salvar rota ou migrar não chama provedor. Teste técnico e benchmark só ocorrem por ação explícita.
- Rollback não apaga as escolhas persistidas dos agentes; downgrade e estratégia de preservação precisam ser verificados antes do release.

**Fora de escopo:** alterar o Gemini padrão, escolher a cadeia automaticamente pelo sistema, popular fallbacks sem escolha do usuário, mudar o agente Enrico, reconfigurar embeddings/OpenRouter, modificar WhatsApp, chamar APIs de fornecedores, executar migration/produção ou deploy.

## Fontes e limites

Pesquisa feita em 13/11/2026 nas páginas oficiais linkadas em cada linha. Especificações/disponibilidade mudam; benchmarks dos fornecedores não são comparação controlada com o diBBerDesk. Os resultados operacionais são os probes datados no handoff citado e não foram reexecutados.
