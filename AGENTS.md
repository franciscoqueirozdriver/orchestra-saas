# Orquestra — orientação de desenvolvimento

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
