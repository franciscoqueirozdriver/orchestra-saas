# Conexões de IA e expansão de provedores

Em **Modelo IA**, cadastre uma conexão para cada combinação de fornecedor,
modelo e credencial. Os presets incluem Gemini, Groq, Mistral, OpenRouter,
OpenAI, xAI e Anthropic. São atalhos de preenchimento, não uma lista fechada.
Informe o identificador de um modelo disponível na sua conta; o painel não
consulta catálogos externos automaticamente.

Para adicionar outro fornecedor, escolha **Outro provedor / personalizado**,
informe um identificador, a URL HTTPS base, o protocolo, o modelo e a chave.
São suportados Chat Completions, Responses, Gemini nativo e Anthropic Messages.
A URL base não deve terminar no caminho de uma operação, como
`/chat/completions`. Endereços privados e redirecionamentos são recusados pelo
cliente de execução. Um fornecedor com outro protocolo ou autenticação exige
adaptador de código e testes de contrato; selecionar um nome não cria suporte.

Em **Agentes**, selecione a conexão principal ou o padrão da empresa. Adicione
alternativas e ordene sua prioridade. O motor utiliza os vínculos configurados,
respeitando disponibilidade e classificação de erros. Uma alternativa não é uma
garantia de resposta: todos os fornecedores podem falhar. Conexões em uso ou
definidas como padrão não podem ser excluídas.

### Fonte da ordem de geração

O painel e o banco do tenant são a fonte de verdade para a seleção em runtime.
`agents.llm_config_id` escolhe a principal do agente; `agents.fallback_config_ids`
guarda a ordem das alternativas. O roteador mantém essa ordem, ignora conexões
desabilitadas, pula cooldowns e tenta a próxima conexão quando um erro permite
fallback. Se o agente não tem principal explícita, usa a conexão padrão da empresa
antes das alternativas. O catálogo de provedores apenas preenche campos do
formulário: não escolhe modelos, não altera conexões existentes e não testa saldo.

Não existe seed de conexões de IA nem migration com uma cadeia de modelos por
empresa. Isso é intencional: o código não deve alterar o modelo padrão ou a ordem
salva no painel. Fixtures de teste podem criar uma cadeia sintética para comprovar
roteamento sem gravar valores de produção, IDs reais ou chaves.

## Chaves e busca de conhecimento

As chaves são criptografadas no armazenamento e nunca são retornadas pela API.
Ao editar, chave vazia mantém a atual. Alterar a URL de geração exige informar
a chave novamente, evitando encaminhar a credencial antiga a outro destino.

A busca tem configuração própria em **Conhecimento → Configurar busca**.
Enquanto não houver configuração própria, utiliza os embeddings da conexão
padrão da empresa por compatibilidade. Consulte
[armazenamento e busca](conhecimento/armazenamento-e-busca.md). A dimensão
atual é 1536 e o transporte de embeddings é compatível com OpenAI. Gemini e
Anthropic nativos precisam de endpoint e chave de embeddings separados.

Trocar o fornecedor de geração preserva a configuração anterior de embeddings
quando os campos de embeddings não foram editados. Se necessário, a credencial
anterior é preservada separadamente para esse transporte. Com documentos
indexados, mudanças de URL/modelo de embeddings e mudanças de padrão para uma
configuração diferente são bloqueadas. Exigem planejamento de reindexação;
não se deve misturar vetores de modelos diferentes, mesmo com dimensão igual.

Uma mesma conexão OpenRouter pode ser vinculada tanto a `fallback_config_ids`
de um agente como a `knowledge_search_configs.connection_id`. São vínculos
independentes: retirar a conexão do fallback não remove a busca, e trocar a
conexão da busca não altera a cadeia de geração. A chave é mantida uma única vez
na conexão; excluir a conexão permanece bloqueado enquanto qualquer desses
vínculos existir. Embeddings ainda precisam de modelo compatível com `/embeddings`
e 1536 dimensões; o fato de uma conexão gerar texto não comprova essa capacidade.

O modelo `openrouter/free` tem uma cota de requisições de modelos gratuitos, não
uma cota de tokens faturados: a documentação atual do OpenRouter informa limites
de 20 requisições/minuto e 50/dia na faixa gratuita, e tentativas falhas contam
para esse limite diário. A mesma documentação diz que tentativas com erro não
são cobradas como tokens de inferência. A conexão e chave podem ser compartilhadas
entre geração e busca, mas os limites/preços dependem do endpoint e modelo; não
assuma que chamadas de embeddings consomem a cota de requisições de `openrouter/free`.
Confira o painel de atividade do OpenRouter para atribuição de uso. Fontes:
[modelos gratuitos e limites](https://openrouter.ai/collections/free-models),
[preços e faturamento](https://openrouter.ai/pricing) e
[API de embeddings](https://openrouter.ai/docs/api/api-reference/embeddings/create-embeddings).

## Extensão e limites de homologação

Novos atalhos ficam em `backend/app/provider_catalog.py`. Novos protocolos ficam
no cliente de IA, acompanhados de testes de autenticação, payload, resposta,
erros, timeout e isolamento por empresa. Não é necessária migration para novas
conexões nos protocolos existentes.

Os testes usam dados sintéticos, HTTP simulado e PostgreSQL descartável.
Cadastrar uma conexão não valida saldo, permissão do modelo ou disponibilidade
real. A homologação externa deve usar conta e destinatário de teste autorizados.
Nenhuma mensagem real é enviada pelo cadastro ou pelos testes de interface.

Referências de contrato: [Gemini](https://ai.google.dev/gemini-api/docs/openai),
[Mistral](https://docs.mistral.ai/api),
[OpenRouter](https://openrouter.ai/docs/api-reference/overview) e
[Anthropic Messages](https://platform.claude.com/docs/en/api/messages).
