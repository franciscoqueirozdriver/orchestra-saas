# Orquestra — orientação de desenvolvimento

- Antes de implementar, leia [`docs/ai/CONTINUITY_PROTOCOL.md`](docs/ai/CONTINUITY_PROTOCOL.md)
  e [`docs/ai/CURRENT_STATE.md`](docs/ai/CURRENT_STATE.md); consulte decisões e handoffs
  relevantes pelo índice [`docs/ai/HANDOFF_INDEX.md`](docs/ai/HANDOFF_INDEX.md).
- Verifique o código e o Git atuais. Documentos e handoffs são evidências datadas,
  não substitutos da inspeção da implementação.
- Consulte handoffs relacionados; não invente componentes/contratos nem faça
  refatorações não solicitadas. Mantenha mudanças pequenas e preserve compatibilidade,
  avaliando todos os consumidores antes de alterar APIs.
- Mudanças de autenticação, autorização, tenant, migrations, provedores, callbacks e
  publicação exigem revisão específica dos riscos e das dependências.
- Desenvolver em `/home/Alessandra/Documentos/orchestra-saas`. GitHub
  `franciscoqueirozdriver/orchestra-saas` compartilha o código. VPS `/opt/orquestra`
  é destino de publicação. Não usar sincronização reversa automática.
- Antes de editar, verificar branch/status e preservar trabalho pendente. Não
  reverter alterações alheias. Backups privados ficam fora do repositório.
- Trabalho novo vai em branch/PR. Merge em main e deploy exigem autorização
  correspondente do usuário; publicar uma branch não autoriza alterar a VPS.
- Publicação usa SHA completo revisado e recusa checkout remoto modificado ou com
  arquivos novos. Ver `docs/fluxo-local-github-vps.md` e `scripts/release.py`.
- Não expor/copiar .env real, credenciais, dumps, volumes, uploads ou dados de
  usuários em documentação, logs, testes ou Git. Revisar caminhos antes de git add.
- Testes de banco usam somente ambiente descartável explicitamente identificado.
  Não usar produção para testes; envios reais exigem destinatário/autorização próprios.
- Não reaplicar migrations históricas em produção. Upgrade/downgrade precisa de
  revisão da cadeia, backup, compatibilidade e autorização de publicação. Não usar
  models mutáveis para definir schema de uma revisão histórica.
- Distinguir trabalho implementado, simulado, homologado externamente e planejado.
  SQL sob docs/intencoes é draft e não pertence à cadeia Alembic executada.
- API/worker executam imagens; frontend/Caddyfile são bind mounts. Verificar ambos
  antes de atribuir comportamento da aplicação ao arquivo mais recente na VPS.
- Registrar diferenças, testes/limitações e efeito operacional em docs/consolidacao
  quando houver resgate/consolidação. Não guardar backups brutos nessa pasta.
- Após trabalho relevante, atualize um handoff datado sem sobrescrever os anteriores;
  mantenha decisões duradouras nos documentos canônicos de `docs/ai/`.
- Execute as verificações pertinentes antes de concluir; relate somente testes
  efetivamente executados, com resultado, e identifique o que ficou sem verificação.
