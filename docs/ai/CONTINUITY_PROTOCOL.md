# Protocolo de continuidade entre agentes

Este procedimento vale para Codex, Cursor, Claude, Gemini e outros agentes. Contexto
documental orienta a investigação; não substitui a leitura do código nem confere
autorização de negócio, publicação ou deploy.

## Inicialização obrigatória

1. Leia `AGENTS.md` e instruções locais aplicáveis (por exemplo, `.cursor/rules/` se existir).
2. Registre branch, SHA completo, `git status --short --branch`, alterações staged/unstaged e não rastreadas. Não edite antes de entender e preservar o trabalho existente.
3. Leia [`CURRENT_STATE.md`](CURRENT_STATE.md), depois `PROJECT_CONTEXT.md` e as decisões relevantes em `DECISIONS.md`.
4. Use [`HANDOFF_INDEX.md`](HANDOFF_INDEX.md) para localizar o handoff mais recente e os registros da tarefa. Leia o histórico pertinente; não o sobrescreva.
5. Inspecione os arquivos, contratos, chamadas, migrations e testes realmente envolvidos.
6. Consulte `KNOWN_RISKS.md`; identifique dados sensíveis, efeitos externos e pré-condições de ambiente.
7. Compare documentação com implementação e histórico Git. Marque divergências e fatos não verificados.
8. Antes de editar, apresente ao usuário um resumo do entendimento e plano, especialmente quando a tarefa muda comportamento, segurança ou negócio.

Se instruções, documentos e código divergirem em decisão de negócio ou segurança,
preserve o estado, registre as fontes e peça uma decisão. Nunca invente componentes,
endpoints, tabelas, resultados de teste ou comportamento de provedor. Evite refatorações
fora do pedido; mudanças em contrato devem mapear os consumidores.

## Registro de cada sessão

Crie um novo arquivo datado sob `docs/handoff/` seguindo o padrão existente. Não
reutilize nem reescreva um handoff antigo. Mantenha-o conciso; fatos permanentes vão
para os documentos canônicos e o índice é atualizado quando necessário.

Modelo mínimo:

```markdown
# Handoff — <objetivo>

Data e agente/modelo:
Estado inicial: branch, SHA completo, remoto observado (ou não observado)
Objetivo e escopo:
Fontes/handoffs lidos:
Alterações realizadas: caminhos e resumo
Decisões: justificativa e referência
Testes/verificações: comando, ambiente, resultado; separar não executado/falhou/passou
Problemas e riscos:
Pendências/bloqueios:
Próxima ação e verificações necessárias:
Estado Git final: branch/SHA, staged, unstaged, untracked; indicar se publicado/deployado
```

Não inclua `.env`, chaves, tokens, dados pessoais, payloads reais, transcrições,
backups, dumps ou caminhos privados que revelem conteúdo. Não declare “validado” sem
registrar o que foi executado e em qual revisão. Um teste existente não é um teste
executado.

## Prevenção de regressões

- **Auth/tenant:** verificar papel, empresa selecionada, filtragem em rota/job e casos negativos cross-tenant.
- **API/UI:** mapear rotas, payloads, frontend, workers e callbacks; testar compatibilidade e erros.
- **Migrations:** revisar cadeia, estado legado, upgrade/downgrade e impacto em dados; somente banco descartável em testes.
- **WhatsApp/provedores:** simular contratos no teste; homologação real exige conta, destinatário e autorização próprios. Não enviar mensagem real por smoke test genérico.
- **Outbox/concorrência/scheduler:** rever idempotência, locks, efeitos incertos, repetição e recuperação após crash.
- **LLM/RAG/conteúdo privado:** validar destino de dados, chaves, dimensões, isolamento e proveniência; conversa histórica não é conhecimento aprovado automaticamente.
- **Infra/deploy:** conferir SHA, imagem, bind mounts, checkout remoto limpo, migration atual e backup. Merge, deploy, mudança de saída e ação externa exigem autorização específica.
- **Testes:** usar os existentes e acrescentar cobertura apropriada quando autorizado. Nunca usar produção nem exportações reais como fixture.

## Fechamento

Ao terminar, atualize o handoff, o índice se necessário, e os documentos canônicos
quando uma decisão/estado permanente mudou. Relate claramente testes, limitações,
Git final e o que continua sem confirmação. Não faça commit, push, merge, publicação,
alteração de VPS ou deploy sem autorização correspondente.
