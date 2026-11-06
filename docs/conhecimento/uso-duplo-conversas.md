# Dois usos para o histórico de conversas

O mesmo acervo alimenta duas finalidades diferentes. A aplicação deve manter a
proveniência para que uma finalidade não substitua a outra.

## Histórico individual do contato

- Preservar as mensagens originais, autor, sequência, data textual, empresa e
  vínculos explícitos com mídias no staging privado.
- Cada autor recebe um identificador estável dentro da exportação. Nomes iguais
  em conversas diferentes não são unidos automaticamente.
- Quando a exportação traz o telefone como autor, normalizar o número e registrá-lo
  como identidade telefônica. Um único telefone distinto no corpo de uma conversa
  individual com um cliente classificado pode ser associado com a mensagem de origem.
  Múltiplos telefones, conflito com outro número ou papel indefinido ficam pendentes.
- Depois que o WhatsApp estiver conectado, associar o histórico à conversa ativa
  pelo telefone confirmado e pelo identificador recebido da integração. O nome da
  agenda ajuda a revisar a associação; não é chave suficiente sozinho.
- Importar esse histórico para as conversas do tenant permitirá que mensagens
  futuras recuperem o contexto da mesma pessoa. Essa ponte para o banco de produção
  ainda exige implementação, vínculo verificado e operação de importação auditável.

## Conhecimento geral de atendimento

- Gerar uma cópia derivada com os papéis de equipe/cliente, preservando a sequência
  e o contexto útil de cada diálogo.
- Remover nomes, telefones e demais identificadores da cópia enviada à busca geral.
  A proteção automática ajuda, mas não substitui revisão humana de conteúdo livre,
  áudio, documentos e imagens.
- Usar os exemplos para recuperar formas de conduzir a conversa, perguntas úteis,
  explicações e transições. Uma fala antiga não confirma preço, estoque, política ou
  instrução atual.
- Conhecimento factual só fica elegível após confirmação pela empresa, validade e
  aprovação. Exemplos de conversa são uma categoria distinta de fatos.
- Nenhum documento deste corpus é indexado automaticamente. O upload ao indexador
  externo é uma etapa separada, feita apenas para o material derivado revisado.

## Estado da implementação

O staging local mantém mensagens originais e autores por conversa em SQLite privado.
As migrações desse banco são próprias do staging e não pertencem ao Alembic de
produção. O lote foi transcrito localmente quando havia faixa de áudio; seis vídeos
sem áudio não geraram transcrição. Há segmentos que requerem revisão humana, e fala
transcrita de vídeo não significa interpretação visual. A cópia derivada de exemplos
está pronta apenas para revisão privada, não para indexação automática.

A aplicação já guarda mensagens de conversas ativas separadas por tenant e chave de
contato. A importação do histórico antigo e o uso conjunto desse histórico no
contexto de uma conversa ainda não foram executados na produção.
