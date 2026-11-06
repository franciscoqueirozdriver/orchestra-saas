# diBBerDesk — Atendimento humano no WhatsApp

**diBBerDesk. Versão: MVP alfa, 30/10/2026.** Atendimento humano no WhatsApp. Este repositório contém uma primeira implementação auto-hospedável para Hostinger KVM 2. Ele não é uma plataforma pronta para lançamento comercial sem homologação e revisão de segurança.

> **Canal WhatsApp:** Z-API exclusivamente. Nenhuma rota de WhatsApp Cloud API, Twilio, Evolution, Baileys, Venom ou WPPConnect é usada.

## O que já existe

- Painel web estático responsivo e API FastAPI; cadastro de empresas pelo administrador da plataforma; autenticação por Argon2/JWT e seleção explícita do tenant pelo backend.
- PostgreSQL 16 com pgvector e usuário de aplicação separado do superuser; Redis para fila Celery e limite distribuído de tentativas de login. Serviços de dados não têm portas publicadas para a internet.
- Adaptador central Z-API para envio de texto, consulta de status e configuração do webhook de mensagem recebida; callback HTTPS com segredo aleatório próprio, segredo guardado como hash, minimização de payload e deduplicação.
- Credenciais Z-API e chaves de provedores de IA cifradas no backend com Fernet. A chave mestra é gerada localmente e não deve ser perdida ou compartilhada.
- Agentes por empresa, configuração textual Groq, xAI Responses e endpoints OpenAI-compatible, histórico de conversa, janela configurável de 3 segundos para agrupar fragmentos e verificação de revisão antes de enviar uma resposta automática.
- Ingestão de documentos suportados pelo painel, embeddings de 1536 dimensões e recuperação RAG escopada por tenant. O backend limita o tamanho das requisições e a URL dos provedores a HTTPS com resolução pública.
- Compose para API, worker, PostgreSQL/pgvector, Redis e Caddy com TLS automático. Scripts locais de backup criptografado e restauração, com confirmação destrutiva.
- Bootstrap interativo sem usuário/senha padrão no código. Testes unitários usam HTTP simulado e não contatam a Z-API ou provedores.

## Limites importantes desta versão

Esta entrega ainda **não** implementa cobrança/assinaturas SaaS, autoinscrição, gestão completa de usuários por empresa, gestão completa de consentimento e listas de bloqueio (já há opt-out e política de envio), auditoria operacional, rate limit de mensagens WhatsApp, homologação real dos callbacks de entrega, transcrição/áudio, processamento real de imagens/vídeos/documentos recebidos, envio de mídia, Google Calendar, CRM/ERP, ferramentas com efeito externo, execução de Groq Tools, xAI Agent Tools ou servidores MCP, nem aprendizado contínuo validado. O código de xAI e Groq nesta versão é de **texto**; não presume compatibilidade com as APIs de ferramentas. Há somente um grafo de resposta inicial, não um sistema completo de múltiplos agentes especializados.

O histórico recente é persistido; há suporte interno a itens de memória e checkpoints, mas ainda falta interface/workflow completo para curadoria de memória individual e aprovação de conhecimento. O RAG usa vetores com 1536 dimensões: configure um endpoint/modelo de embeddings compatível com essa dimensão; a API de chat e a de embeddings podem ser diferentes.

A preparação de infraestrutura foi validada localmente com build Docker, testes em Python 3.12 e inicialização de PostgreSQL/pgvector, Redis, API e worker, além de backup criptografado e restauração em stack isolada. TLS público, conexão Z-API, webhooks reais, envio/recebimento e implantação na VPS ainda precisam de homologação com domínio e credenciais reais. Os testes locais não equivalem aos critérios de aceite da integração real.

## Arquitetura e documentação

A proposta técnica com comparação de projetos open source, decisões, estrutura de dados, fases e fontes está em [`docs/architecture-proposal.md`](docs/architecture-proposal.md). Fatos verificados para Hostinger, Groq, xAI e o contrato Z-API usado pelo MVP estão em [`docs/providers-and-hosting.md`](docs/providers-and-hosting.md). O passo a passo de VPS está em [`docs/deploy-hostinger.md`](docs/deploy-hostinger.md), e controles/limitações operacionais em [`docs/security-and-operations.md`](docs/security-and-operations.md). Critérios pendentes são mantidos em [`TODO.md`](TODO.md).

## Stack

- **Dependências:** versões de produção fixadas em `backend/requirements.lock`; atualizações devem regenerar esse arquivo e passar pela validação.
- **API/runtime:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic e Pydantic Settings.
- **Segurança:** Argon2 para senhas, JWT curto, Fernet para credenciais, segredo hash de callback, limite de login no Redis e validação SSRF para destinos de IA/embeddings.
- **Dados/filas:** PostgreSQL 16 + pgvector, Redis 7 e Celery; LangGraph com checkpoint PostgreSQL no fluxo de resposta.
- **Web:** HTML, CSS e JavaScript sem Node em runtime; Caddy como proxy e TLS automático.
- **VPS alvo:** KVM 2 informado como 2 vCPU, 8 GB RAM e 100 GB NVMe. Limites Docker configurados: PostgreSQL 2 GiB, worker 1,5 GiB, API 1,2 GiB, Redis 384 MiB e Caddy 160 MiB (cerca de 5,2 GiB somados, além do sistema operacional e overhead). O worker tem concorrência 2; inferência de modelos é externa. Fontes e ressalvas no documento de provedores.

## Testes locais

Requer Python 3.12. Na raiz do repositório:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements-dev.txt
pytest -q
```

A suíte atual verifica senha/JWT/cifra, autorização de tenant, parser de callbacks, endpoints/payloads Z-API com HTTP simulado, caminhos de texto dos provedores e janela de agrupamento. Nunca use credenciais reais em testes unitários.

## Estado da revisão da PR #1

A revisão implementa atribuição explícita por instância, outbox serializada, recuperação
com scheduler separado e contratos de provedores/callbacks testados com transporte
simulado. A primeira publicação inicia com envio global suspenso. Consulte
[revisão e limites](docs/consolidacao/2026-11-05-revisao-pr1.md) antes de autorizar um
piloto real. As conversas brutas locais seguem o [processo privado de conhecimento](docs/conhecimento/preparacao-privada.md)
e não são importadas ou enviadas a IA automaticamente.

## Desenvolvimento e publicação

Desenvolva localmente e compartilhe por branch/PR no GitHub. A VPS recebe somente commits revisados, com checkout limpo. Veja [fluxo local → GitHub → VPS](docs/fluxo-local-github-vps.md) e o [relatório de consolidação](docs/consolidacao/2026-11-05.md). A branch consolidada contém trabalho resgatado ainda em homologação; consulte seus bloqueios antes de promover a produção.

## Implantação

Siga [`docs/deploy-hostinger.md`](docs/deploy-hostinger.md). Em resumo: aponte DNS para a VPS, abra apenas SSH/80/443, instale Docker Engine e Compose v2 no servidor, clone o repositório, execute `./scripts/init-env.sh` e `./scripts/deploy.sh`. Caddy solicita certificados ao ACME automaticamente quando o DNS e as portas estão corretos. Crie o administrador inicial com `docker compose exec api python -m app.bootstrap`.

**Não execute `docker compose down -v` em produção**: isso apaga os volumes. Não publique `.env` nem os backups. Preserve uma cópia off-site da chave Fernet e da passphrase dos backups, separada da VPS. Leia o guia antes do primeiro deploy.
