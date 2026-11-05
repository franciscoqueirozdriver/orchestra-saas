# Contrato das migrações propostas

Os arquivos são drafts PostgreSQL dependentes, na ordem 001 → 002 → 003, e não
foram aplicados nem homologados em PostgreSQL nesta entrega documental.

| Draft | Cobertura das intenções |
|---|---|
| 001 | C01/C03–C08: política, persona, atribuição de agente, estado, revisão, cancelamento e humano |
| 002 | C02/C05/C06/C09/C15: turnos, partes de saída, lease e eventos auditáveis |
| 003 | C10–C15: qualidade, ferramentas, execuções, mídia, memória revisada, permissões do contato e fallback |

Complementos de código necessários: regras de TTL, expiração, rate limit Redis,
claim ordenado, atualização de updated_at, modo humano, permissões por papel,
criptografia, backfill e agregação dos estados das partes no pai. Defaults não são
políticas completas. Não há triggers de updated_at nem workers nesta proposta SQL.

As FKs compostas novas impedem vínculos entre tenants nos novos objetos. Isso não
corrige retroativamente todas as FKs simples do schema legado, nem estabelece RLS.
Todos os handlers novos devem validar escopo, papel e vínculo de instância/agente.

Uma conversa deve ter estado criado sob lock antes de processar comandos. Registro
de takeover inclui ator, motivo e vencimento nos eventos; expiração não libera IA
sem decisão da política. Estado `unknown` de entrega não pode virar retry automático.

Antes de transformar em Alembic, revisar o banco implantado e a cadeia real de
revisões. A revisão inicial usa Base.metadata.create_all: mantê-la sem ajustar a
estratégia pode fazer tabelas futuras nascerem na revisão inicial e colidirem com
estes CREATE TABLE. Congelar o schema histórico da inicial ou adotar baseline
explicitamente revisado, com teste tanto de instalação vazia quanto de upgrade.

Downgrade pretendido (não fornecido como script executável): desativar features,
parar novos dispatchers, reconciliar efeitos, exportar dados; remover dependentes
na ordem inversa 003 → 002 → 001 e remover primeiro FKs de atribuição/memória.
Nunca apagar dados de produção como “rollback automático”. Prefira manter schema
aditivo e reverter por flags, respeitando a política de retenção.

SQL originais relevantes do A Mesa para estudo, não execução:

- `0002_whatsapp_conversacional_e_pessoas_updates.sql`: estado de fluxo e propostas de cadastro.
- `0003_whatsapp_agente_autonomo.sql`: decisões e autonomia.
- `0004_rag_conhecimento_igreja.sql`: recuperação de conhecimento; Orquestra já tem pgvector.
- `0006_whatsapp_gatilhos_pastoral_sprint2.sql`: gatilhos específicos, generalizar por tipo de evento.
- `0007_whatsapp_debounce_inbound.sql`: RPCs de acúmulo/claim; snapshot nesta pasta de referências.
- `0008_whatsapp_perguntas_nao_respondidas.sql`: lacunas; snapshot de referência.
- `0016_fluxo_relatorios_whatsapp.sql`: exemplo de estado, não importar o domínio de relatório.

Não importar auth.users, service_role, políticas Supabase ou números de contatos
como se existissem no banco Orquestra. O executor é o usuário de migrações definido
no deploy; revisar privilégio/ownership antes de promover.
