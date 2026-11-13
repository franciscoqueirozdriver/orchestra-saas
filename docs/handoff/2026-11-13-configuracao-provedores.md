# Handoff — configuração de provedores sem sobrescrever o painel

**Data:** 13/11/2026
**Base:** `main` / `origin/main`, `702827502f534c39fc2dd8daeaefbe098b40accf`.
**Branch:** `feat/provider-config-reproducibility`.
**Escopo:** documentar e testar roteamento dinâmico de provedores e uso compartilhado
da conexão OpenRouter. Nenhuma seleção de modelo, valor de tenant ou dado de produção
é alterado por esta mudança.

## Estado conferido

Uma consulta somente de leitura à VPS confirmou as nove conexões exibidas pelo
responsável. A conexão padrão da empresa continua Gemini `gemini-3.5-flash-lite`.
Os modelos e protocolos observados no banco foram:

| Conexão no painel | Modelo | Protocolo |
|---|---|---|
| NVIDIA - Mistral Large 4 | `mistralai/mistral-large-4-1t-a52b` | OpenAI-compatible / chat-completions |
| Gemini | `gemini-3.5-flash-lite` | Gemini |
| Groq | `qwen/qwen3.8-27b` | Chat Completions |
| OpenRouter | `openrouter/free` | Chat Completions |
| Gemini Gemma | `gemma-4-31b-it` | Gemini |
| NVIDA - Step 5 | `stepfun-ai/step-5-preview` | OpenAI-compatible / chat-completions |
| NVIDIA - DeepSeek Flash | `deepseek-ai/deepseek-v4.1-flash` | OpenAI-compatible / chat-completions |
| NVIDIA - Nemotron Lightning | `nvidia/nemotron-3.5-lightning-30b-a3b` | OpenAI-compatible / chat-completions |
| NVIDIA - GPT OSS | `openai/gpt-oss-20b` | OpenAI-compatible / chat-completions |

O modelo padrão da empresa não foi alterado. A principal e a ordem de fallback do
agente também não foram gravadas ou modificadas por esta tarefa; a política ativa
continua sendo a que estiver salva na ferramenta/painel. A busca apontava para a
conexão OpenRouter e `openai/text-embedding-3-small`; foram observados 6 documentos
indexados e 18 trechos. Não foram lidos conteúdos, chaves ou prompts.

## Implementação e decisões

- `candidate_configs` já lê a principal e a lista ordenada do agente; não há fallback
  codificado por marca/modelo. Alterar uma conexão no painel não muda as demais.
- Nenhum seed de conexões por tenant foi encontrado. Nenhuma migration foi criada:
  a seleção depende do painel e as conexões exigem credenciais privadas. Fixtures
  sintéticas são a fonte de configuração dos testes.
- Adicionados contratos sintéticos para os nove identificadores acima, usando
  seus protocolos salvos e sem chamadas reais. O teste de fallback também comprova
  uma cadeia sintética de cinco conexões, incluindo cooldown e erros 429, 402 e
  401. Ele prova a ordem somente quando configurada no agente; não altera o default
  nem impõe uma cadeia aos tenants.
- Coberto o uso de uma única conexão OpenRouter como fallback de geração e vínculo
  de busca. Remover um vínculo não remove o outro, e salvar repetidamente a mesma
  configuração de busca mantém um único registro.
- A API fixa 1536 dimensões, e o transporte recusa vetores com outra dimensão com
  erro explícito. O teste agora verifica a mensagem.
- `.env.example` não contém nomes de modelos/provedores de geração; os modelos e a
  ordem permanecem no painel. Não foi alterado.

## OpenRouter: limites e cobrança

O mesmo vínculo de conexão pode usar a mesma credencial em geração e busca. Isso
compartilha conta/chave, não transforma embeddings e geração em uma só operação ou
em uma quota idêntica. A documentação atual do OpenRouter informa 20 req/min e 50
req/dia para variantes gratuitas na conta sem compra de créditos; tentativas com
erro contam para o limite diário. A página de preços diz que falhas não são
cobradas como tokens de inferência. Embeddings podem ter modelo/preço/contabilização
próprios; não foi afirmado que `/embeddings` consome o limite diário de
`openrouter/free`. Fontes oficiais: [modelos gratuitos](https://openrouter.ai/collections/free-models),
[preços](https://openrouter.ai/pricing) e [API de embeddings](https://openrouter.ai/docs/api/api-reference/embeddings/create-embeddings).

## Riscos, reversão e aplicação

- O código não registra contagem de tokens/custo nem tentativas de embeddings em
  `model_runs`; o painel de atividade do provedor é necessário para atribuição de
  consumo.
- Configurar Gemma ou OpenRouter no fallback não valida quota, credencial ou
  conformidade semântica de resposta. A homologação de provedores continua separada.
- A PR contém somente testes e documentação; não há migration, seed de produção,
  alteração de `.env`, configuração de tenant, reinício ou deploy. Aplicá-la não
  muda os dados atuais.
- Reversão: reverter o commit/PR de código e documentação; não há downgrade de
  banco nem alteração a restaurar na VPS. A ordem de modelos continua a que estiver
  salva no painel.

## Validação

Suíte completa em container Python 3.12, com PostgreSQL/pgvector descartável, Git
disponível para os testes do release guard, `MEDIA_DIR` temporário e código-fonte
montado somente leitura: **320 passed, 2 skipped**. Os dois skips são os testes de
consolidação de migrations que requerem uma baseline original adicional.
`git diff --check` também passou. Nenhum teste automatizado chamou provedores.

Foi feita separadamente uma verificação real, não persistente, em 13/11/2026:
uma chamada curta (`Responda somente: OK`) para cada conexão. Não foram criados
`ModelRun`, mensagens ou alterações no banco. As chamadas externas podem contar
para cota/cobrança do fornecedor. Resultado observado:

| Modelo | Resultado da chamada de diagnóstico |
|---|---|
| `mistralai/mistral-large-4-1t-a52b` | Timeout local de 45 s; acesso não confirmado |
| `gemini-3.5-flash-lite` | Resposta não vazia; 12,1 s |
| `qwen/qwen3.8-27b` | Resposta não vazia; 1,4 s |
| `openrouter/free` | Primeira chamada truncada pelo teto de 16 tokens do diagnóstico; repetida com 64 tokens e respondeu em 1,0 s |
| `gemma-4-31b-it` | HTTP 500; acesso funcional não confirmado |
| `stepfun-ai/step-5-preview` | Timeout local de 45 s; acesso não confirmado |
| `deepseek-ai/deepseek-v4.1-flash` | Timeout local de 45 s; acesso não confirmado |
| `nvidia/nemotron-3.5-lightning-30b-a3b` | HTTP 401; autenticação/acesso não confirmado |
| `openai/gpt-oss-20b` | HTTP 401; autenticação/acesso não confirmado |

Os timeouts vieram do timeout configurado no cliente. O teste registra somente
categoria/status e duração; o corpo remoto, chaves e texto de resposta não foram
impressos. Esses probes confirmam somente o resultado momentâneo de uma requisição
mínima, não qualidade, estabilidade, política de quota nem compatibilidade com
respostas comerciais reais. Os modelos com timeout, HTTP 500 e HTTP 401 exigem
revisão separada no painel do fornecedor antes de serem considerados utilizáveis.

Também foi feito um probe separado do endpoint de embeddings selecionado em
Conhecimento, usando um único texto sintético, sem indexar nem persistir: `openai/text-embedding-3-small`
retornou vetor com **1536 dimensões** em 416 ms. Isso confirma o contrato técnico
do embedding no momento do teste, não indexa nem reprocessa documentos.

## Próximo trabalho separado

O responsável definiu a direção para uma tarefa posterior: manter principal e
fallback globais como padrão da empresa, copiar essa ordem ao criar um agente e
permitir ao usuário personalizá-la no próprio agente. Alterar o padrão global não
deve sobrescrever agentes existentes. Essa tarefa deve avaliar a fonte do padrão,
compatibilidade com agentes já configurados, UX e testes de herança/edição. Também
foi solicitado pesquisar o potencial e os pontos fortes dos modelos cadastrados e
indicar adequação por tarefa de agente. Nenhuma dessas mudanças faz parte desta PR.

## Próxima ação

Revisar este diff e a CI; revalidar no painel a ordem pretendida antes de qualquer
alteração operacional. Merge e deploy não fazem parte desta etapa.
