# Provedores configuráveis

Base revisada: `20fa68f8ff1a7473fadffc4ee1fa7da941d47fb8`.
Branch: `feature/provedores-configuraveis`.

O backend já tinha conexões múltiplas e protocolos nativos que o formulário
antigo não expunha. O painel agora usa esses recursos: presets extensíveis,
conexão personalizada, edição, padrão da empresa e alternativas ordenadas por
agente. Preserva chaves quando vazias e recusa remoção de conexões vinculadas.

A geração e os embeddings têm configuração separada. Mudanças de geração
preservam a busca anterior; mudanças de namespace com documentos indexados
exigem reindexação planejada. Não há mudança de schema nem nova migration.

Validação local: 120 testes unitários/guardas e 43 testes de integração com
PostgreSQL descartável passaram. A execução sem banco pulou os mesmos 43,
que foram executados separadamente com sucesso. Dois cenários Chrome passaram:
painel de atendimento e conexões/protocolos/vínculos de agentes. Sintaxe JS,
compilação Python e `git diff --check` passaram.

As credenciais são sintéticas, os provedores são simulados e nenhuma mensagem
real foi enviada. Não houve acesso ao banco nem alteração dos serviços da VPS
nesta tarefa. Contas, saldo, modelos disponíveis e peculiaridades reais de
fornecedores continuam sujeitos a homologação externa autorizada.

Publicação futura: revisar a PR, aguardar CI, autorizar merge e publicar o SHA
completo validado pelo procedimento de `docs/fluxo-local-github-vps.md`.
Conferir checkout remoto limpo, backup e recibo antes da aplicação; manter
envios pausados durante a verificação. Como não há migration, a reversão de
código usa o SHA/imagens anteriores preservados, sem downgrade de banco.
Conexões novas devem permanecer sem uso até validar os provedores escolhidos.
