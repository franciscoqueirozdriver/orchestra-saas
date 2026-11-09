# Índice de handoffs e fontes de continuidade

Preserve documentos históricos. Este índice indica escopo e confiabilidade temporal;
não os transforma em retrato atual. Atualize-o ao adicionar handoffs relevantes.

## Handoffs de sessão

| Documento | Escopo | Como usar |
|---|---|---|
| [`docs/handoff/2026-11-06-publicacao-e-ingestao.md`](../handoff/2026-11-06-publicacao-e-ingestao.md) | Publicação autorizada, pipeline privado e importação histórica; inclui números e estado operacional datados | Fonte histórica detalhada; não tomar SHA/revisão/serviços como atuais sem conferência |
| [`docs/handoff/2026-11-09-auditoria-continuidade.md`](../handoff/2026-11-09-auditoria-continuidade.md) | Auditoria deste snapshot, documentos examinados, divergências e validação da documentação | Usar para entender origem dos arquivos canônicos desta auditoria |

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
- WhatsApp: `docs/conexoes-whatsapp.md`; verificar sua data e contrastar com código/contrato externo.

## Outros documentos históricos/temáticos

`README.md`, `docs/architecture-proposal.md`, `docs/arquitetura.md`,
`docs/diagnostico-e-plano-2026-10-30.md`, `docs/implementation-plan.md`, os dois
arquivos `TODO*`, `docs/providers-and-hosting.md`, `docs/provedores-ia.md`,
`docs/deploy-hostinger.md`, `docs/security-and-operations.md`, `docs/historico-whatsapp.md`,
`docs/marca/identidade-dibberdesk.md`, documentos em `docs/contratacao/` e `tests/README.md`
foram localizados. São fontes específicas ou snapshots; confronte alegações de status
com o código e a referência temporal antes de usar.
