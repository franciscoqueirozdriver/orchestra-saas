# Documentos e busca independentes

Em Conhecimento, Enviar documento salva o texto extraído e os metadados da
empresa, sem exigir modelo de conversa, chave ou chamada externa. O arquivo
original não é retido. Formatos e limites de extração continuam os mesmos.
O status `pending_index` aparece como **Aguardando indexação**. Documentos nesse
estado não entram na busca nem impedem respostas por falta de embeddings.

Em **Configurar busca**, cadastre URL HTTPS base, modelo de embeddings de 1536
dimensões e chave. O serviço deve aceitar o contrato OpenAI `/embeddings`.
A chave é criptografada e não é retornada ao painel. Chave vazia preserva a
configuração própria atual; endpoint novo exige chave novamente. Salvar esta
configuração não envia dados para fornecedores. Não há catálogo automático.

**Indexar para busca** é uma ação explícita que envia o texto ao serviço
configurado. O painel pede confirmação dessa transmissão. Quando termina, o
status é `indexed`, mostrado como **Disponível para busca**. Falhas preservam o
texto salvo e permitem nova tentativa. Chamadas concorrentes são serializadas
por empresa; repetir a indexação concluída não duplica os trechos.

As credenciais da busca são independentes das conexões dos agentes. Para
compatibilidade, enquanto não existir configuração própria, a configuração
legada da conexão IA padrão continua sendo usada. A tela identifica essa origem.
Para migrar, informe explicitamente a chave no formulário da base. Se já houver
índices, preserve URL/modelo; trocar o espaço vetorial exige planejamento de
reindexação. Não há reindexação nem envio automático na migration.

A revisão `0006_knowledge_storage` acrescenta texto extraído aos documentos e
uma tabela de configuração por empresa. Documentos antigos indexados continuam
utilizáveis, embora não tenham o texto original reconstruído. Não se tenta
inventar o original a partir de trechos sobrepostos. O downgrade recusa remover
texto salvo ou configurações existentes. Em reversão operacional, prefira as
imagens anteriores com schema aditivo preservado; não reverta o banco cegamente.

Conteúdo de documentos e chaves são dados privados. A publicação leva apenas
código, migration e documentação. Testes usam documentos sintéticos e transporte
simulado; disponibilidade, credenciais e modelos reais exigem homologação.

## Reaproveitar conexão cadastrada

Em Configurar busca, escolha uma conexão da empresa e informe o **modelo de
embeddings**. URL e chave manuais ficam ocultas. A API guarda apenas o vínculo,
a URL derivada e o modelo; não duplica a chave. A credencial atual da geração é
lida da conexão selecionada somente no servidor, inclusive após rotação.
A chave de embeddings legada da conexão não é usada silenciosamente nesse modo.
Configuração manual continua disponível para credenciais independentes.

Gemini sugere `gemini-embedding-001` e deriva `/v1beta/openai` da URL nativa.
As requisições ao endpoint oficial Google pedem 1536 dimensões e os vetores são
normalizados. O nome do modelo de conversa não é usado para indexar documentos.
Outros fornecedores precisam oferecer embeddings compatíveis; selecionar uma
conexão não confirma modelo, quota ou disponibilidade real.

A conexão não pode ser excluída enquanto estiver vinculada à busca. Desativação
ou mudança de endpoint faz a busca recusar o uso até revisão; não encaminha uma
chave automaticamente para um novo destino. Mudança de espaço vetorial com
índices existentes continua bloqueada. Isso não implementa fallback entre
modelos de embeddings diferentes.

A revisão aditiva `0007_search_connection` não altera configurações existentes.
Seu downgrade recusa referências ativas. **Reversão para código anterior após
criar vínculos exige antes restaurar uma configuração manual equivalente**, com
credencial cifrada, revisão/backup e autorização, ou publicar correção à frente.
O código anterior não sabe resolver a referência; apenas voltar a imagem não
mantém a busca vinculada funcionando. Não executar downgrade automático.
