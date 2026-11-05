# Núcleo conversacional — branch de testes aprovada

Base: 328e2b083fb48b94bdc489e96886ad4c136b37a0. Aprovação do usuário: executar E0–E5
em branch separada para testes; sem merge/deploy/envios reais. Plano em
../intencoes/atendimento-natural-a-mesa/PLANO-PARA-APROVACAO.md.

## E0 — decisões de reaproveitamento

Mesa consultado somente para leitura, HEAD f9758a043d7ef64b8a44ec259c9913019948c916;
AGENTS.md lido. Nenhuma alteração no repositório fonte. Snapshots dd19753 e commits
449fed5/ac23e89 permanecem referências, não uma afirmação de versão perfeita.
Diff dd19753..HEAD dos módulos mensagemDebounce, humanTakeover,
chunkRespostaWhatsApp, mudancaAssuntoConversa e outputGuard não apresentou mudanças.
O coordenador whatsapp-receber ainda contém gates de ociosidade, catálogo e
interpretação; igualdade dos módulos não prova ausência de regressão no conjunto.

| Origem | Decisão |
|---|---|
| Debounce | Reutilizar agrupamento existente com espera máxima de 20 s, sem buffers em memória como garantia distribuída |
| Chunking | Adaptar preservação de parágrafos/listas; uma divisão persistida, sem cabeçalho/delays aleatórios obrigatórios |
| Takeover | Pausa explícita por conversa, autoria e retomada autorizada; não expirar automaticamente por mensagem manual nem copiar regras pastorais |
| Assunto/retomada | Contexto de turno com validade e instruções de correção; não portar matchers de igreja/cadastro nem gate continuar/nova |
| Humanize/outputGuard | Perfil por agente com flag desligada, texto transparente e limites; não fingir humano nem cortar dados por estilo |
| Memória/RAG | Reusar tabelas atuais; memória sem aprovação não entra no prompt; nenhuma ingestão de acervo por consequência |
| Provedor | Interface de transporte conservando Z-API e política unknown; WaMe/MCP ficam posteriores |

E0 confirma o intervalo inicial de 92–144 h como referência de escopo, não tempo
medido desta execução. Qualidade subjetiva exige avaliador humano; testes de texto
simulado não autorizam declarar ganho medido de naturalidade.

## Limites de arquitetura escolhidos

Novos recursos conversacionais opt-in por agente. A espera máxima limita a janela
de agrupamento; não é SLA de resposta completa nem elimina invalidação por entrada
que chega durante inferência. Controle de cancelamento/opt-out/humano tem prioridade.
Respostas divididas registram partes e recibos individualmente; nenhum reenvio cego
após efeito incerto. Mensagem aceita externamente não pode ser desfeita.

Schema aditivo em novas revisões; drafts não executados. Banco de teste descartável
explicitamente identificado. Nenhuma leitura de docs/Conversas, envio a IA, SSH,
migration ou alteração de serviço da VPS nesta execução.
