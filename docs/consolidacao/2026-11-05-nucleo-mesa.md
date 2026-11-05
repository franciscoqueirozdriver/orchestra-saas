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

## Implementação na branch

| Etapa | Entrega técnica | Limite de validação |
|---|---|---|
| E0 | Histórico e referência conferidos; decisões acima; corpus de 20 entradas/estados sintéticos | Comparação de código, sem reimplantar/executar o sistema Mesa nem afirmar ausência de regressões nele |
| E1 | Cancelamento e humano prioritários no opt-in; janela com teto; takeover/resume e envio humano idempotente; ações com autoria e revisão otimista | Controle de conversa não cancela pedido/compra; retomar aguarda novo inbound, sem religar envios/consentimento |
| E2 | Turnos persistidos, request anterior, validade, correções e histórico rotulado de operador; esclarecimento repetido limitado | Sinais conservadores, não classificador semântico completo nem motor de fluxos de negócio; coerência depende do modelo |
| E3 | Perfil administrativo por agente: tom, concisão, emojis, vocabulário, exemplos revisados e limites; configuração invalida pendências | Não há aferição de qualidade com modelos reais; guard não é prova de correção factual |
| E4 | Uma outbox por resposta e partes duráveis; revalidação por parte, correlação de eco e recibos, agregação de status e rate limit por parte | Presença Z-API ainda indisponível: adaptador retorna false; falha opcional não bloqueia texto; não há WaMe |
| E5 | Testes unitários, PostgreSQL, Chrome com API fictícia, CI e roteiro de revisão | Avaliação humana e piloto real continuam pendentes; nenhum envio externo realizado |

Schema novo 0005_conversation_core: perfil JSON, contexto e início de turno,
autoria, ações/turnos, partes e aprovação explícita em memory_items. Constraints
compostas impedem associar turno/ação/parte a outra empresa. Instalação e upgrade
não atribuem agente, aprovam memória ou habilitam o núcleo. A configuração é opt-in.

Memórias antigas ficam preservadas, com approved=false, e deixam de entrar no
prompt até revisão. Não há CRUD/painel avançado de aprovação nesta entrega; isso
permanece separado. Não alterar o banco real à mão para contornar esse bloqueio.
Documentos continuam no fluxo administrativo existente; nada do staging de conversas
foi publicado na busca. Antes de ativar qualquer piloto, revisar também as pendências
antigas da outbox: não presumir que uma resposta gerada antes desta revisão já atende
à política de conteúdo atual.

Downgrade recusa dados em turnos/ações/partes, perfis configurados, memórias aprovadas
e cadeia incompatível de múltiplos modelos. Reversão preferencial por flag e código
compatível, mantendo schema/dados e reconciliando aceites/unknown antes de outro
sender. Nunca executar o dispatcher antigo junto com o novo.

O lock de sessão por empresa permanece; tem limite de throughput e exige conexão
direta/afinidade de sessão. Aceite/entrega/leitura continuam distintos. Mensagem
já aceita pelo fornecedor pode chegar mesmo depois de o operador pedir pausa.
O controle de taxa usa registros recentes de tentativas e pode ser conservador
quando callbacks atualizam o estado. Medir latência/carga antes de ampliar uso.

## Como revisar com segurança

1. Consultar a branch feature/nucleo-conversacional-mesa e a PR; não fazer merge ou
   rodar deploy para experimentar as alterações.
2. Testes de API/banco reproduzíveis pelo workflow .github/workflows/validate.yml:
   banco orchestra_consolidation_test descartável; nunca substituir pelo DSN real.
   Unitários devem usar ambiente test, OUTBOUND_ENABLED=false e configuração
   sintética; não carregar o .env da VPS. Os testes locais desta entrega montaram
   apenas snapshot dos arquivos de código permitidos, sem dados privados.
3. Para o browser sintético: instalar playwright-core@1.56.1 em pasta temporária e
   executar NODE_PATH=/pasta-temporaria/node_modules node tests/ui/conversation-panel.cjs.
   Requer Chrome; usa perfil novo, serve apenas frontend em loopback e intercepta
   todas as chamadas da API. Requisições externas são abortadas. Não usa login real.
4. Num futuro ambiente de homologação separado, configurar perfil opt-in por agente,
   verificar tom e botões de assumir/responder/retomar. A mudança de perfil não
   habilita agente, instância ou envio global automaticamente.
5. Usar os 20 casos sintéticos de tests/fixtures/conversation_cases.json e a matriz
   de aceitação histórica. Preparar diálogos completos com fonte factual fictícia
   e avaliar clareza, continuidade, repetição e tom com pessoas. O corpus executável
   atual testa políticas/estado; não é uma avaliação de respostas de um LLM.
6. Homologação de modelo/provedor real e destinatários requer autorização própria.
   Não usar acervo privado como fixture, prompt de teste externo ou fonte automática.

## Proteção e validação

Nenhum arquivo de docs/Conversas rastreado; exclusões Git/Docker mantidas. Nenhum
original, transcrição, conteúdo de contato ou resultado da amostra foi lido/copiado
nesta etapa. Nenhuma chamada a provedor LLM/WhatsApp ou serviço da VPS foi realizada.
Dependências de teste instaladas somente em /tmp. Banco novo descartável em rede
interna, sem portas publicadas e sem volumes de dados reais; outros serviços locais
não foram alterados.

Ver o resultado do CI no SHA da PR para os totais finais. Passaram localmente os
contratos anteriores, novos casos de estado/chunking/perfil, integrações de partes,
callbacks, takeover, concorrência, isolamento, memória pendente excluída e cadeia de
migração. Chrome validou perfil, takeover, erro dentro do modal, retry idempotente e
resume com API sintética. As 33 verificações documentais dos snapshots passaram.

Pendências externas à validação técnica: revisão humana de naturalidade, comparação
com modelo real, latência/carga representativa, operação de unknown, homologação de
Z-API/presença e piloto autorizado. Áudio online, ferramentas, WaMe, MCP e publicação
do acervo permanecem fora desta branch de execução.

## Preparação da primeira publicação autorizada

Após autorização do usuário para publicar, o primeiro acesso SSH foi recusado pelo
agente local (assinatura da chave indisponível). Nenhuma alteração remota ou merge
foi executado nessa tentativa. É necessário desbloquear a chave no terminal local,
sem compartilhar passphrase em chat.

A conferência do helper detectou incompatibilidade com Compose legado sem scheduler:
consulta direta a serviço inexistente pode falhar antes da verificação opcional.
Corrigido inventário para consultar primeiro os nomes declarados; ausência de serviço
obrigatório continua sendo recusada. Dois testes sintéticos cobrem esse bootstrap.
