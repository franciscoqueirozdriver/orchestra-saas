# Conexões WhatsApp

A tela **Conexões WhatsApp** é o lugar em que a empresa escolhe o fornecedor e cola as credenciais. Depois de salva, a conexão usa o mesmo atendimento, o mesmo envio, o mesmo webhook e a mesma criação manual de grupo. O rótulo do botão continua **Criar grupo via API**.

Não há migration nova para a segunda conexão. O tipo fica na coluna `provider`, já existente: `zapi` ou `wame`. A chave é criptografada e a API não a devolve.

## WhatsApp via API

Crie a instância do número no painel desse fornecedor.

| Onde nasce | Onde colar no diBBerDesk |
| --- | --- |
| ID da instância | ID da conexão |
| Token da instância | Credencial de acesso |
| Token de cliente, se o painel exibir | Credencial adicional. Se não existir, deixe vazio |

Não cole o token no campo de ID. Depois de salvar, use **Callbacks**. Se a plataforma não confirmar o registro, cadastre a URL mostrada nos callbacks de mensagens recebidas do fornecedor. A URL contém o segredo de callback e não deve ir para o Git nem para um ticket.

## WhatsApp via API alternativa

Ative a instância no painel desse fornecedor. A mesma chave vale para o canal oficial e para a conexão por QR.

| Onde nasce | Onde colar no diBBerDesk |
| --- | --- |
| Chave da instância | Chave da instância |
| Identificador interno, escolhido aqui | ID da conexão. Letras, números, `_` ou `-`. Não cole a chave |

Deixe desligada, no painel do fornecedor, a opção **Exigir token de acesso** (`Authorization: Bearer`). O conector autentica pela chave no endereço da API e não envia esse cabeçalho. Ligar a opção interrompe envio, status, webhook e criação de grupo.

Ao salvar, a plataforma registra o webhook no formato de mensagens, inclusive as mensagens enviadas pelo próprio número, para o aceite `ASSUMINDO`. A chave não entra nesse endereço. O webhook que chega continua exigindo o segredo próprio da plataforma.

Instagram, Messenger e Telegram que usem a mesma chave são confirmados e não viram conversa neste painel.

No canal oficial, a Meta pode recusar texto livre fora da janela de 24 horas. O painel envia o mesmo texto que já envia hoje. Modelos aprovados não fazem parte desta etapa.

A base padrão do conector alternativo é `https://server.wame.api.br`, substituível por `WAME_API_BASE_URL`. A do conector atual continua em `ZAPI_API_BASE_URL`.
