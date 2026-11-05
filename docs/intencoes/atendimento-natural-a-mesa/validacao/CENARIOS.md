# Aceitação — atendimento natural

## Corpus mínimo com dados fictícios

| Caso | Entrada/condição | Resultado esperado |
|---|---|---|
| Fragmentação | “Oi” → “queria saber” → “o horário”, em menos de 3s | Uma resposta ao pedido completo; sem três cumprimentos |
| Entrada contínua | Fragmentos por mais de 30s | Teto de espera definido, nenhuma mensagem perdida |
| Saudação + pedido | “Bom dia, qual o horário?” | Responder ao horário usando evidência, sem ignorar o pedido |
| Cancelamento | “Cancela” enquanto a IA trabalha | Invalidar revisão anterior e partes ainda não enviadas |
| Interrupção | Nova pergunta após primeira bolha | Bloquear bolhas obsoletas e tratar o turno novo |
| Negação útil | “Não. Quero o endereço, não o horário” | Preservar o novo pedido; não descartar após “não” |
| Correção | “Não foi isso que eu pedi” | Recuperar pergunta/resposta vinculadas e tentar corrigir |
| Ambiguidade | Resposta ainda incompreensível após uma clarificação | Não repetir o mesmo gate indefinidamente |
| Troca de assunto | Pergunta lateral durante um fluxo | Responder/alternar sem reinterpretar como valor de campo |
| Retomada | Retorno depois da janela de contexto | Não usar filtro antigo silenciosamente; perguntar só se necessário |
| Follow-up | “E os de amanhã?” após consulta de horários | Usar intenção/filtro anterior com fonte atual |
| Áudio | Áudio válido em PT-BR | Transcrever, agregar ao turno e responder; sem alegar ouvir quando falha |
| Áudio hostil | URL privada, redirect privado, arquivo gigante ou MIME falso | Recusar com segurança e orientação textual |
| Humano | “Quero falar com alguém” | Registro de fila/takeover real, IA suspensa conforme política |
| Sem humano | Fila não configurada/indisponível | Informar limite sem prometer retorno inexistente |
| Transparência | “Você é uma pessoa?” | Informar que é assistente automatizado sem fallback de estilo |
| Texto extenso | Resposta com parágrafos, lista e nomes | Partes ordenadas, sem perder itens e sem truncar no meio |
| Repetição legítima | Mesma pergunta em outro turno | Responder; dedup não bloqueia pedido legítimo |
| Replay | Mesmo webhook recebido duas vezes | Uma persistência e uma resposta por revisão |
| Ferramenta | Pergunta exige dado real não disponível | Não inventar; pedir dado/encaminhar de modo verdadeiro |
| Ferramenta com escrita | Pedido sem permissão/sem confirmação | Não executar; nem por fallback de outro provedor |
| Memória | Correção do usuário ainda pendente | Não publicar como verdade para outros contatos/empresas |
| Opt-out | Pedido de parar comunicações | Atualizar permissão; campanha e pending dispatch respeitam política |
| Falha de presença | send-presence falha | Texto continua sem revelar token/URL |

## Integração e concorrência obrigatórias

- Dois workers disputam o mesmo evento, turno e primeira parte: um único claim válido.
- Nova mensagem/cancelamento/takeover durante geração, presença e intervalo entre bolhas.
- Lease vencido com envio externo ambíguo: nenhum replay cego; reconciliação explícita.
- Aceite, entrega e leitura fora de ordem: estado monotônico, sem confundir aceite com entrega.
- Crash depois de persistir evento e antes de enfileirar: reconciliação encontra órfão.
- Redis indisponível: fonte de verdade preservada e operação falha de maneira visível.
- Tenant A tenta atribuir agente, anexar turno, mídia, ferramenta, memória ou outbox do B:
  API nega e constraints novas rejeitam referências cruzadas.
- Todos os tokens, callback secrets, áudio/URLs e prompts permanecem fora de logs comuns.
- Upgrade de banco existente e instalação nova produzem schema compatível, inclusive inicial
  histórica Alembic, backfill, ownership e serviço não-superuser.
- Rollback de código com flags desligadas não reenvia respostas já enviadas por partes.

## Comparação histórica

Usar `dd19753` como referência consultável, com commits de correção `449fed5` e
`ac23e89` já incluídos. Construir corpus separado dos bugs documentados no v5:
loop de retomada, relatório errado por matcher amplo, repetição de resposta,
negação que apaga o pedido. Não usar logs pessoais como fixtures públicas.

Avaliar A Mesa histórico, A Mesa atual e Orquestra com os mesmos diálogos fictícios.
Registrar modelo, prompt, versão, flags, latência e avaliação humana cega quando
possível. Medir conclusão do pedido, correção factual, clarificações desnecessárias,
repetição, continuidade e tamanho/ritmo. Não inventar pontuação antes do piloto.

## Estado de validação desta pasta

`verificar_prototipo.py` valida somente exemplos Python e integridade dos snapshots.
Ele não homologa SQL, TypeScript, WhatsApp, modelos, permissões nem experiência real.
