# Intervenção humana pelo grupo da equipe

## Fluxo implementado

Cada conexão WhatsApp pode ser configurada para notificar um grupo de atendimento. A organização cria o grupo no WhatsApp ou, quando a conexão oferece esse recurso, aciona **Criar grupo via API** no painel. O botão não cita fornecedor: a plataforma decide se ele aparece pela capacidade da conexão, não pelo nome do provedor. A ação é sempre manual e exige um administrador, os participantes e confirmação antes da chamada. Convites privados ficam desligados por padrão; ativá-los exige confirmação adicional. O conector atual exige ao menos um participante e pede para não incluir na lista o próprio número conectado que cria o grupo. [Contrato de criação de grupos usado pelo conector atual](https://z-api-docs.vercel.app/group/create-group).

Depois da criação, a plataforma registra o identificador retornado e os números de participantes como autorizados a assumir. A organização ainda deve conferir os membros e pode editar a lista de autorizados. Para grupos criados fora da plataforma, o administrador informa manualmente o identificador e os números autorizados. A criação não valida nem ativa alertas.

Antes de habilitar alertas, um administrador envia uma mensagem de teste real pelo painel e confirma que ela chegou ao grupo correto. Até essa confirmação, o encaminhamento permanece pendente e o sistema não envia alertas de intervenção para o grupo.

Quando o cliente pede uma pessoa, o sistema pausa a automação, cria um código de seis dígitos com validade de 60 minutos e, se o grupo estiver validado e os envios estiverem liberados, publica somente o código e a instrução de aceite. A automação também pode pedir intervenção quando não consegue concluir uma resposta com segurança após tentativas de esclarecimento ou quando a geração da IA falha.

O atendente responde **em privado** ao número conectado usando `ASSUMINDO 123456`. O backend confere a lista de números autorizados, a validade e o estado do código. O primeiro aceite processado fica atribuído ao número do atendente; a trava por empresa serializa aceitações concorrentes. O sistema envia o contexto recente da conversa em privado e o atendente continua pelo painel diBBerDesk, em **Conversas**. Uma segunda pessoa recebe a informação de que o caso já foi assumido.

## Estados e limites

- Grupo novo ou alterado: `pending`; exige novo teste e confirmação da organização.
- Teste aceito pelo provedor: `test_sent`; a organização ainda precisa confirmar recebimento no grupo correto.
- Grupo confirmado: `validated`; alertas podem ser encaminhados.
- Chamado: `awaiting_claim`, `claimed`, `expired` ou `setup_required`.
- O código expira após 60 minutos. Só números cadastrados podem assumir. A alteração do grupo ou da lista de atendentes revoga a validação anterior.
- O envio do alerta e da resposta privada respeita as pausas de envio global e da instância.
- A mensagem de teste é uma mensagem real e só é enviada após ação explícita de um administrador no painel.
- O alerta do grupo não contém telefone, nome ou histórico do cliente. O contexto é montado na hora do aceite a partir das mensagens da conversa e enviado privadamente; ele não é duplicado na tabela de chamados.
- Mensagens recebidas em grupos são ignoradas e removidas do payload persistido do webhook. O comando de aceite privado também tem seu payload removido após processamento.
- A confirmação do painel é uma declaração da organização de que viu o teste no grupo; a API não verifica a presença individual dos atendentes no grupo.
- O provedor pode aceitar o envio e depois não entregar. A organização deve validar a chegada do teste no WhatsApp. Os alertas operacionais registram a aceitação HTTP do provedor, não confirmação de leitura.
- Erros de envio deixam a conversa pausada; não há repetição automática de um envio cujo efeito externo seja ambíguo.

## Homologação pendente

O conector atual envia texto para o identificador do grupo e lê os campos `isGroup` e `participantPhone` do webhook, conforme o [envio de texto](https://z-api-docs.vercel.app/message/send-message-text) e as [mensagens recebidas](https://z-api-docs.vercel.app/webhooks/on-message-received) desse contrato. A conexão alternativa usa o mesmo fluxo de grupo, alerta e aceite, com o adaptador descrito em [conexões WhatsApp](conexoes-whatsapp.md). O fluxo ainda precisa ser homologado pela organização em um grupo de teste real antes da ativação.
