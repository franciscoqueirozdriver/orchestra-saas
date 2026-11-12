# Onda 1 — núcleo conversacional humanizado

Base: `a4aa4ce` (branch `feat/conversational-core`, worktree
`/tmp/orchestra-conversational-core`). Spec:
`docs/superpowers/specs/2026-11-12-atendimento-humanizado-onda1-design.md`.
Plano: `docs/superpowers/plans/2026-11-12-atendimento-humanizado-onda1.md`.
Registro das Tasks 1–8B nos relatórios datados em
`.superpowers/sdd/2026-11-12-atendimento-humanizado-onda1/`.

Os recursos novos são opt-in por agente pelas flags `memory_enabled`,
`structured_decision_enabled` e `presence_enabled`, todas desligadas por padrão
(`backend/app/schemas.py`). Nenhuma instalação, upgrade ou configuração liga essas
flags automaticamente. `presence_enabled` só produz efeito quando o provedor da
instância é `zapi` (`backend/app/tasks.py`).

## Escopo entregue

| Task | Entrega | Limite de validação |
|---|---|---|
| 1 | Persona configurável no perfil do agente (tom, concisão, emojis, vocabulário, exemplos revisados) | Guard de estilo não é prova de correção factual |
| 1B | Configuração de negócio, produtos, processos e documentos no painel | Fluxo de indexação e escrita sem teste de integração dedicado |
| 2 | Contrato estruturado de decisão (`parse_decision_envelope`, `clean_visit`, `state_patch`) | Validação fecha em erro; não substitui interpretação do modelo |
| 3 | Memória em camadas e migration `0012_conversation_memory` (aditiva) | Dados históricos preservados; memória não aprovada não entra no prompt |
| 4 | Humanização de entrega: `delivery_plan`, `part_delay`, `should_wait`, aberturas anti-repetição | Presença limitada; silêncio é guarda determinística |
| 5 | Integração no pipeline de resposta (memória, decisão, humanização) | Comportamento final depende do modelo; flags desligadas mantêm caminho anterior |
| 6 | Resumo rolante assíncrono | Cursor por `created_at`; caminho incremental sem teste dedicado |
| 7 | Rotas de memória e última decisão, com escopo por tenant | Aprovar/excluir fato não invalida revisão nem cancela Outbox de todo o tenant |
| 8 / 8B | Painel de persona, memória, negócio, catálogo, processos e documentos | Botões de escrita herdados visíveis para não-admin |
| 9 | Corpus de 52 casos e este registro | Corpus testa políticas/estado, não qualidade de respostas de LLM |

## O que foi testado

Executado nesta sessão, no container `orchestra-saas:test` (Python 3.12):

- Unitários (`tests`, exceto `tests/integration`): **217 passed, 1 failed**. A falha é
  ambiental e esperada: `tests/test_private_knowledge.py` executa `git ls-files` e o
  container não enxerga o `.git` do worktree (`fatal: not a git repository`).
- Integração (`tests/integration`, PostgreSQL descartável
  `orchestra_consolidation_test`, rede `sdd-test-20261112`): **85 passed, 2 skipped**.
  Os dois skips são de `test_migration_consolidation.py`, que exige baseline de
  fonte original isolado.
- Corpus conversacional (`tests/test_conversation_corpus.py`): **3 passed**, cobrindo
  52 casos em `tests/fixtures/conversation_cases.json`.

O corpus valida três contratos determinísticos sobre dados sintéticos:

1. `len(CASES) >= 40` — há 52 casos.
2. `transition()` e `command()` coincidem com o `mode` e o `command` esperados em
   todos os casos.
3. `should_wait()` coincide com `expect` (`wait`/`reply`) nos casos que o declaram.

Evidência RED/GREEN: antes do corpus, o teste falhou com `assert 20 >= 40` e lista de
esperas vazia; após a expansão, os três testes passaram sem alteração de código de
comportamento.

Não executado nesta sessão: testes de UI em Node (`tests/ui`, Playwright/Chrome),
suíte completa de CI, migration em ambiente real e qualquer avaliação com modelo real.

## O que é simulado

- Os 52 casos do corpus são dados sintéticos de avaliação de políticas, não diálogos
  reais nem amostras de acervo privado. Eles exercitam `transition`, `command` e
  `should_wait`; não avaliam a qualidade textual gerada por um modelo.
- Os testes de integração usam banco descartável explicitamente identificado, nunca
  produção.
- Presença do provedor e latência por parte são observadas por boas práticas de
  unidade; não há medição de latência real de rede nem confirmação de presença.

## O que permanece pendente

- Homologação de modelo/provedor real e de destinatários reais: requer autorização
  própria. Nenhuma chamada a provedor de IA ou WhatsApp foi feita.
- Avaliação humana de naturalidade, clareza, continuidade, repetição e tom.
- Testes de UI (Playwright/Chrome) e validação da cadeia de migration em ambiente
  isolado com baseline original.
- Pendências menores registradas (deferidas) nos relatórios: cursor de resumo por
  `created_at`, caminho incremental de resumo, cobertura de UI, campos numéricos sem
  `required`, escrita de não-admin no painel, entre outras.
- Fora da Onda 1: ferramentas/leitura de banco, roteamento por tarefa, cotas, áudio,
  calendário e aprendizado automático.

## Riscos

- Comportamento final do texto depende do modelo; o corpus não mede qualidade nem
  garante ausência de regressões semânticas.
- Presença é limitada e opcional; falha opcional não bloqueia texto.
- `presence_enabled` só tem efeito com provedor `zapi`; outros provedores permanecem
  sem presença.
- Migração `0012` é aditiva, mas upgrade/downgrade reais exigem backup, revisão da
  cadeia e autorização de publicação. Downgrade com dados de memória precisa ser
  avaliado antes.
- Corpus verde não autoriza ampliar uso; medir latência/carga e operar `unknown`
  antes de piloto.

## Como reverter

Reversão preferencial por flag: desligar `memory_enabled`,
`structured_decision_enabled` e `presence_enabled` por agente restaura o caminho
anterior sem apagar schema nem dados. Não executar dispatchers concorrentes nem
sincronização reversa. Merge em `main` e deploy na VPS exigem autorização própria;
esta branch não autoriza publicação. Antes de reverter código com schema já migrado,
reconciliar estado de decisões e memória e revisar a cadeia de migration.
