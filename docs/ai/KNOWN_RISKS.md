# Riscos e validações obrigatórias

Os itens abaixo são pontos de atenção observados; não constituem auditoria de
segurança completa nem declaração de vulnerabilidade confirmada.

| Área | Risco/limite | Antes de mudar |
|---|---|---|
| Autenticação e tenant | Erro em dependências ou filtro de consulta pode expor empresa a outra | Revisar todas as rotas/leitores/jobs envolvidos e adicionar teste negativo de tenant/role com fixture sintética |
| Migrations | Cadeia local chegou a `0010`; snapshot de banco real é desconhecido | Ler migration anterior e posterior, upgrade/downgrade, dados legados e impacto em release; nunca alterar migration histórica ou executar em produção sem autorização e backup |
| API e UI | Rotas chamadas `zapi` servem ambos os adaptadores; contratos podem ter consumidores no JS, worker e callbacks | Mapear chamadas/consumidores e preservar compatibilidade; testar payloads de cada provedor sem segredos |
| Conectores WhatsApp | Z-API e WAME têm APIs, callbacks, políticas e semânticas externas diferentes | Testes simulados não equivalem a homologação; conferir contrato atual e usar conta/número de teste autorizado |
| Grupo/intervenção | Código de aceite, números autorizados, mensagem privada, grupo e envio são ações sensíveis | Revisar autorização, expiração, concorrência, redaction e falha ambígua; mensagens de teste exigem consentimento operacional explícito |
| Outbox e scheduler | Estado persistente e efeito no fornecedor podem divergir em timeout ou crash | Revisar idempotência, reconciliação, lease/lock e estados `unknown`; evitar retry cego |
| Checkpointer | `checkpointer.setup()` pode criar estruturas/index e comportamento varia sob concorrência | Preservar cache de inicialização e o teste/commit corretivo; não recolocar setup por resposta sem avaliar locks/DDL |
| Provedores LLM/embeddings | Chaves, endpoint SSRF, limites, fallback e formato de resposta afetam dados e custos | Revisar `url_safety.py`, protocolo, dimensões, limites, retenção e destino de dados; não presumir sucesso porque a conexão foi salva |
| Dados de conversa | Histórico contém dados pessoais; originais privados não são conhecimento aprovado | Não abrir/copiar/exportar material privado para Git, logs, prompts ou fixtures; manter isolamento, retenção e aprovação |
| Conhecimento/RAG | Documento pode estar apenas armazenado ou indexado; alterar embeddings requer reindexação | Verificar status e configuração ativa, empresa e proveniência; não confundir histórico com regras aprovadas |
| Infra/segredos | `.env`, volumes, backups e imagens guardam segredos/dados; release pode aplicar migrations e reiniciar serviços | Checar `.gitignore`, `.dockerignore`, contextos, recibo/backup, SHA completo e checkout remoto; publicação/deploy requer autorização própria |
| Mídia | `MEDIA_DIR` persistente e processadores de upload carregam risco de privacidade, tamanho e conteúdo hostil | Conferir limites, tipo real, armazenamento/retention, permissões e tenant; não anexar acervo real a testes |
| Docs sobre produção | Handoffs são snapshots com datas; código local posterior não prova estado remoto | Consultar VPS/CI apenas com escopo e autorização adequados; rotular sem confirmação como desconhecido |

## Estado de execução nesta auditoria

Nenhum teste foi executado nesta tarefa. Existem testes em `tests/`; os resultados
antigos citados em `docs/consolidacao/` e `docs/handoff/` pertencem aos SHAs e datas
registrados ali e não devem ser promovidos a resultado do commit `40272d0`.
