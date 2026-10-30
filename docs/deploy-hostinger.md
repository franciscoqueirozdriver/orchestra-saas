# Implantação — Hostinger VPS KVM 2

## Escopo e premissas

Este roteiro assume Ubuntu Server com acesso `sudo`, um domínio/subdomínio dedicado ao painel e uma VPS nova ou sem volumes deste produto. O KVM 2 consultado estava listado com 2 vCPU, 8 GB RAM e 100 GB de disco NVMe; confirme os recursos e as regras do firewall no painel da sua própria conta antes do deploy, pois planos podem mudar. A VPS é um único domínio de falha, não alta disponibilidade. Inferência/embeddings são serviços externos, nunca executados como modelos locais pesados na KVM 2.

**A instalação não foi executada nesta entrega**: o ambiente de desenvolvimento não tinha Docker e não havia acesso à VPS/domínio. Faça o primeiro deploy em janela controlada e valide os critérios da seção “Pós-deploy”.

## 1. Preparar DNS, VPS e firewall

1. Instale Ubuntu Server suportado pela Hostinger e confirme o acesso SSH por chave.
2. Crie um registro DNS `A` do subdomínio escolhido (por exemplo, `app.seudominio.com`) apontando ao IPv4 público da VPS. Se houver registro `AAAA`, ele também precisa apontar a um IPv6 funcional; remova o registro inválido para evitar validações TLS intermitentes.
3. No firewall da Hostinger e no firewall do sistema, permita `22/tcp` para SSH (idealmente limitado ao seu IP), `80/tcp` e `443/tcp`. `443/udp` é opcional para HTTP/3. Não publique portas de PostgreSQL, Redis ou API; o Compose já os mantém sem mapeamento público.
4. Instale Docker Engine e o plugin Docker Compose v2 conforme o procedimento oficial para sua versão do Ubuntu: [Docker Engine — instalação no Ubuntu](https://docs.docker.com/engine/install/ubuntu/). Valide `docker --version` e `docker compose version`.
5. Crie um usuário Linux de deploy com acesso restrito ao Docker. Acesso ao socket Docker equivale, na prática, a privilégio root; conceda somente a pessoas confiáveis.

## 2. Transferir o código e gerar segredos

Transfira o arquivo ZIP de entrega ou um clone privado do repositório para a VPS, extraia em, por exemplo, `/opt/orquestra`, e entre nessa pasta. Antes de iniciar:

```bash
cd /opt/orquestra
chmod +x scripts/*.sh database/init/01-app-user.sh
./scripts/init-env.sh
```

Informe somente a origem HTTPS (exemplo: `https://app.seudominio.com`), sem caminho nem porta. O script cria aleatoriamente senhas PostgreSQL (superuser e runtime separados), segredo JWT e chave Fernet, gravando `.env` com permissão `600`. As chaves de Z-API e IA serão inseridas no painel depois; não coloque-as na linha de comando, Git ou suporte.

Confira que o arquivo `.env` pertence ao usuário de deploy, mantenha-o fora do Git/backups públicos e confirme os valores de `PUBLIC_BASE_URL` e `PUBLIC_DOMAIN`. **Perder `CREDENTIALS_ENCRYPTION_KEY` torna as credenciais Z-API/LLM cifradas irrecuperáveis.** Preserve uma cópia protegida fora da VPS.

## 3. Subir os contêineres

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

O banco usa uma conta superuser apenas no contêiner PostgreSQL e cria `orquestra_app` como proprietário/usuário de runtime sem superuser. O script em `database/init/01-app-user.sh` e a extensão pgvector rodam **somente na inicialização de um volume PostgreSQL novo**. Não remova volumes existentes para “forçar” inicialização: isso apaga os dados. Se o volume já tiver sido criado por uma versão anterior do projeto, faça uma migração planejada do usuário do banco antes de subir esta configuração.

O Caddy ocupa portas 80/443 e solicita/renova certificado TLS automaticamente. Espere a propagação DNS e a emissão do certificado. O guia de saúde é:

```bash
curl --fail --show-error https://app.seudominio.com/health
```

A resposta `{"ok":true,...}` confirma que o processo API atende. Esse endpoint **não** verifica sozinho toda a disponibilidade do banco, Redis, worker ou integração externa. Para diagnósticos operacionais, use `docker compose ps` e leia seletivamente `docker compose logs api worker db redis web`; não compartilhe dumps de log sem revisar os dados.

## 4. Criar o administrador inicial e configurar empresas

Com a API em execução, rode o bootstrap interativo:

```bash
docker compose exec api python -m app.bootstrap
```

Ele só cria o primeiro administrador de plataforma se não existir outro; não há senha-padrão no repositório. Depois, acesse `https://app.seudominio.com`, autentique-se, crie uma empresa/tenant e defina o administrador dela. Não compartilhe a senha inicial por canal inseguro.

Cada empresa escolhe uma instância Z-API própria e as configurações de IA no painel. A chave é enviada ao backend por HTTPS e guardada cifrada; a API não a devolve ao navegador. Groq e xAI estão implementados **apenas para texto** neste MVP. Informe o modelo e a chave conforme sua conta/limites; o nome de modelo muda com os catálogos dos provedores. Para RAG, configure também um endpoint de embeddings compatível com 1536 dimensões (pode ser outro serviço e outra chave).

## 5. Conectar uma instância Z-API

1. Crie/prepare uma instância e obtenha `instanceId`, `token` e, quando habilitado em sua conta, `Client-Token` no painel Z-API.
2. No painel Orquestra, em **Instâncias Z-API**, cadastre credenciais da própria empresa. O backend tentará consultar/configurar o webhook oficial de recebimento em HTTPS.
3. Se a configuração automática falhar, o painel mostra uma URL única de callback para ser copiada e cadastrada no painel Z-API. Essa URL contém um segredo; guarde-a e não a publique. Se a janela for fechada antes de copiá-la, desative e recrie a instância para gerar outro segredo nesta versão.
4. Teste o estado da instância e envie somente uma mensagem autorizada a um número de teste sob seu controle. A aceitação HTTP da Z-API não equivale a confirmação de entrega ao destinatário.
5. Crie e revise o agente. Resposta automática começa desligada; mantenha-a desligada até testar conteúdo, privacidade, consentimento e escopo de destinatários. O módulo atual não implementa gestão completa de consentimento, bloqueio ou limites de envio.

A implementação segue os endpoints registrados em [`providers-and-hosting.md`](providers-and-hosting.md): enviar texto, consultar status e configurar `On Message Received`. Não substitua a Z-API por outro transporte. Mídia recebida é registrada como marcador, sem baixar ou transcrever; o envio automático ainda é de texto.

## 6. Backups e atualização

Veja [`security-and-operations.md`](security-and-operations.md) antes de agendar backups. `scripts/backup.sh` requer uma passphrase em arquivo local protegido, cria dumps do banco e de `app_data` cifrados e mantém 14 dias no disco local. Configure uma cópia off-site e monitore o resultado; o script não configura por conta própria um destino externo.

Atualize o código em janela controlada: faça backup, revise a versão, execute `docker compose up -d --build` e valide saúde e fluxos. **Nunca use `docker compose down -v` em dados de produção**. Mudanças de `CREDENTIALS_ENCRYPTION_KEY` inutilizam credenciais já cifradas; mudanças de `JWT_SECRET` encerram tokens ativos.

## 7. Pós-deploy: gates de homologação

Antes do piloto, comprovar manualmente e registrar evidência de: login e isolamento entre dois tenants; criação/consulta de uma instância real; callback recebido, duplicado e não autorizado; persistência de conversa; envio de texto e resposta aceita pela Z-API; comportamento ao desconectar provedor/worker; janela de agrupamento de mensagens; uso do RAG com chave/endpoint de embeddings real; backup e restauração em um ambiente de teste; renovação TLS e reinício dos contêineres. Não considere `/health` isoladamente como aprovação de produção.
