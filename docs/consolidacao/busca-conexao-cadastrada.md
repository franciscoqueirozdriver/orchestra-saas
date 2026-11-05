# Busca com conexão cadastrada

Base: 308a74f53caa9629632dd3b9dc94071ae1bfb039.
Branch: feature/busca-conexao-cadastrada.

O formulário permite selecionar uma conexão já cadastrada, escolher o modelo
específico de embeddings e aproveitar a chave da geração no servidor sem cópia.
Mantida configuração manual e compatibilidade com configurações anteriores.
Gemini oficial recebe dimensions=1536 e normalização. Não se usa o modelo de
conversa como modelo de embeddings e não se promete acesso real pelo cadastro.

Migration 0007_search_connection: coluna nullable referenciando llm_configs,
exclusão restrita, sem backfill nem envio externo. API valida empresa, estado e
protocolo; preserva namespace dos índices. Mudança de endpoint da conexão exige
revisão explícita. Rota de exclusão recusa conexão vinculada. Rotação da chave
no mesmo endpoint é aproveitada sem recadastrar a busca.

Validação: 123 testes unitários/guardas e 49 integrações PostgreSQL descartável
passaram. Três cenários Chrome passaram. Inclui dimensão/payload Gemini,
normalização, referências por empresa, ausência de cópia/exposição de chave,
rotação, endpoint alterado, exclusão e downgrade protegido. Instalação fresca,
upgrade legado, Alembic check e regressão do atendimento também passaram.
Sem chamadas reais a fornecedores, dados pessoais ou mensagens. Homologação de
quota/modelo real permanece pendente. Documentos locais privados preservados.

Usuário autorizou commit, main e sincronização com VPS. Publicação requer CI do
SHA, checkout remoto limpo, revisão 0006 conferida, backup cifrado e imagens
anteriores preservadas; inicia envios pausados. Verificar SHA/imagens, revisão
0007, saúde, scheduler, worker, frontend e HTTPS após aplicar.

Risco de reversão: após referências novas, código anterior não resolve as chaves
vinculadas. Preferir correção à frente ou restaurar configuração manual equivalente
com revisão e backup antes de retomar código anterior. Não remover referências,
dados, volumes ou executar downgrade automático.
