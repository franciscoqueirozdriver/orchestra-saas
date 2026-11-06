# Ingestão privada de WhatsApp

Implementação separada em scripts/private_knowledge/pipeline.py. Reutiliza a área
privada e o inventário anterior (inventory.py); não duplica a API de documentos.
A API atual cria embeddings externos e não é adequada ao material bruto. Não há
ponte desta ferramenta para KnowledgeDocument/KnowledgeChunk nem fila Celery da
produção. A fila local durável de transcrições é SQLite, com exclusividade de
processamento por flock. Esta etapa não modifica o schema PostgreSQL da aplicação.

## Separação e segurança

- Originais continuam em docs/Conversas, ignorados por Git e Docker.
- Banco, reconstruções, modelo, inventário e propostas ficam fora do repositório,
  diretórios 700, arquivos de resultados 600. O banco tem dados pessoais brutos;
  requer proteção do computador, backup privado e política de retenção própria.
- Empresa é obrigatória. Sem mapeamento humano, usar unassigned: aprovação bloqueada.
  Não inferir empresa pelo contato. Identificadores de mensagens/fontes são locais.
- Não há HTTP/embeddings na ingestão. Modelo deve estar previamente disponível em
  pasta local. Faster-whisper usa local_files_only, CPU/int8 e flags offline;
  FFmpeg aceita protocolos file/pipe. Não executar em Docker nem montar o acervo.
- Runtime opcional usa requirements.lock deste diretório de scripts; não foi
  acrescentado ao backend/requirements nem à imagem de produção. Modelo não está no Git.
- A aprovação é somente local. Não há exportação/publicação automática para busca.

## Uso repetível

Preparar um virtualenv local fora do repositório (Python 3.9+ e FFmpeg). Instalar
scripts/private_knowledge/requirements.lock. O lock registra o ambiente da amostra,
Python 3.9/Linux; a CI testa o código em Python 3.12, sem exigir os pesos reais.
Baixar previamente o modelo público Systran/faster-whisper-tiny, incluindo model.bin,
config.json, tokenizer.json e vocabulary.txt. Esse download não recebe material privado.

Exemplo sintético, caminhos devem ser adaptados sem publicar nomes pessoais:

```sh
python scripts/private_knowledge/inventory.py /pasta/exportacoes --output /pasta-privada/inventario.json
python scripts/private_knowledge/pipeline.py --db /pasta-privada/staging.sqlite --company EMPRESA ingest /pasta/exportacoes --export-relative export.txt --max-exports 1
python scripts/private_knowledge/pipeline.py --db /pasta-privada/staging.sqlite --company EMPRESA transcribe --source-id 2 --model-path /pasta-privada/modelo
python scripts/private_knowledge/pipeline.py --db /pasta-privada/staging.sqlite --company EMPRESA transcribe-all --model-path /pasta-privada/modelo --threads 2
python scripts/private_knowledge/pipeline.py --db /pasta-privada/staging.sqlite --company EMPRESA classify-authors --staff-name NOME_CONFIRMADO
python scripts/private_knowledge/pipeline.py --db /pasta-privada/staging.sqlite --company EMPRESA identify-phones
python scripts/private_knowledge/pipeline.py --db /pasta-privada/staging.sqlite --company EMPRESA authors --output /pasta-privada/autores.csv
python scripts/private_knowledge/pipeline.py --db /pasta-privada/staging.sqlite --company EMPRESA export-learning-corpus --output-dir /pasta-privada/conhecimento-derivado
python scripts/private_knowledge/pipeline.py --db /pasta-privada/staging.sqlite --company EMPRESA reconstruct --output /pasta-privada/conversa.json
python scripts/private_knowledge/pipeline.py --db /pasta-privada/staging.sqlite --company EMPRESA propose --message-id 1 --kind example --text-file /pasta-privada/candidato.txt
python scripts/private_knowledge/pipeline.py --db /pasta-privada/staging.sqlite --company EMPRESA approve --proposal-id 1 --reviewer REVISOR --confirm-personal-and-factual-review
```

IDs devem ser consultados **localmente** no SQLite, sempre filtrando company. Não
copiar resultados de SELECT com conteúdo para tickets, chat, Git ou logs. A transcrição
é explícita por fonte: o comando ingest inventaria a pasta recursivamente, mas só lê
as exportações selecionadas e não transcreve todo o acervo. max-exports tem padrão 1.
`transcribe-all` carrega o modelo local uma vez, é retomável por fonte e escreve
contadores de progresso sem conteúdo nos logs. `classify-authors` recebe um nome de
equipe confirmado e só classifica o outro participante como cliente quando a
exportação tem exatamente dois autores. `authors` exporta nomes e telefones para CSV
privado; nunca salvar esse arquivo no repositório. Um único telefone distinto no corpo
de uma conversa 1:1 com cliente classificado pode ser associado, com mensagem de origem.
Múltiplos telefones, conflito ou papel desconhecido ficam pendentes de revisão.
`export-learning-corpus` grava uma cópia sanitizada e limitada em tamanho para revisão
humana; os arquivos não são indexados automaticamente.
O comando reconstruct preserva todas as versões históricas por source_id; consumidores
não devem misturá-las como uma única conversa nem assumir que uma substituiu outra.
Os outputs recusam sobrescrita; use outro nome para uma reconstrução posterior.

## Persistência, vínculos e retomada

As migrações SQLite 0001–0004 são exclusivas deste staging, fora do Alembic de
produção. Tabelas incluem fontes, mensagens, anexos, autores por conversa, cartões
de contato, candidatos de associação, transcrições, segmentos e propostas.
SHA256/empresa/caminho/versão identificam fontes;
ordem pertence à exportação, data original fica textual, sem presumir fuso, século
ou interpretação de data ambígua. Fontes alteradas ganham revisão, sem apagar antigas.

Parser suporta cabeçalhos Android/iOS e continuações multilinha. Mensagens de sistema
ficam sem autor; não há diarização da fala. O autor do envio não é necessariamente o
falante do áudio. Autores têm identificador próprio dentro da exportação; nomes iguais
não são unidos entre conversas. Um telefone no campo de autor é normalizado para
associação posterior; telefones citados no corpo não vinculam automaticamente uma
pessoa. Referências explícitas e nome isolado vinculam apenas arquivo da
mesma pasta. Caracteres de direção invisíveis são removidos da referência, não do
original. Nomes em prosa, horário próximo, anexos ocultos, arquivos ausentes e nomes
ambíguos não autorizam associação. Não extrai conhecimento de PDF/imagens/VCF nesta
fase; esses arquivos são inventariados e vinculados quando explicitamente citados.

Retomada reutiliza transcrição concluída para mesma fonte e receita: versão,
faster-whisper, hash dos artefatos do modelo, parâmetros e versão do FFmpeg.
Interrupções/erros podem ser retomados; segmentos entram numa transação, sem saída
parcial concluída. flock local evita dois processos de inferência sobre o mesmo
banco. Não usar esse banco em filesystem de rede ou compartilhado entre máquinas.
Erros persistidos são classes/códigos, não stderr ou conteúdo privado.

Vínculos de uma exportação já parseada são preservados. Se um anexo ausente aparecer
depois, a reavaliação de vínculos exige uma nova versão de processamento explícita;
não renomear/anexar arquivos silenciosamente a uma revisão aprovada.

## Conhecimento factual e atendimento humanizado

Propostas são seleção explícita, com mensagens de origem; não há classificação por
IA nem transformação automática de todo histórico em regras. Categoria fact é
**candidata**, não afirmação atual. Categoria example também exige revisão: remover
pessoas, contatos, situações identificáveis, falhas de atendimento e instruções
inadequadas antes de aprovar. Texto recebido não tem autoridade sobre o sistema.

Redação automática mascara autores conhecidos na empresa, e-mails, links e sequências
numéricas. É auxílio conservador e pode mascarar valores úteis ou deixar nomes de
terceiros, endereços e dados sensíveis. Não é anonimização certificada. O revisor deve
reformular o conteúdo, verificar consentimento/finalidade e validar privacidade.
Não há reconhecimento de rostos, OCR, diarização ou interpretação visual.
Fatos exigem confirmação atual e validade futura em --valid-until AAAA-MM-DD. Preços,
prazos e instruções históricos não viram regras atuais. Expiração precisa ser
reconferida em eventual publicação futura. approved_local nunca significa indexed.

## Amostra executada em 05/11/2026

Recursos observados: Intel i3-N305, 8 CPUs, RAM total 7,4 GiB / disponível ~1,6 GiB;
GPU não utilizável. tiny multilíngue, CPU/int8, 2 threads, beam 1, português explícito,
sem VAD, sem contexto entre janelas; processamento sequencial.

Inventário anterior: 1.213 arquivos, 33 pastas, ~500 MB. Triagem privada encontrou
56 textos e 14 exportações com referências literais a áudio e vídeo. Escolheu-se
uma conversa curta entre essas, sem inferir empresa: unassigned.

- Amostra: 33 fontes inventariadas, 79 mensagens, 33 vínculos explícitos resolvidos.
- Somente 1 áudio e 1 vídeo transcritos; demais mídias permanecem pendentes.
- Áudio: duração 11,69 s; processamento 1,56 s; 3 segmentos; nenhum avg_logprob < -1.
- Vídeo: duração 30,44 s; processamento 6,87 s; 11 segmentos; **todos avg_logprob < -1**.
- Segunda execução reutilizou ambos, sem duplicar segmentos. O primeiro download
  incompleto do modelo gerou erros preservados; nova receita completa concluiu.
- 1 citação histórica candidata a fact e 1 diálogo candidato a example, ambos
  pending_review e bloqueados para aprovação enquanto empresa não atribuída.

Tempos de inferência incluem preparação FFmpeg/carregamento, não instalação/download.
Não extrapolar para 500 MB com duas mídias. Pontuação interna não é taxa de acerto;
sem referência humana não há WER nem precisão medida. O vídeo exige revisão por
escuta e comparação com modelo maior quando houver memória, antes de uso. Áudio
sem alerta também exige revisão. Sem VAD podem ocorrer alucinações em música/silêncio.

**Transcrever a fala do vídeo não equivale a interpretar suas imagens.** Não se
conclui intenção, produto exibido, texto em tela ou identidade de falantes.

## Atualização do processamento integral

A empresa do acervo foi confirmada. O staging privado contém 61 cópias/exportações
textuais (60 hashes distintos), 8.013 linhas incluindo mensagens de sistema e 7.799
mensagens de participantes. Autores foram separados por conversa: 59 autores de
equipe identificados pelo nome de equipe confirmado pela responsável, 59 clientes inferidos
somente como contraparte em exportações 1:1 e dois autores sem papel. Isso classificou
4.159 mensagens como equipe, 3.583 como cliente e manteve 57 sem papel. A identidade
de cada autor continua local à exportação; nomes iguais não foram unidos entre
históricos.

Das 791 mídias, 785 têm transcrição local concluída pelo modelo tiny: 738 áudios e 47
vídeos. Seis vídeos não têm faixa de áudio; não há fala para transcrever. O staging
mantém 4.733 segmentos. 428 ficaram abaixo do limiar interno de confiança e exigem
escuta/revisão; essa pontuação não mede acurácia. A inferência foi local, sem envio a
provedores. Os arquivos privados não foram copiados para Git/Docker nem para a
VPS/produção.

O histórico completo foi reconstruído em JSON privado, e uma cópia de aprendizado
com 59 diálogos e 7.721 mensagens foi gerada em quatro arquivos privados. Exportações
idênticas foram deduplicadas apenas nessa cópia; permanecem no staging com sua
proveniência. Os oito telefones únicos encontrados em mensagens ficaram vinculados
com evidência; sete candidatos conflitantes ou ambíguos aguardam revisão. O histórico
ainda não foi associado a chaves de contato da integração. A cópia de aprendizado
exige revisão de privacidade e qualidade antes de qualquer indexação. Nenhum dos dois
foi importado na produção. Veja [uso duplo das conversas](uso-duplo-conversas.md).

## Validação

Fixtures exclusivamente sintéticas cobrem parser, multilinha/datas, caracteres
invisíveis, vínculos certos/ausentes/ambíguos/ocultos, ausência de associação por
proximidade/prosa, retomada, revisão de fonte, transcrição fake com segmentos/erros,
isolamento por empresa, aprovação e destinos privados. Smoke real da amostra não
é teste de acurácia. Contrato de inferência local conferido no
[código oficial do faster-whisper](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py).

Na validação atual, **19 testes locais passaram**, com fixtures sintéticas;
`git diff --check` também passou. Isso não mede a qualidade semântica das transcrições.
Os resultados persistentes ficam em diretório privado fora do repositório. O SQLite
de staging é a fonte de proveniência; a reconstrução integral e a cópia de aprendizado
mais recentes foram geradas no processamento de 06/11. Backups de estágio e resultados
anteriores permanecem separados para auditoria e não devem substituir a versão atual.
O [handoff](../handoff/2026-11-06-publicacao-e-ingestao.md) registra contagens,
limitações, publicação e próximos passos.
