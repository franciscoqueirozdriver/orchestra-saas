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

## Extensão e limites de homologação

Novos atalhos ficam em `backend/app/provider_catalog.py`. Novos protocolos ficam
no cliente de IA, acompanhados de testes de autenticação, payload, resposta,
erros, timeout e isolamento por empresa. Não é necessária migration para novas
conexões nos protocolos existentes.

Os testes usam dados sintéticos, HTTP simulado e PostgreSQL descartável.
Ao salvar uma conexão, a aplicação envia pelo backend um prompt técnico curto ao
modelo salvo e apresenta sucesso ou erro categorizado. A tela também tem um botão
**Testar modelo** para repetir a verificação em conexões existentes. O resultado
não altera principal, alternativas, cooldown ou busca e não é persistido em
`model_runs`; a conexão permanece salva mesmo quando o teste falha. As credenciais
e o corpo bruto do fornecedor não são devolvidos nem registrados pela rota. Cada
teste é uma chamada externa e pode consumir quota/custo. Esse teste confirma apenas
que a conexão respondeu naquele momento, não qualidade, saldo futuro ou adequação
para atendimento real. Nenhuma mensagem de WhatsApp é enviada.

Os testes automatizados usam apenas dados sintéticos, HTTP simulado e PostgreSQL
descartável; não chamam fornecedores reais. Homologação de comportamento comercial
deve ser feita separadamente com conta e destinatário de teste autorizados.

Referências de contrato: [Gemini](https://ai.google.dev/gemini-api/docs/openai),
[Mistral](https://docs.mistral.ai/api),
[OpenRouter](https://openrouter.ai/docs/api-reference/overview) e
[Anthropic Messages](https://platform.claude.com/docs/en/api/messages).
