# Histórico de conversas do WhatsApp

## Onde aparece

Depois da importação, abra **Conversas** no Orquestra e selecione a conversa. A linha do tempo mostra as mensagens anteriores com autor, direção e data original. Mensagens importadas levam a indicação **Histórico**. Se a exportação não continha a data de uma mensagem, a tela informa **Data ausente no arquivo**; a ordem daquela origem é mantida.

Conversas identificadas por telefone ficam vinculadas ao telefone confirmado no material. A aplicação também registra aliases para reconciliar identificadores de telefone e LID recebidos posteriormente pelo WhatsApp. Registros sem telefone confirmado permanecem visíveis como conversas históricas separadas e não são unidos por mera semelhança de nome.

## Efeito no atendimento

Mensagens históricas de clientes e da equipe podem compor o contexto recente do agente quando houver nova mensagem naquela conversa. Registros de sistema e mensagens sem autor confirmado ficam visíveis, mas não são enviados como fala de cliente ou da equipe ao modelo. O contexto continua limitado pela janela de histórico configurada no agente.

A importação marca conversas sem histórico de consentimento como `history_only` e `consent_status=unknown`. A primeira mensagem real recebida pode associar aliases e retirar a marca de histórico. Isso não altera, por si só, a política de envio, o estado global de envio ou as permissões do contato.

## Proveniência e reprocessamento

O importador `python -m app.history_import` recebe JSONL por entrada padrão. Sem `--apply`, apenas valida o tenant, a instância, hashes, ordem e metadados. A gravação é transacional e idempotente por tenant e hash de origem. Cada lote registra hash, versão do processamento, fuso horário e quantidade de mensagens; cada mensagem guarda lote, ordinal e data original.

O exportador local `scripts/private_knowledge/pipeline.py ... export-history-for-application` gera o JSONL com permissão `0600` fora do repositório. O arquivo, originais, transcrições e banco de staging são dados privados: não os adicione ao Git, imagens Docker, logs ou documentação. A sincronização deve transportar o arquivo diretamente pela entrada padrão do contêiner, sem copiá-lo para o checkout ou para o GitHub.

Transcrições locais de áudio são inseridas como texto do anexo com marca de revisão pendente e timestamps de segmentos. Para vídeo, apenas o áudio pode ter transcrição; imagens do vídeo não são interpretadas. Imagens e documentos anexados ficam representados por marcadores, sem copiar os arquivos ao banco da aplicação.

## Publicação

Uma publicação deve usar `scripts/release.py` com SHA revisado, branch limpa na VPS, revisão de banco esperada e backup verificado. A migration `0008_historical_conversations` não pode ser revertida depois que houver lotes ou aliases: o downgrade recusa para proteger histórico e proveniência. Não execute a migration diretamente fora do procedimento de release.
