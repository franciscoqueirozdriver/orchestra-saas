# Conexões WhatsApp

A tela **Conexões WhatsApp** mostra dois fornecedores. Cada um oferece dois modelos: **API oficial** e **API não oficial (QR Code)**.

| Fornecedor | API não oficial (QR Code) | API oficial |
| --- | --- | --- |
| Z-API | Implantado. ID da instância, token e token de cliente se o painel mostrar. | Ainda não implantado. A tela mostra a oferta e impede o cadastro. |
| WAME | Implantado. No painel: **Server** e **Key**. | Implantado. Os mesmos **Server** e **Key**. |

Depois de salva, a conexão usa o mesmo atendimento, o mesmo envio, o mesmo webhook e a mesma criação manual de grupo. O botão continua **Criar grupo via API**.

Não há segredo devolvido pela API. O tipo fica na coluna `provider`:

- `zapi` — Z-API, API não oficial (QR Code)
- `wame_qr` — WAME, API não oficial (QR Code)
- `wame_official` — WAME, API oficial
- `wame` — conexão WAME salva antes da escolha de modelo

A URL **Server** da WAME fica em `api_base_url` (migration `0010_wame_api_base_url`).

## Z-API

A API oficial da Z-API ainda não tem conector nesta plataforma.

Para a API por QR Code, crie a instância no painel da Z-API.

| Onde nasce | Onde colar no diBBerDesk |
| --- | --- |
| ID da instância | ID da conexão |
| Token da instância | Credencial de acesso |
| Token de cliente, se o painel exibir | Credencial adicional. Se não existir, deixe vazio |

Não cole o token no campo de ID. Depois de salvar, use **Callbacks**. Se a plataforma não confirmar o registro, cadastre a URL mostrada nos callbacks de mensagens recebidas do fornecedor. A URL contém o segredo de callback e não deve ir para o Git nem para um ticket.

## WAME

No painel da WAME só aparecem **Server** e **Key**. Nome e ID da conexão não existem lá: invente-os nesta tela.

| Onde nasce | Onde colar no diBBerDesk |
| --- | --- |
| Server (ex.: `https://us.api-wa.me`) | Server |
| Key | Chave da instância |
| Inventado aqui | Nome de identificação |
| Inventado aqui | ID da conexão. Letras, números, `_` ou `-`. Não cole a Key |

Escolha nesta tela se a conexão é a API oficial ou a API por QR Code. A mesma Key vale para os dois.

Deixe desligada, no painel da WAME, a opção **Exigir token de acesso** (`Authorization: Bearer`). O conector autentica pela Key no endereço da API e não envia esse cabeçalho. Ligar a opção interrompe envio, status, webhook e criação de grupo.

Ao salvar, a plataforma registra o webhook no formato de mensagens, inclusive as mensagens enviadas pelo próprio número, para o aceite `ASSUMINDO`. A Key não entra nesse endereço. O webhook que chega continua exigindo o segredo próprio da plataforma.

Instagram, Messenger e Telegram que usem a mesma Key são confirmados e não viram conversa neste painel.

Na API oficial, a Meta pode recusar texto livre fora da janela de 24 horas. O painel envia o mesmo texto que já envia hoje. Modelos aprovados não fazem parte desta etapa.

Se uma conexão antiga não tiver Server salvo, o conector usa `WAME_API_BASE_URL` (padrão `https://server.wame.api.br`). Conexões novas devem colar o Server do painel. A da Z-API continua em `ZAPI_API_BASE_URL`.
