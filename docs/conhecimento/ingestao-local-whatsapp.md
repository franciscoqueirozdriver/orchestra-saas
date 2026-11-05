# Ingestão privada de WhatsApp — amostra local

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
python scripts/private_knowledge/pipeline.py --db /pasta-privada/staging.sqlite --company EMPRESA reconstruct --output /pasta-privada/conversa.json
python scripts/private_knowledge/pipeline.py --db /pasta-privada/staging.sqlite --company EMPRESA propose --message-id 1 --kind example --text-file /pasta-privada/candidato.txt
python scripts/private_knowledge/pipeline.py --db /pasta-privada/staging.sqlite --company EMPRESA approve --proposal-id 1 --reviewer REVISOR --confirm-personal-and-factual-review
```

IDs devem ser consultados **localmente** no SQLite, sempre filtrando company. Não
copiar resultados de SELECT com conteúdo para tickets, chat, Git ou logs. A transcrição
é explícita por fonte: o comando ingest inventaria a pasta recursivamente, mas só lê
as exportações selecionadas e não transcreve todo o acervo. max-exports tem padrão 1.
O comando reconstruct preserva todas as versões históricas por source_id; consumidores
não devem misturá-las como uma única conversa nem assumir que uma substituiu outra.
Os outputs recusam sobrescrita; use outro nome para uma reconstrução posterior.

## Persistência, vínculos e retomada

Migration SQLite 0001_private.sql é exclusiva deste staging, fora do Alembic de
produção. Tabelas: sources, messages, attachments, transcriptions, segments,
proposals e proposal_messages. SHA256/empresa/caminho/versão identificam fontes;
ordem pertence à exportação, data original fica textual, sem presumir fuso, século
ou interpretação de data ambígua. Fontes alteradas ganham revisão, sem apagar antigas.

Parser suporta cabeçalhos Android/iOS e continuações multilinha. Mensagens de sistema
ficam sem autor; não há diarização da fala. O autor do envio não é necessariamente o
falante do áudio. Referências explícitas e nome isolado vinculam apenas arquivo da
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

O acervo completo não foi processado. Próxima decisão: confirmar empresa/subpastas,
revisar a amostra por escuta, corrigir redação pessoal e avaliar tiny versus base/small
com folga de memória, antes de autorizar lote maior. Nenhum dado foi à VPS/produção.

## Validação

Fixtures exclusivamente sintéticas cobrem parser, multilinha/datas, caracteres
invisíveis, vínculos certos/ausentes/ambíguos/ocultos, ausência de associação por
proximidade/prosa, retomada, revisão de fonte, transcrição fake com segmentos/erros,
isolamento por empresa, aprovação e destinos privados. Smoke real da amostra não
é teste de acurácia. Contrato de inferência local conferido no
[código oficial do faster-whisper](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py).

Nesta entrega, **15 testes locais passaram** (13 da ingestão e 2 da proteção anterior),
com fixtures sintéticas; validação de sintaxe Python e git diff --check também passou.
Os dados persistentes ficam em /home/Alessandra/Documentos/orchestra-private/ingestao-amostra-20261105:
sample-v2.sqlite é o banco válido; sample-reviewed-structure.json é a reconstrução
com proveniência/alertas; summary.json contém somente métricas agregadas. Tentativas
anteriores permanecem separadas para auditoria, não devem ser usadas como versão final.
