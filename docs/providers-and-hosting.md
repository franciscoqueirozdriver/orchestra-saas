# Notas de implementação — Hostinger, Groq e xAI

## Hostinger KVM 2

A tabela oficial consultada lista o KVM 2 com 2 vCPU, 8 GB de RAM, 100 GB de disco, 8 TB de banda e I/O indicado de 300 MB/s. A Hostinger também informa que os VPS podem usar 100% das vCPU alocadas enquanto houver créditos de CPU; quando os créditos se esgotam, a capacidade disponível cai temporariamente para 20% da capacidade alocada e retorna conforme os créditos se recompõem. O painel da conta contratada é a fonte final de valores, pois parâmetros/planos podem mudar.

**Implicação de arquitetura:** executar PostgreSQL com pgvector, Redis, API, um worker e proxy web na mesma VPS é adequado como início controlado, com limites de memória/concorrência e monitoramento. Não executar inferência de LLM pesada, embedding local ou processamento de mídia pesado no KVM 2; usar serviços externos configurados por tenant. A VPS é um único domínio de falha e não dá alta disponibilidade por si só.

Fonte oficial: [Parâmetros e limites dos planos Hostinger](https://www.hostinger.com/support/6976044-parameters-and-limits-of-hosting-plans-in-hostinger/).

## Groq

A documentação oficial descreve a API Groq como majoritariamente compatível com clientes OpenAI e indica base URL `https://api.groq.com/openai/v1` com a chave Groq como `api_key`. A compatibilidade não é total; a página enumera campos não suportados, como `logprobs`, `logit_bias`, `top_logprobs` e `messages[].name`.

A documentação da Groq descreve a Responses API como beta, com suporte a entrada de texto/imagem e function calling; o cliente deve manter o histórico porque as conversas stateful ainda não são suportadas. Na página consultada, ferramentas built-in browser search e code interpreter são suportadas apenas por `openai/gpt-oss-20b` e `openai/gpt-oss-120b`.

**Implicação de arquitetura:** permitir Groq como opção configurável para inferência/LLM compatível, guardar a chave no backend e manter o histórico/checkpoints no PostgreSQL/LangGraph. Não presumir suporte a todos os parâmetros ou ferramentas do contrato OpenAI. A configuração de Responses API/ferramentas deverá ser um adaptador distinto, não uma simples troca de base URL.

Fontes oficiais: [Groq OpenAI compatibility](https://console.groq.com/docs/openai); [Groq Responses API](https://console.groq.com/docs/responses-api).

## xAI: ferramentas gerenciadas e servidores MCP

A documentação oficial xAI divide ferramentas em ferramentas built-in executadas nos servidores do provedor (por exemplo, Web Search, X Search, Code Interpreter, Image Generation e Collections Search) e function calling para funções próprias. A documentação diz que preço de ferramentas pode incluir tokens e chamadas de ferramenta.

A API xAI documenta Remote MCP com `server_url`, `server_label`, `allowed_tools` e, opcionalmente, Authorization/headers; são suportados transportes Streaming HTTP e SSE. A documentação recomenda HTTPS e limitar `allowed_tools`: sem a lista, todas as ferramentas expostas pelo servidor MCP ficam disponíveis ao modelo. Os parâmetros `require_approval` e `connector_id` no OpenAI Responses API não são suportados atualmente, segundo a página consultada.

**Implicações de segurança:** (1) não expor execução de código, escrita em CRM/ERP, exclusão, envio de mensagens ou outros efeitos sensíveis por padrão; (2) construir allowlist server-side por tenant/ferramenta; (3) validar novamente autorização e argumentos no serviço próprio antes de qualquer mutação; (4) pedir aprovação humana no produto para ações de impacto, sem depender de um parâmetro do xAI API que a documentação diz não suportar; (5) manter credenciais de MCP próprias por tenant, cifradas no banco e nunca no prompt/logs; (6) revisar consentimento, retenção e transferência de dados, pois chamadas e contexto são processados pelo provedor externo. Para a primeira versão, recomendar ferramentas somente de leitura (por exemplo, busca) e deixar code execution desabilitado.

Fontes oficiais: [xAI tools overview](https://docs.x.ai/developers/tools/overview); [xAI remote MCP tools](https://docs.x.ai/developers/tools/remote-mcp).


## Z-API — contrato efetivamente usado nesta versão

- **Enviar texto:** `POST https://api.z-api.io/instances/{instanceId}/token/{token}/send-text`, JSON `{ "phone": "...", "message": "..." }`; a documentação recomenda telefone sem máscara e descreve `zaapId`, `messageId` e `id` na resposta 200. O status HTTP inicial não prova entrega.
- **Consultar instância:** `GET https://api.z-api.io/instances/{instanceId}/token/{token}/status`, header `Client-Token` quando habilitado/configurado; a resposta documenta `connected`, `error` e `smartphoneConnected`.
- **Configurar callback de recebimento:** `PUT https://api.z-api.io/instances/{instanceId}/token/{token}/update-webhook-received`, header `Client-Token` e JSON `{ "value": "https://..." }`. A Z-API aceita somente callbacks HTTPS.
- **Callback recebido:** exemplo de texto usa `type: "ReceivedCallback"`, `instanceId`, `messageId`, `phone`, `fromMe`, `momment`, `status`, `senderName`/`chatName` e `text.message`; mídias vêm em objetos próprios como `image.imageUrl` e `audio.audioUrl`. Nesta versão, o webhook persiste um subconjunto minimizado, não armazena URLs de mídia, e só responde automaticamente a texto individual recebido.
- A documentação consultada não caracteriza no callback uma assinatura criptográfica universal; a implementação acrescenta um token aleatório próprio na URL e o mantém somente como hash no banco. Isso é autenticação por segredo de URL/defesa adicional, não assinatura nativa Z-API.

Fontes oficiais: [Enviar texto](https://developer.z-api.io/message/send-message-text); [Status da instância](https://developer.z-api.io/instance/status); [On Message Received](https://developer.z-api.io/en/webhooks/on-message-received); [exemplos de callbacks recebidos](https://developer.z-api.io/en/webhooks/on-message-received-examples).
