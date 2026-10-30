# Segurança e operação — versão inicial

## Controles implementados

- Senhas de usuário com Argon2; tokens JWT curtos; segredos PostgreSQL, JWT e Fernet gerados pelo script de instalação, fora do Git.
- PostgreSQL de runtime com usuário separado sem superuser. O superuser é restrito ao serviço DB e às rotinas de backup/restauração. PostgreSQL, Redis e API não têm portas publicadas; a borda exposta é o Caddy em 80/443.
- Credenciais Z-API/LLM cifradas em repouso no banco com Fernet. O banco contém ciphertext, mas a chave de decifragem está disponível aos contêineres API/worker; proteja o host, `.env`, backups e acesso ao Docker.
- Autenticação de webhook por segredo imprevisível próprio no caminho, comparado com hash no banco; checagem do identificador de instância, validação de JSON, limite de corpo e deduplicação por chave de evento. A documentação Z-API consultada não caracteriza assinatura criptográfica universal desse callback; o token é uma proteção adicionada pelo produto, não assinatura nativa.
- Rate limit distribuído no login via Redis (8 tentativas por IP/e-mail hash por minuto); limite de corpo ASGI (1 MiB em geral; até `UPLOAD_MAX_MB + 2 MiB` para upload); validação HTTPS, DNS público, porta 443 e ausência de redirects para destinos de provedores de IA/embeddings, mitigando SSRF.
- Caddy com HTTPS automático, CSP e cabeçalhos de segurança; access log Uvicorn desabilitado. Logs do backend não devem incluir prompts, payloads, URLs de callback ou conteúdo de mensagens.
- Mensagens fragmentadas são agrupadas por uma janela configurável; revisão da conversa é verificada antes do envio. Outbox tem chave idempotente e unicidade de resposta por revisão, evitando reenvio automático após timeout ambíguo.

## Isolamento SaaS

A aplicação usa filtragem explícita por `tenant_id` em rotas e tarefas; usuários de tenant não podem escolher livremente outro tenant. O administrador da plataforma precisa selecionar um tenant ativo para operar. IDs em checkpoints incluem tenant e conversa. Isso é **isolamento implementado na camada de aplicação**, não Row-Level Security do PostgreSQL. Um erro futuro de consulta, nova rota ou script pode romper a barreira; antes de dados reais, acrescente testes de integração adversariais entre duas empresas, revisão de todas as consultas e, idealmente, RLS no banco.

## Segredos e dados

1. Não inclua `.env`, chaves de API, callback URLs, mensagens ou dados pessoais em commits, tickets, capturas de tela e logs.
2. Restrinja acesso SSH, acesso de Docker, diretórios de volumes e arquivos de backup. O socket Docker é equivalente a root.
3. Faça cópia protegida da `CREDENTIALS_ENCRYPTION_KEY` fora do VPS; sem ela os tokens já cifrados não podem ser decifrados. Planeje recriptografia de todos os registros antes de rotacioná-la. Rotacionar apenas `JWT_SECRET` invalida sessões ativas.
4. A resposta via modelo envia ao provedor externo histórico recente e contexto recuperado; embeddings enviam trechos de documento ao provedor configurado. Revise contrato/DPA, região, retenção e uso de dados de cada provedor, e minimize o conteúdo enviado.
5. Não use material secreto como conteúdo de documentos. Os guardrails de prompt são defesa em profundidade, não autorização técnica.

## Limitações e riscos residuais

- Não existe ainda ferramenta externa executável pelo agente; Groq Tools, xAI Agent Tools, MCP, Calendar, CRM e ações de escrita estão desligados/não implementados. Isso evita efeitos externos sem autorização e também significa que o critério “executar tarefas” ainda está pendente.
- Não há gestão completa de consentimento/opt-out, blocklist, limite de envio WhatsApp, escalonamento de risco ou rotina automática de retenção/exclusão LGPD. Respostas automáticas devem permanecer desligadas até criar tais controles e homologar o fluxo sob política aplicável.
- O status de envio é `accepted` após resposta HTTP, não confirmação de entrega. Em falha de rede depois do envio, o estado pode ser ambíguo; verifique outbox/Z-API antes de repetir manualmente.
- Mídias recebidas não são baixadas, transcritas ou analisadas; URLs de mídia não são armazenadas. Envio é só texto. Conteúdo e memória são processados segundo o fluxo RAG/LLM configurado.
- A checagem DNS pública reduz destinos SSRF, mas não substitui firewall de saída e não elimina todas as técnicas de DNS rebinding/alteração de DNS. Restrinja egress no host se a plataforma permitir URLs de embedding genéricas.
- O Redis é privado à rede Docker, mas sem senha nesta configuração mínima. Não publique sua porta. Backup captura PostgreSQL e `app_data`, não uma cópia durável do Redis; eventos ficam no banco, mas tarefas enfileiradas podem precisar ser reprocessadas após perda do broker.
- Restauração, renovação de certificado, reconexão Z-API, limites do plano e carga real não foram testados nesta entrega.

## Backup, retenção e recuperação

`scripts/backup.sh` faz stream de `pg_dump` e `app_data` para arquivos criptografados com OpenSSL AES-256-CBC/PBKDF2 e cria checksums SHA-256. Ele exige `BACKUP_PASSPHRASE`, procura por padrão `$HOME/.config/orquestra-backup/env` e retém arquivos por 14 dias no diretório local `backups/`. AES-CBC não fornece autenticação criptográfica do ciphertext por si só; o checksum detecta corrupção acidental, não adulteração maliciosa. Proteja e mantenha a passphrase fora do servidor.

Crie primeiro o arquivo de passphrase com acesso restrito e guarde uma cópia da passphrase em um gerenciador fora da VPS. O arquivo local é necessário para o cron; não o inclua na cópia off-site dos backups.

```bash
install -d -m 700 "$HOME/.config/orquestra-backup"
umask 077
printf 'BACKUP_PASSPHRASE=%s\n' "$(openssl rand -hex 32)" > "$HOME/.config/orquestra-backup/env"
chmod 600 "$HOME/.config/orquestra-backup/env"
mkdir -p /opt/orquestra/backups && chmod 700 /opt/orquestra/backups
```

Após testar manualmente `cd /opt/orquestra && ./scripts/backup.sh`, agende no crontab do mesmo usuário de deploy. Horário é o fuso do servidor (ajuste conforme necessário):

```cron
PATH=/usr/local/bin:/usr/bin:/bin
0 2 * * * cd /opt/orquestra && /opt/orquestra/scripts/backup.sh >> /opt/orquestra/backups/backup.log 2>&1
```

Monitore falhas, copie os arquivos criptografados para destino independente (off-site) e conserve a passphrase separadamente. Esse envio externo não é configurado pelo projeto. Faça teste de restauração em ambiente isolado com os arquivos e chave correspondentes antes de confiar no backup; a restauração substitui dados e exige digitar `RESTAURAR`.
