# Transferência do atendimento natural: A Mesa → Orquestra

**Leia primeiro [INTENCOES.md](INTENCOES.md).** Esta pasta é um pacote de especificação
para implementação futura. Nada nela foi ligado ao runtime ou aplicado a um banco.

| Arquivo/pasta | Uso |
|---|---|
| [INTENCOES.md](INTENCOES.md) | Escopo C01–C16, histórico, decisões, fases, aceitação e reversão |
| [codigo-proposto/](codigo-proposto/) | Protótipo Python e contratos de integração |
| [migracoes-propostas/](migracoes-propostas/) | SQL adaptado ao schema Orquestra; drafts, não revisões Alembic |
| [referencias-a-mesa/manifesto.json](referencias-a-mesa/manifesto.json) | Snapshots históricos versionados e SHA-256 |
| [validacao/CENARIOS.md](validacao/CENARIOS.md) | Corpus mínimo de conversas e testes de infraestrutura |
| [validacao/verificar_prototipo.py](validacao/verificar_prototipo.py) | Verificação local e determinística da proposta Python e dos hashes |

Os SQL desta pasta e os SQL de referência **não devem ser copiados diretamente
para `backend/migrations/versions/` nem executados com psql**. O deploy atual não
varre esta pasta. Promoção exige implementação, models, Alembic, backfill e testes.
Não existe comando de deploy neste pacote.
