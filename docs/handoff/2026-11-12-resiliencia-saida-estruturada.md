# Handoff — resiliência de saída estruturada do modelo

**Data:** 12/11/2026
**Objetivo:** corrigir a falha em que o provedor respondia com texto ou JSON incompatível
com o contrato de visita e o agente escalava imediatamente, sem tentar outra conexão
configurada.
**Estado:** trabalho local em `feat/semantic-llm-fallback`, baseado em
`465d6b3e2185d1714bdbbde59383bda94c0b4b40`. Sem commit, push, merge, deploy, migration ou
chamada real a provedor.

## Evidência inicial

O ticket operacional 404388 indicava falha de resposta vazia/inválida. A revisão
correlacionada mostrava tentativa de provedor concluída, mas sem conteúdo interpretável
pelo contrato comercial. O texto da conversa e a resposta bruta do modelo não foram
incluídos neste handoff. A falha ocorria porque `model_router.generate_with_fallback`
considerava suficiente a resposta textual do transporte; a validação de
`parse_visit_response` acontecia depois que a cadeia de modelos já tinha terminado, em
`tasks.respond_to_conversation`.

Esta era uma causa concreta compatível com o ticket, não prova de que toda resposta
genérica “não consegui concluir” tenha a mesma origem. Não foram chamados os provedores
reais nem reproduzida a mesma conversa em produção.

## Alterações

- `backend/app/model_router.py`: aceita validador opcional de resposta; executa-o antes
  de persistir sucesso e antes de reutilizar cache. Saída incompatível é registrada com
  `result=invalid_response` e `failure_stage=response_validation`; o próximo candidato
  habilitado recebe o mesmo snapshot imutável. Se todas as conexões falharem no contrato,
  retorna `LLMError(category="invalid_response")`.
- `backend/app/tasks.py`: passa o validador somente quando
  `visit_booking_enabled` está ativo; agentes sem envelope estruturado preservam texto
  legado. Cadeia esgotada por formato inválido cria intervenção com diagnóstico
  específico e continua fail-closed.
- `backend/app/routes_conversations.py` e `frontend/app.js`: o painel mostra o estágio
  de falha e estado/motivo da última intervenção. Não expõe resposta bruta, histórico,
  segredo ou prompt.
- `tests/integration/test_runtime_safety.py`: cobre fallback após saída inválida, cadeia
  toda inválida, cache histórico inválido, passagem do validador pelo turno de visita e
  apresentação sanitizada do diagnóstico.
- `docs/ai/MESSAGE_FLOW.md`, `DECISIONS.md`, `KNOWN_RISKS.md`, `CURRENT_STATE.md` e
  `HANDOFF_INDEX.md`: registram comportamento, status local e riscos.

Sem tabela ou migration nova. O fluxo não altera perguntas/respostas comerciais,
confirmação operacional de visita, provedores escolhidos, configuração do tenant, envio
humanizado ou política de publicação.

## Validação executada

- Cinco testes focados de integração: **5 passaram**, em PostgreSQL descartável
  `orchestra_consolidation_test` dentro do container `orchestra-semantic-pg-20261112`.
- Suíte completa repetida com o ambiente corrigido: **223 passaram em 61,29 s**. Incluiu
  Git montado somente para leitura e `safe.directory` limitado ao checkout `/app`, além
  do PostgreSQL descartável e `MEDIA_DIR=/tmp/orchestra-semantic-media`; sem chamadas
  externas.
- `git diff --check`: aprovado antes da atualização documental; repetir na revisão final.
- `node --check frontend/app.js` e `compileall` haviam passado na revisão inicial. A
  tentativa posterior de `compileall` no container não pôde gravar `__pycache__` no
  bind mount somente de leitura; isso foi uma limitação de permissão, não erro de sintaxe.
- Não foi executado teste de navegador nesta etapa. A mudança de frontend é apenas texto
  diagnóstico e escapa os campos dinâmicos com `esc()`.

## Limitações e riscos remanescentes

- A validação sintática da estrutura não garante que a interpretação semântica do modelo
  esteja correta. Valores allowlist ainda podem ser escolhidos incorretamente pelo modelo;
  o backend continua limitando quando eles atualizam estado.
- Testes usam respostas sintéticas. Gemini, Groq e demais provedores não foram
  homologados e podem não produzir o contrato com confiabilidade.
- Se todos os modelos retornarem estrutura inválida, ocorre intervenção humana; não há
  reparo adicional por segunda chamada ao mesmo modelo nesta alteração.
- O painel acrescenta campos opcionais ao JSON de diagnóstico. Confirmar consumidores
  externos antes de alterar esse contrato no futuro.
- O conteúdo bruto da pasta local `docs/IDEIAS AI/` permanece privado/não rastreado e não
  deve ser adicionado ao Git. As recomendações DOLA aproveitadas foram sintetizadas em
  `docs/ai/DECISIONS.md`; a adoção de ferramentas/memória longitudinal está planejada,
  não implementada.

## Próximo passo recomendado

Revisar diff e testes desta branch. Depois, seguir a evolução em etapas: estado de diálogo
e avaliações offline; ferramentas operacionais allowlist e tenant-scoped com confirmação;
memória longitudinal aprovada e com proveniência; ciclo supervisionado de correção. Fazer
homologação de saída com provedor e canal de teste autorizados antes de ativar em operação.

## Estado Git ao encerrar

Branch: `feat/semantic-llm-fallback`. Base: `465d6b3e2185d1714bdbbde59383bda94c0b4b40`.
Alterações não commitadas limitadas aos cinco arquivos de implementação/teste listados e
os seis documentos de continuidade/handoff. Não trocar de branch ou publicar sem nova
revisão/autorização.
