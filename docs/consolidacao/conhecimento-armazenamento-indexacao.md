# Armazenamento e indexação separados

Branch: `feature/conhecimento-armazenamento-indexacao`, sobre a correção de
provedores da PR #4. Envio salva texto extraído sem IA; indexação é explícita e
configuração de busca própria por empresa. Originais não são armazenados.
Mantido fallback de configuração legada e documentos previamente indexados.

Migration aditiva `0006_knowledge_storage`, sobre `0005_conversation_core`:
texto extraído nullable e tabela de configuração por empresa com chave cifrada.
Não transforma documentos nem chama provedores. Downgrade recusa remoção de
textos/configurações novos. Migrations são transações individuais: downgrade
atravessando várias revisões pode concluir uma revisão vazia antes de outra
recusar. Testes conferem esse comportamento e preservação de dados.

Validação local: 120 testes unitários/guardas e 47 integrações PostgreSQL
passaram, incluindo instalação/upgrade legado, Alembic check, armazenamento sem
modelo, retomada após falha, isolamento, concorrência e downgrade protegido.
Três cenários Chrome passaram (conhecimento, provedores e atendimento).
Transportes externos simulados, sem conteúdo real, importação ou mensagens.

Publicação em main e VPS autorizada pelo usuário. O procedimento exige CI verde,
checkout remoto limpo, revisão 0005 conferida, backup cifrado e tags das imagens
anteriores. Aplicar apenas a nova revisão e manter envios pausados. Conferir
SHA, saúde, schema, assets e TLS após deploy. Sem reindexação automática.
Para reversão, conservar schema aditivo e imagens/SHA anteriores; não executar
um downgrade que apague o texto salvo. Homologação dos provedores reais permanece
pendente. Documento privado local de conhecimento fica fora do commit.
