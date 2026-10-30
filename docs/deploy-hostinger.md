# Passo a passo — criar e configurar a VPS Hostinger

**Atualizado em 30/10/2026.** O roteiro assume que você já contratou o plano KVM 2 e quer hospedar o MVP Orquestra. Os nomes dos botões do hPanel podem variar ligeiramente.

## Primeiro: corrigir o erro de Python que você enviou

O log indica Python 3.9. A criação do ambiente virtual falhou porque falta o pacote `venv`; depois disso, `pip install` parece ter iniciado fora de um ambiente virtual e instalado pacotes no diretório `~/.local`. Se esse comando ainda estiver executando, interrompa-o com `Ctrl+C`. Não tente remover esses pacotes do Python global.

O projeto usa Python 3.12 dentro do Docker e requer ao menos Python 3.10 para testes locais. O caminho mais simples para testar localmente é Ubuntu 24.04 com Python 3.12:

```bash
sudo apt update
sudo apt install -y python3.12-venv
cd ~/Documentos/orchestra-saas
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-dev.txt
pytest -q
```

Se `python3.12` não existir, confira com `python3 --version`. `sudo apt install python3-venv` corrige o erro de `ensurepip` para o Python padrão do sistema, mas **não torna Python 3.9 compatível com o código atual**. Use Python 3.12 para testes. Isso não impede a implantação: na VPS, a aplicação roda nos contêineres Python 3.12 e não depende do Python instalado no host.

## 1. Escolher o sistema operacional

No hPanel, abra **VPS → Configurar/Manage** e conclua a ativação. Na escolha de imagem, use **Plain OS → Ubuntu 24.04 LTS 64-bit**. Evite Ubuntu Desktop, painéis como CyberPanel/CloudPanel e imagens de aplicativos. Este produto usa Docker Compose e Caddy, então um sistema limpo reduz serviços e portas desnecessários. A Hostinger lista Ubuntu 24.04 e 26.04 como imagens simples e também oferece imagem Docker baseada em Ubuntu 24.04. Docker Engine declara suporte a ambas as LTS, mas recomendo 24.04 para este primeiro deploy por ser uma base mais madura e amplamente usada.[1] [2]

Escolha o datacenter mais próximo da maioria dos seus clientes, se a região desejada estiver disponível. Defina um hostname identificável, por exemplo `orquestra-prod-01`. Crie uma senha root longa, única e guarde-a em um gerenciador de senhas. Registre o IPv4 público da VPS. Se já existir uma instalação que você queira preservar, **não troque nem reinstale o sistema**: a reinstalação apaga os dados da VPS.[3]

## 2. Criar e cadastrar a chave SSH

No seu computador, abra Terminal (macOS/Linux) ou PowerShell (Windows) e gere uma chave dedicada:

```bash
ssh-keygen -t ed25519 -C "orquestra-hostinger" -f ~/.ssh/orquestra_hostinger
```

No Windows PowerShell, o comando equivalente é:

```powershell
ssh-keygen -t ed25519 -C "orquestra-hostinger" -f "$env:USERPROFILE\.ssh\orquestra_hostinger"
```

Escolha uma frase-senha para a chave. O arquivo `orquestra_hostinger.pub` é a chave **pública**, que pode ser cadastrada no hPanel. O arquivo sem `.pub` é a chave privada: nunca a envie a ninguém. A Hostinger permite adicionar chaves em **VPS → seu servidor → Settings/Configurações → SSH keys**; em alguns fluxos, a opção aparece durante a ativação.[4]

Conecte-se primeiro como `root`, usando a chave quando estiver configurada:

```bash
ssh -i ~/.ssh/orquestra_hostinger root@IP_DA_VPS
```

Se preferir, use o Terminal disponível no painel Hostinger para o primeiro acesso. Confirme o fingerprint do servidor quando o cliente SSH perguntar.

## 3. Atualizar o Ubuntu e criar um usuário de operação

Já conectado como `root`, atualize o sistema e instale utilitários básicos:

```bash
apt update && apt upgrade -y
apt install -y sudo curl ca-certificates gnupg ufw fail2ban unattended-upgrades unzip
 timedatectl set-timezone America/Sao_Paulo
hostnamectl set-hostname orquestra-prod-01
```

Na linha `timedatectl`, remova o espaço inicial antes do comando se copiar o bloco. Depois reinicie para aplicar atualizações de kernel, se houver:

```bash
reboot
```

Reconecte-se e crie um usuário normal chamado `orquestra`:

```bash
adduser orquestra
usermod -aG sudo orquestra
```

Escolha uma senha forte para esse usuário. Instale a chave pública para ele antes de desligar acesso por senha. Do seu computador, macOS/Linux:

```bash
ssh-copy-id -i ~/.ssh/orquestra_hostinger.pub orquestra@IP_DA_VPS
```

No Windows, se `ssh-copy-id` não estiver disponível, adicione o conteúdo da chave `.pub` a `/home/orquestra/.ssh/authorized_keys` usando o Terminal do hPanel. No servidor, os comandos são:

```bash
install -d -m 700 -o orquestra -g orquestra /home/orquestra/.ssh
nano /home/orquestra/.ssh/authorized_keys
```

Cole a linha pública inteira, salve e aplique as permissões:

```bash
chown -R orquestra:orquestra /home/orquestra/.ssh
chmod 700 /home/orquestra/.ssh
chmod 600 /home/orquestra/.ssh/authorized_keys
```

**Antes de endurecer o SSH, abra uma segunda janela no computador e valide**:

```bash
ssh -i ~/.ssh/orquestra_hostinger orquestra@IP_DA_VPS
sudo whoami
```

O segundo comando deve responder `root`. Mantenha a sessão original ou o Terminal do hPanel aberto até terminar o próximo passo. Só então desligue login SSH de root e por senha:

```bash
sudo tee /etc/ssh/sshd_config.d/00-orquestra-hardening.conf >/dev/null <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
EOF
sudo sshd -t
sudo sshd -T | grep -E '^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication) '
sudo systemctl reload ssh
```

Confirme que a saída mostra `permitrootlogin no`, `passwordauthentication no`, `kbdinteractiveauthentication no` e `pubkeyauthentication yes`. Teste de novo uma nova conexão como `orquestra`. Se algo falhar, não feche a sessão já aberta e volte a ajustar o arquivo pelo hPanel. Não é necessário trocar a porta SSH nesta primeira instalação.

## 4. Configurar os dois firewalls

### Firewall Hostinger

No hPanel, abra **VPS → seu servidor → Security/Segurança → Firewall**, crie um grupo, adicione as regras e ative-o na VPS. A política gerenciada descarta tráfego que não esteja explicitamente permitido.[5]

| Protocolo | Porta | Origem | Necessidade |
|---|---:|---|---|
| TCP | 22 | Seu IP público, se for estático; caso contrário, qualquer origem | SSH. Mantenha somente com autenticação por chave. |
| TCP | 80 | Qualquer origem | HTTP e validação/redirecionamento TLS do Caddy. |
| TCP | 443 | Qualquer origem | Painel/API HTTPS. |
| UDP | 443 | Qualquer origem | Opcional; HTTP/3 do Caddy. HTTPS continua funcionando sem esta regra. |

**Não abra** 5432 (PostgreSQL), 6379 (Redis) nem 8000 (API). O Compose do projeto não publica essas portas.

### Firewall Ubuntu (UFW)

Como `orquestra`, permita SSH e web **antes** de ativar o UFW:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw enable
sudo ufw status verbose
```

O Docker alerta que portas de contêiner publicadas podem passar pelas regras do UFW. Por isso, mantenha o firewall de borda Hostinger ativo e revise `docker-compose.yml`: neste projeto, apenas Caddy publica 80/443; banco, Redis e API permanecem internos.[6] [7]

Ative Fail2ban para reduzir tentativas repetidas de login SSH:

```bash
sudo tee /etc/fail2ban/jail.d/sshd.local >/dev/null <<'EOF'
[sshd]
enabled = true
backend = systemd
maxretry = 5
findtime = 10m
bantime = 1h
EOF
sudo systemctl enable --now fail2ban
sudo fail2ban-client status sshd
```

Deixe atualizações de segurança automáticas habilitadas. Confira o timer após instalar o pacote:

```bash
sudo dpkg-reconfigure --priority=low unattended-upgrades
systemctl list-timers apt-daily-upgrade.timer
```

Escolha **Yes/Sim** quando for perguntado se deseja instalar atualizações de segurança automaticamente.

## 5. Instalar Docker Engine e Compose

A instalação oficial do Docker suporta Ubuntu 24.04 LTS. Entre como `orquestra` e cadastre o repositório oficial do Docker:[6]

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run hello-world
```

Para executar o Compose sem `sudo`, inclua o usuário `orquestra` no grupo `docker` e abra uma nova sessão:

```bash
sudo usermod -aG docker orquestra
```

Saia do SSH e entre novamente; então verifique:

```bash
docker --version
docker compose version
docker run hello-world
```

Atenção: o grupo `docker` concede privilégios equivalentes a root. Mantenha esse grupo restrito a quem administra a VPS.[8]

## 6. Apontar um subdomínio

Use um subdomínio dedicado, como `app.seudominio.com`; não é necessário mover o domínio nem alterar os registros de e-mail. No editor DNS da Hostinger (ou do registrador atual), crie:

- Tipo: `A`
- Host/Nome: `app`
- Aponta para: IPv4 público da VPS
- TTL: padrão

A Hostinger documenta esse formato de host para subdomínios e alerta que a propagação pode levar até 24 horas.[9] Remova apenas registros conflitantes de `app` (A, CNAME ou AAAA antigo); não apague MX/SPF/DKIM. Não crie registro AAAA se não tiver IPv6 funcional apontado para esta VPS.

Confira a resolução no seu computador:

```bash
getent ahostsv4 app.seudominio.com
```

O IP retornado deve ser o da VPS. Substitua `app.seudominio.com` em todas as etapas seguintes pelo seu domínio real.

## 7. Transferir o projeto e iniciar os serviços

Baixe o arquivo [Orquestra SaaS MVP — ZIP](/home/ubuntu/orquestra-saas-mvp.zip) para seu computador. Em macOS/Linux, envie-o por SSH:

```bash
scp -i ~/.ssh/orquestra_hostinger ~/Downloads/orquestra-saas-mvp.zip orquestra@IP_DA_VPS:/tmp/
```

No Windows PowerShell:

```powershell
scp -i "$env:USERPROFILE\.ssh\orquestra_hostinger" "$env:USERPROFILE\Downloads\orquestra-saas-mvp.zip" orquestra@IP_DA_VPS:/tmp/
```

Conecte-se à VPS como `orquestra` e extraia o projeto em `/opt/orquestra`:

```bash
sudo test ! -e /opt/orquestra
sudo unzip -q /tmp/orquestra-saas-mvp.zip -d /opt
sudo mv /opt/orquestra-saas /opt/orquestra
sudo chown -R orquestra:orquestra /opt/orquestra
cd /opt/orquestra
chmod +x scripts/*.sh database/init/01-app-user.sh
```

Gere as senhas e chaves locais, informando a origem pública HTTPS quando solicitado:

```bash
./scripts/init-env.sh
```

O script cria `.env` com permissão `600`. Não envie esse arquivo ao GitHub nem o compartilhe. Preserve uma cópia criptografada/segura dele fora da VPS: contém `CREDENTIALS_ENCRYPTION_KEY`, necessária para decifrar chaves de API gravadas no banco.

Valide a configuração e suba o sistema:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=80 db api worker web
```

O primeiro boot instala pgvector, cria o usuário de runtime PostgreSQL e executa as migrações. Quando o DNS já apontar para a VPS e as portas 80/443 estiverem permitidas, o Caddy solicitará TLS automaticamente. Confira:

```bash
curl --fail --show-error https://app.seudominio.com/health
```

A resposta esperada começa com `{"ok":true}`. Se o certificado não sair, verifique DNS A/AAAA, o hostname `PUBLIC_DOMAIN` e as regras do firewall; consulte `docker compose logs --tail=100 web`.

Crie o administrador inicial do painel:

```bash
docker compose exec api python -m app.bootstrap
```

Depois acesse `https://app.seudominio.com`, crie a empresa/tenant e configure as próprias credenciais Z-API e IA pelo painel. Não há usuário ou senha padrão. A auto-resposta permanece desativada por padrão. Faça primeiro um teste manual com número/instância sob seu controle.

## 8. Agendar e proteger backups

O projeto contém `scripts/backup.sh`, mas não configura sozinho armazenamento off-site nem cron. Ele exige uma passphrase local protegida e grava dumps criptografados em `/opt/orquestra/backups`. Siga as instruções de [`security-and-operations.md`](security-and-operations.md), teste uma execução manual e uma restauração em ambiente separado antes de depender dela.

O backup de banco e `app_data` **não inclui `.env`**. Guarde `.env`, passphrase de backup e suas cópias fora do VPS, separadas dos arquivos de backup. Envie os arquivos criptografados para armazenamento independente; uma cópia somente no mesmo disco não protege contra falha/encerramento da VPS. Confirme também no hPanel se o seu plano oferece snapshots/backup gerenciado e qual é a retenção; isso não substitui o backup testado do aplicativo.

## 9. Checklist de conclusão

- [ ] Ubuntu 24.04 LTS 64-bit, hostname correto e sistema atualizado.
- [ ] Login SSH por chave como `orquestra`; root e autenticação SSH por senha desativados depois de testar a nova sessão.
- [ ] Firewall Hostinger aplicado e UFW ativo; abertas somente 22/TCP, 80/TCP, 443/TCP e, opcionalmente, 443/UDP.
- [ ] Docker e Compose funcionam; usuário Docker é confiável e `.env` tem permissão `600`.
- [ ] DNS A resolve para o IPv4 correto, sem AAAA inválido.
- [ ] `docker compose ps` mostra os serviços ativos e a URL HTTPS retorna saúde.
- [ ] Administrador de plataforma criado; credenciais configuradas pelo painel e primeiro teste manual concluído.
- [ ] Backup local executado, cópia off-site criada e restauração ensaiada em ambiente isolado.

## Não faça

- Não execute `docker compose down -v` em produção: isso remove os volumes do banco e dos arquivos.
- Não abra 5432, 6379 ou 8000 no firewall e não publique essas portas no Compose.
- Não desligue autenticação por senha/root antes de testar a chave SSH em uma segunda sessão.
- Não ative auto-resposta para clientes reais antes de homologar Z-API, consentimento, opt-out, limites de envio e políticas de dados. Esses controles ainda são pendentes no MVP.
- Não torne o repositório GitHub público enquanto não revisar segredos, dados, dependências e licença. GitHub privado é opcional; para este primeiro deploy, copiar o ZIP por SCP é suficiente.

## Referências oficiais

[1]: https://www.hostinger.com/support/1583571-what-are-the-available-operating-systems-for-vps-at-hostinger/ "Sistemas operacionais disponíveis para VPS Hostinger"
[2]: https://docs.docker.com/engine/install/ubuntu/ "Instalar Docker Engine no Ubuntu"
[3]: https://www.hostinger.com/support/4965922-how-to-change-the-operating-system-of-your-vps-at-hostinger/ "Alterar ou reinstalar o sistema operacional da VPS"
[4]: https://www.hostinger.com/tutorials/how-to-set-up-ssh-keys/ "Configurar chaves SSH"
[5]: https://www.hostinger.com/support/8172641-how-to-use-a-managed-vps-firewall-at-hostinger/ "Firewall gerenciado da Hostinger para VPS"
[6]: https://docs.docker.com/engine/install/ubuntu/ "Instalação do Docker e alerta de firewall no Ubuntu"
[7]: https://docs.docker.com/engine/install/ubuntu/ "Limitações de UFW e portas Docker publicadas"
[8]: https://docs.docker.com/engine/install/linux-postinstall/ "Etapas pós-instalação do Docker para Linux"
[9]: https://www.hostinger.com/support/4468886-how-to-manage-a-records-at-hostinger/ "Gerenciar registros A na Hostinger"
[10]: https://www.hostinger.com/tutorials/how-to-set-up-vps/ "Configurar uma VPS, criar usuário não-root e firewall"
