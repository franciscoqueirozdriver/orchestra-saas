# Riscos e validações obrigatórias

Os itens abaixo são pontos de atenção observados; não constituem auditoria de
segurança completa nem declaração de vulnerabilidade confirmada.

| Área | Risco/limite | Antes de mudar |
|---|---|---|
| Sessão da plataforma | JWT de acesso expira em 30 min por padrão. A renovação local via `/auth/me` só funciona enquanto o token ainda é válido; expiração após inatividade prolongada ou rotação de `JWT_SECRET` exige novo login. Renovação automática ainda precisa validação após publicação. | Manter teste de token perto da expiração, 401/retry e usuário inativo; nunca prolongar validade sem autenticar usuário ativo. Verificar configuração efetiva sem revelar segredo e confirmar em produção após release. |
| Autenticação e tenant | Erro em dependências ou filtro de consulta pode expor empresa a outra | Revisar todas as rotas/leitores/jobs envolvidos e adicionar teste negativo de tenant/role com fixture sintética |
| Migrations | Cadeia local chegou a `0010`; snapshot de banco real é desconhecido | Ler migration anterior e posterior, upgrade/downgrade, dados legados e impacto em release; nunca alterar migration histórica ou executar em produção sem autorização e backup |
| API e UI | Rotas chamadas `zapi` servem ambos os adaptadores; contratos podem ter consumidores no JS, worker e callbacks | Mapear chamadas/consumidores e preservar compatibilidade; testar payloads de cada provedor sem segredos |
| Conectores WhatsApp | Z-API e WAME têm APIs, callbacks, políticas e semânticas externas diferentes | Testes simulados não equivalem a homologação; conferir contrato atual e usar conta/número de teste autorizado |
| Grupo/intervenção | Código de aceite, números autorizados, mensagem privada, grupo e envio são ações sensíveis | Revisar autorização, expiração, concorrência, redaction e falha ambígua; mensagens de teste exigem consentimento operacional explícito |
| Outbox e scheduler | Estado persistente e efeito no fornecedor podem divergir em timeout ou crash | Revisar idempotência, reconciliação, lease/lock e estados `unknown`; evitar retry cego |
| Interrupção entre partes | Na branch local, callback durável e dispatcher serializam pelo lock de tenant; evento, invalidação e cancelamento de partes pendentes são atômicos para conversas resolvidas sem ambiguidade. A geração também aguarda eventos preemptivos não processados. O lock durante I/O externo pode atrasar webhooks da mesma empresa | Manter teste determinístico de webhook persistido com worker pendente, teste concorrente e redelivery; chamada externa iniciada antes do aceite durável não é cancelável, e contato/alias ambíguo não preempta conversa por inferência; medir atrasos sob latência do provedor |
| Checkpointer | `checkpointer.setup()` pode criar estruturas/index e comportamento varia sob concorrência | Preservar cache de inicialização e o teste/commit corretivo; não recolocar setup por resposta sem avaliar locks/DDL |
| Provedores LLM/embeddings | Chaves, endpoint SSRF, limites, fallback e formato de resposta afetam dados e custos. A geração de embeddings da busca ocorre durante a montagem do contexto e não é registrada como tentativa em `model_runs`; conexões OpenRouter podem ser compartilhadas por geração e busca | Revisar `url_safety.py`, protocolo, dimensões, limites, retenção e destino de dados; não presumir sucesso porque a conexão foi salva. Separar no diagnóstico cota de requisições gratuitas de cobrança por tokens; consultar atividade do fornecedor e não atribuir a chamada de embeddings ao contador de geração sem evidência |
| Dados de conversa | Histórico contém dados pessoais; originais privados não são conhecimento aprovado | Não abrir/copiar/exportar material privado para Git, logs, prompts ou fixtures; manter isolamento, retenção e aprovação |
| Conhecimento/RAG | Documento pode estar apenas armazenado ou indexado; alterar embeddings requer reindexação | Verificar status e configuração ativa, empresa e proveniência; não confundir histórico com regras aprovadas |
| Infra/segredos | `.env`, volumes, backups e imagens guardam segredos/dados; release pode aplicar migrations e reiniciar serviços | Checar `.gitignore`, `.dockerignore`, contextos, recibo/backup, SHA completo e checkout remoto; publicação/deploy requer autorização própria |
| Mídia | `MEDIA_DIR` persistente e processadores de upload carregam risco de privacidade, tamanho e conteúdo hostil | Conferir limites, tipo real, armazenamento/retention, permissões e tenant; não anexar acervo real a testes |
| Docs sobre produção | Handoffs são snapshots com datas; código local posterior não prova estado remoto | Consultar VPS/CI apenas com escopo e autorização adequados; rotular sem confirmação como desconhecido |
| Qualificação e interpretação de visita | Fatos concretos (data, cidade, telefone etc.) ainda passam por extração determinística; confirmações contextuais são interpretadas pelo modelo a partir do histórico e do estado estruturado. O formato estruturado do modelo pode falhar ou ser interpretado incorretamente; saída inválida falha fechada para intervenção. Em conversa preexistente, a reconstrução considera até 200 mensagens recentes | Manter origem/timestamps dos fatos; aceitar semântica apenas em campo allowlist quando existe pergunta pendente. Testes mockados não provam qualidade do Gemini ou de outro provedor; homologar com canal de teste autorizado sem usar acervo privado como fixture Git |
| Pedido de visita sem agenda integrada | O sistema não consulta disponibilidade nem reserva horário; alerta de intervenção pode não ser enviado se grupo não estiver validado | Permanecer em `awaiting_confirmation`, informar pendência com honestidade e validar o fluxo humano antes de operação; nunca converter preferência em `confirmed` |
| Interpretação de afirmações de agendamento | A proteção contra confirmações falsas é determinística e cobre construções conhecidas, mas não é uma garantia semântica para toda paráfrase. Testes mostraram que uma versão anterior tratava “encaminhar à equipe para confirmar disponibilidade” como promessa; a guarda agora requer uma afirmação de compromisso | Manter testes de linguagem sintética para compromissos e encaminhamentos; exigir validação operacional antes de comunicar disponibilidade. Qualquer texto do modelo não equivale a reserva |
| Data relativa em visita | “Próxima quinta” é preservada como frase, sem conversão para data absoluta porque não há fuso de negócio por tenant | Não confirmar compromisso nem calcular disponibilidade até existir timezone/configuração de agenda autorizada |
| Segmentação global | Toda resposta automática usa até três partes de 300 caracteres e intervalo de 2 s; texto maior ou indivisível segue para intervenção, o que pode aumentar handoffs | Medir cancelamentos, latência e legibilidade em operação controlada; limites são hipóteses de experiência, não limites oficiais do WhatsApp |
| Saída estruturada do modelo | Antes, o roteador podia classificar como sucesso uma chamada HTTP bem-sucedida mesmo quando a resposta não cumpria o envelope semântico de visita; cache desse texto também poderia ser reutilizado. Na branch local `feat/semantic-llm-fallback`, o contrato é validado antes do sucesso/cache e a saída inválida tenta o próximo modelo configurado com o mesmo snapshot; se todos falharem, continua fail-closed e gera intervenção diagnóstica | A suíte usa fakes; comportamento semântico e conformidade de formato de Gemini/Groq/outros não estão homologados. Confirmar com prompts sintéticos em provedor e destinatário de teste autorizados antes de ativar respostas reais |
| Evolução modular inspirada na DOLA | As ideias locais incluem módulos de percepção, memória, decisão e ações. Criar agentes autônomos ou ferramentas sem escopo pode ampliar prompt injection, acesso entre tenants e efeitos externos | Evoluir em etapas: estado/histórico e contratos; avaliação offline; depois registro allowlist de ferramentas tenant-scoped, com autorização e confirmação humana para efeitos sensíveis. Não iniciar multiagente ou aprendizado automático de conversas brutas |

## Validação local da continuidade conversacional — 2026-11-10

Na branch `feat/enrico-context-booking`, 154 testes unitários passaram e 58 de
integração passaram em PostgreSQL descartável; dois testes de consolidação de migrations
foram pulados por ausência da baseline de origem. A cobertura sintética verifica
metadados de telefone de Z-API/WAME, resposta do cliente, recebedor terceiro, segmentação
global mesmo com perfil sem opt-in e ausência de fluxo de visita para agentes sem a
capacidade configurada. Isso não demonstra a qualidade de extração em todas as formas de
escrita, nem homologação da agenda, dos grupos ou dos provedores.

## Validação local da branch de envio humanizado — 2026-11-10

Na branch `feat/humanized-whatsapp-delivery`, os testes unitários passaram (149) em
container sem rede; os testes de integração passaram (57) usando PostgreSQL descartável
e `MEDIA_DIR` temporário. Isso valida os cenários simulados no checkout local, não
homologa WAME/Z-API nem demonstra o estado da VPS. A suíte não elimina a limitação de
cancelamento de chamadas externas já iniciadas nem resolve associação de contato
ambígua.

## Revisão local do núcleo conversacional — 2026-11-12

Na branch local `test/conversational-core-onda1`, o resumo agora pagina por
`(created_at, id)`, para não ignorar mensagens com timestamps iguais. Cursors antigos
sem ID reprocessam a mensagem de fronteira (`created_at >= cursor`), o que pode
duplicar contexto no resumo, mas evita perder mensagens empatadas. A rota de exclusão
de memória agora exige administrador para itens `kind='business'` e continua filtrando
por tenant. Os testes desta revisão são locais e não indicam que essas mudanças estejam
na `main`, no GitHub ou na VPS.

A avaliação de respostas adicionada nesta branch usa somente casos sintéticos e rubrica
de revisão humana. Seus testes validam estrutura e ausência de identificadores de
contato; não pontuam respostas de Gemini ou de outro LLM. A qualidade conversacional,
o resumo com modelo real e a configuração operacional ainda exigem avaliação separada.
