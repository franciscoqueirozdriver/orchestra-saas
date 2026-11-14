# Índice de handoffs e fontes de continuidade

Preserve documentos históricos. Este índice indica escopo e confiabilidade temporal;
não os transforma em retrato atual. Atualize-o ao adicionar handoffs relevantes.

## Handoffs de sessão

| Documento | Escopo | Como usar |
|---|---|---|
| [`docs/handoff/2026-11-06-publicacao-e-ingestao.md`](../handoff/2026-11-06-publicacao-e-ingestao.md) | Publicação autorizada, pipeline privado e importação histórica; inclui números e estado operacional datados | Fonte histórica detalhada; não tomar SHA/revisão/serviços como atuais sem conferência |
| [`docs/handoff/2026-11-09-auditoria-continuidade.md`](../handoff/2026-11-09-auditoria-continuidade.md) | Auditoria deste snapshot, documentos examinados, divergências e validação da documentação | Usar para entender origem dos arquivos canônicos desta auditoria |
| [`docs/handoff/2026-11-10-envio-humanizado.md`](../handoff/2026-11-10-envio-humanizado.md) | Implementação local opt-in de respostas em blocos via outbox, testes e limitações do ambiente | Conferir branch e estado Git no próprio handoff; não representa publicação ou homologação |
| [`docs/handoff/2026-11-10-contexto-conversacional-global.md`](../handoff/2026-11-10-contexto-conversacional-global.md) | Contexto estruturado global, confirmação contextual de contato, recebedor de visita e prevenção de falsa confirmação | Mudança local em `feat/enrico-context-booking`; consultar resultados, limitações e Git final; não representa deploy |
| [`docs/handoff/2026-11-10-tentativa-sincronizacao.md`](../handoff/2026-11-10-tentativa-sincronizacao.md) | Tentativa inicial de publicação de `main`, quando GitHub/VPS estavam inacessíveis | Registro histórico, supersedido quanto ao estado atual pelo handoff de publicação abaixo |
| [`docs/handoff/2026-11-10-publicacao-enrico.md`](../handoff/2026-11-10-publicacao-enrico.md) | Correção da divergência local/GitHub, CI, release na VPS, backup, schema e verificações pós-publicação | Registro do release `1f7d1a8`; saída global desativada; homologação de atendimento permanece pendente |
| [`docs/handoff/2026-11-11-interpretacao-contextual-enrico.md`](../handoff/2026-11-11-interpretacao-contextual-enrico.md) | Interpretação semântica pelo modelo, preservação da resposta contextual e publicação | Release `cf2ed78` verificado na VPS; saída automática desativada; homologação com provedor real pendente |
| [`docs/handoff/2026-11-11-controle-automacao-conversa.md`](../handoff/2026-11-11-controle-automacao-conversa.md) | Painel por conversa para diagnosticar e operar pausas globais, de conexão, agente, contato e outbox | Implementação local em `feat/automation-control-panel`; não testada em suíte, não publicada e não verificada na VPS |
| [`docs/handoff/2026-11-12-resiliencia-saida-estruturada.md`](../handoff/2026-11-12-resiliencia-saida-estruturada.md) | Regressão de saída JSON inválida em visitas; fallback semântico antes da intervenção, diagnóstico e validação local | Branch `feat/semantic-llm-fallback`, base `465d6b3e`; local apenas, sem provider real, push, merge ou deploy |
| [`docs/handoff/2026-11-12-revisao-memoria-e-avaliacao.md`](../handoff/2026-11-12-revisao-memoria-e-avaliacao.md) | Cursor de resumo com desempate estável, autorização para excluir fatos comerciais e corpus sintético de avaliação de respostas | Branch local `test/conversational-core-onda1`; commit inicial `725679e`, alterações ainda não commitadas/não publicadas |
| [`docs/handoff/2026-11-13-teste-conexao-modelo.md`](../handoff/2026-11-13-teste-conexao-modelo.md) | Teste curto ao salvar conexão, renovação da sessão de login e publicação | PRs #12/#13 integradas; SHA `33c9268` publicado na VPS. A renovação foi testada sinteticamente; sessão de usuário real permanece sem validação |
| [`docs/handoff/2026-11-13-configuracao-provedores.md`](../handoff/2026-11-13-configuracao-provedores.md) | Registro de configuração de provedores, papéis compartilhados do OpenRouter, limites observados e testes sintéticos | Branch `feat/provider-config-reproducibility`; não altera seleção de modelos nem dados de produção; conferir estado Git/PR antes de usar como atual |
| [`docs/handoff/2026-11-13-planejamento-roteamento-modelos.md`](../handoff/2026-11-13-planejamento-roteamento-modelos.md) | Proposta de alternativas padrão da empresa, cópia da conexão escolhida pelo usuário ao criar agente e avaliação documental dos nove modelos | Plano não implementado; branch `plan/company-model-routing`; conferir aprovação e Git antes de executar |
| [`docs/handoff/2026-11-14-exclusao-documentos-conhecimento.md`](../handoff/2026-11-14-exclusao-documentos-conhecimento.md) | Botão administrativo para excluir documento e trechos da base, com confirmação; testes locais e status de publicação | Conferir SHA/PR/VPS no handoff antes de tratar como publicado; documento `base-conhecimento-agentes.md` do checkout principal ficou fora do escopo |

O handoff de 06/11 evoluiu em commits `d8d04b3`, `a07dc7d` e `621d926` (importação
histórica), culminando no arquivo atual. Use `git show <commit>:<caminho>` se for
necessário recuperar exatamente uma versão anterior; não confunda as versões com
handoffs independentes.

## Consolidações e relatórios de mudanças

| Documento | Foco |
|---|---|
| [`docs/consolidacao/2026-11-05.md`](../consolidacao/2026-11-05.md) | Resgate e comparação entre local, GitHub e VPS; evidência operacional da data |
| [`docs/consolidacao/2026-11-05-revisao-pr1.md`](../consolidacao/2026-11-05-revisao-pr1.md) | Testes de atribuição, scheduler, contratos, concorrência e limitações da revisão |
| [`docs/consolidacao/2026-11-05-nucleo-mesa.md`](../consolidacao/2026-11-05-nucleo-mesa.md) | Decisão de reaproveitamento de núcleo conversacional e limites |
| `docs/consolidacao/busca-conexao-cadastrada.md` | Configuração da busca com conexão de IA existente |
| `docs/consolidacao/conhecimento-armazenamento-indexacao.md` | Separação entre armazenamento de documento e indexação |
| `docs/consolidacao/provedores-configuraveis.md` | Histórico da configuração de provedores |

## Referências canônicas por assunto

- Estado e stack: [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) e [`CURRENT_STATE.md`](CURRENT_STATE.md).
- Fluxo de mensagens WhatsApp ponta a ponta: [`MESSAGE_FLOW.md`](MESSAGE_FLOW.md), com referências a rotas, workers, transportes e testes.
- Decisões e limites: [`DECISIONS.md`](DECISIONS.md) e [`KNOWN_RISKS.md`](KNOWN_RISKS.md).
- Inicialização e handoff futuro: [`CONTINUITY_PROTOCOL.md`](CONTINUITY_PROTOCOL.md).
- CI: [`.github/workflows/validate.yml`](../../.github/workflows/validate.yml) executa pytest, integração Alembic/PostgreSQL descartável, verificações de shell/Compose, build Docker e testes de UI sintéticos. O arquivo define o que roda; só uma execução remota confirma o resultado de um SHA.
- Publicação: [`docs/fluxo-local-github-vps.md`](../fluxo-local-github-vps.md) e `scripts/release.py`.
- Segurança operacional: `docs/security-and-operations.md`.
- Histórico de conversa e ingestão privada: arquivos `docs/conhecimento/`, `docs/historico-whatsapp.md` e handoff 06/11. Material bruto é privado e não deve ser lido por padrão.
- Atendimento e migrations propostas de A Mesa: `docs/intencoes/atendimento-natural-a-mesa/`; documentos e código proposto ali não significam que tudo foi incorporado.
- Intervenção humana: `docs/intervencao-humana-grupo.md` e implementação referenciada em `CURRENT_STATE.md`.
- Rota de geração empresa/agente: [`docs/planos/2026-11-13-roteamento-modelos-empresa-e-agentes.md`](../planos/2026-11-13-roteamento-modelos-empresa-e-agentes.md); proposta não implementada. A conexão principal continua sendo escolhida pelo usuário em Modelo IA.
- WhatsApp: `docs/conexoes-whatsapp.md`; verificar sua data e contrastar com código/contrato externo.

## Outros documentos históricos/temáticos

`README.md`, `docs/architecture-proposal.md`, `docs/arquitetura.md`,
`docs/diagnostico-e-plano-2026-10-30.md`, `docs/implementation-plan.md`, os dois
arquivos `TODO*`, `docs/providers-and-hosting.md`, `docs/provedores-ia.md`,
`docs/deploy-hostinger.md`, `docs/security-and-operations.md`, `docs/historico-whatsapp.md`,
`docs/marca/identidade-dibberdesk.md`, documentos em `docs/contratacao/` e `tests/README.md`
foram localizados. São fontes específicas ou snapshots; confronte alegações de status
com o código e a referência temporal antes de usar.
