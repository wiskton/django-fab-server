# 🚀 django-fab-server

**Fabric 3.x + Python 3 para provisionar servidores e fazer deploy de projetos Django/PHP**

Suporta 🐧 **Ubuntu · Debian · Fedora · CentOS Stream/RHEL · Arch Linux**

## 🧭 Como funciona

É um conjunto de automações em `fabfile.py` que acessa o servidor via SSH e instala/configura tudo que um site em Django (Python) ou PHP precisa: Nginx, banco de dados (MySQL/MariaDB), Supervisor (Gunicorn) ou php-fpm, FTP (ProFTPD/vsftpd), compilação de traduções (gettext) e certificados SSL gratuitos (Let's Encrypt / Certbot).

## 📋 Índice

- [📁 Estrutura de pastas](#estrutura-de-pastas)
- [✅ Requisitos](#requisitos)
- [⚙️ Instalação](#instalação)
- [🔑 Acesso SSH](#acesso-ssh)
- [🐧 Distros suportadas](#distros-suportadas)
- [📜 Comandos de Provisionamento (`server/`)](#comandos-de-provisionamento-server)
- [🚀 Comandos de Deploy do Cliente (`client/`)](#comandos-de-deploy-do-cliente-client)
- [🌐 Exemplo: criando um site novo](#exemplo-criando-um-site-novo)
- [🔒 Segurança](#segurança)
- [🧪 Testes](#testes)
- [🐳 Docker](#docker)
- [🏗️ Estrutura interna](#estrutura-interna)

## 📁 Estrutura de pastas

| Pasta         | O que tem |
|---------------|-----------|
| `server/`     | `fabfile.py` que **provisiona** o servidor do zero (`newserver`, `newaccount`, `install-ssl`, `nginx-restart`...) |
| `server/inc/` | templates Jinja2 (Nginx, Supervisor, ProFTPD/vsftpd) usados pelo provisionamento |
| `client/`     | `fabfile.py` **"cliente"**: copie sozinho para dentro do SEU projeto Django/PHP para gerenciar deploy (`fab deploy`, `fab enable-ssl`, `fab config`...) |
| `html/`       | documentação detalhada ([NEWDEV.md](html/NEWDEV.md), [NEWSERVER.md](html/NEWSERVER.md)) |
| `tests/`      | testes automatizados (pytest) com cobertura 100% dos comandos e templates |

> `server/` e `client/` são independentes — `client/fabfile.py` não importa nada de `server/`, sendo feito para ser copiado, sozinho, para dentro de outro repositório.

## ✅ Requisitos

- Servidor Ubuntu, Debian, Fedora, CentOS Stream/RHEL ou Arch Linux
- Python 3.10+
- `Fabric>=3.2.0`
- `Jinja2>=3.1.0`

## ⚙️ Instalação

```bash
# 1. Clonar o repositório
git clone git@github.com:wiskton/django-fab-server.git
cd django-fab-server

# 2. Criar e ativar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependências
pip install -r requirements.txt
```

Para provisionar servidores, configure o arquivo local (nunca versionado):

```bash
cd server
cp local_settings-template.py local_settings.py
```

Edite `server/local_settings.py` com o IP (`host`), usuário (`user = "root"`) e caminho da chave privada (`chave`).

## 🔑 Acesso SSH

Antes de rodar `fab newserver`, configure o acesso sem senha via chave SSH:

```bash
# 1. Gerar chave SSH (se ainda não possuir)
ssh-keygen -t ed25519 -C "seu-email@exemplo.com"

# 2. Copiar a chave pública para o servidor
ssh-copy-id root@SEU_IP_DO_SERVIDOR

# 3. Testar a conexão
ssh root@SEU_IP_DO_SERVIDOR
```

## 🐧 Distros suportadas

Defina a distro do servidor na variável `os_family` do `local_settings.py`:

```python
os_family = "debian"  # "debian" (Ubuntu/Debian), "fedora", "rhel" ou "arch"
```

| `os_family` | Distros | Gerenciador | Banco de Dados | FTP | SSL / Certbot |
|---|---|:---:|:---:|:---:|:---:|
| `debian` | Ubuntu, Debian | `apt` | MySQL | proftpd | `certbot python3-certbot-nginx` |
| `fedora` | Fedora | `dnf` | MariaDB | proftpd | `certbot python3-certbot-nginx` |
| `rhel` | CentOS Stream, RHEL, Rocky, Alma | `dnf` (+ EPEL) | MariaDB | proftpd | `certbot python3-certbot-nginx` |
| `arch` | Arch Linux, Manjaro | `pacman` | MariaDB | **vsftpd** | `certbot certbot-nginx` |

## 📜 Comandos de Provisionamento (`server/`)

Execute dentro da pasta `server/`:

```bash
cd server
fab --list
```

| Categoria | Comandos Principais |
|---|---|
| 🖥️ **Servidor** | `newserver` (setup completo do servidor do zero) · `newaccount` (Python, PHP ou NPM/Node.js) · `delaccount` · `listaccount` |
| 🔒 **SSL / HTTPS** | `install-ssl` (instala Certbot e ativa certificado Let's Encrypt no Nginx) |
| 📦 **Pacotes** | `build-server` (inclui `gettext`/`msgfmt`) · `python-server` · `node-server` (Node.js + NPM) · `mysql-server` · `git-server` · `others-server` |
| 🗄️ **Banco de Dados** | `newbase` · `dropbase` · `mysql-start` · `mysql-stop` · `mysql-restart` |
| 🌐 **Nginx** | `nginx-start` · `nginx-stop` · `nginx-restart` · `nginx-reload` |
| 🧩 **Supervisor** | `supervisor-start` · `supervisor-stop` · `supervisor-restart` · `start-server` · `stop-server` · `restart-server` |
| 📁 **FTP** | `proftpd-restart` (ou `vsftpd` no Arch) |
| 👤 **Acesso** | `adduser` · `userdel` · `login` · `upload-public-key` |
| 🔁 **Sistema** | `restart` · `reboot` |

---

## 🚀 Comandos de Deploy do Cliente (`client/`)

Copie o arquivo `client/fabfile.py` para a raiz do seu projeto (**Django/Python**, **PHP** ou **NPM/Node.js**):

```bash
cp /caminho/django-fab-server/client/fabfile.py /caminho/meu-projeto/fabfile.py
```

Abra o terminal na pasta do seu projeto e utilize os comandos:

```bash
# Setup inicial do projeto no servidor (gera chaves, clona e prepara ambiente)
fab config

# Deploy unificado (auto-detecta Python, PHP ou NPM)
fab deploy

# Ou force o deploy específico por linguagem:
fab deploy-python   # pip install, npm build (se houver), migrate, gettext, collectstatic, supervisor restart
fab deploy-php      # composer install, npm build (se houver), artisan (Laravel), reload php-fpm/nginx
fab deploy-npm      # npm ci/install, npm run build, supervisor restart (SSR) ou reload nginx (SPA)

# Utilitários NPM e Composer
fab npm-install
fab npm-build
fab update-composer
fab reload-php

# Ativar certificado SSL gratuito (HTTPS com Let's Encrypt)
fab enable-ssl

# Criar superusuário administrador no servidor (Django)
fab createsuperuser

# Corrigir diretivas do Supervisor (suporta Python e Node.js)
fab fix-supervisor

# Acessar sessão SSH direta no servidor dedicado
fab login

# Executar comandos do Django no servidor
fab manage:cmd="migrate"
fab manage:cmd="dbshell"
```

---

## 🌐 Exemplo: Criando um Site Novo do Zero

### Passo 1: Provisionar o Servidor
```bash
cd server
fab newserver
```
*(Instala Nginx, MySQL/MariaDB, Python, Node.js, NPM, Supervisor, Git, Gettext, Certbot e FTP).*

### Passo 2: Criar a Conta do Site
```bash
fab newaccount
```

**Opção A — Python / Django:**
```text
Digite o nome da conta: meudominio
Digite o domínio do site (sem www): meudominio.com
Escolha a linguagem: 1 (PYTHON)
Digite o número de uma porta livre: 8002
Digite o nome da pasta settings/wsgi: config
```

**Opção B — PHP:**
```text
Digite o nome da conta: meudominio
Digite o domínio do site (sem www): meudominio.com
Escolha a linguagem: 2 (PHP)
```

**Opção C — NPM / Node.js (SSR / API com Supervisor ou Frontend Estático SPA):**
```text
Digite o nome da conta: meudominio
Digite o domínio do site (sem www): meudominio.com
Escolha a linguagem: 3 (NPM)
Tipo de aplicação NPM: 1 (Node.js SSR / API) ou 2 (Frontend Estático / SPA)
Digite a porta (se SSR): 8070
Comando de start (se SSR): npm run start
```

### Passo 3: Configurar o Projeto no Servidor
Na pasta do seu projeto (Django, PHP ou Node/NPM):
```bash
fab config
# Copie a chave SSH exibida e adicione em: GitHub > Settings > Deploy Keys
fab deploy
fab enable-ssl
```

---

## 🔒 Segurança

- **Banco de Dados**: Credenciais e comandos SQL não trafegam na linha de comando (`ps aux` protegido); senhas são transmitidas via arquivos temporários protegidos por permissão `600`.
- **Nginx**: Bloqueia arquivos ocultos (`.env`, `.git`, `.htaccess`), desabilita listagem de diretórios (`autoindex off`), aplica cabeçalhos `X-Content-Type-Options`, `X-Frame-Options` e `Referrer-Policy`. Suporte a WebSockets para Node.js.
- **Gunicorn / Node.js no Supervisor**: Executa sob usuário Linux isolado com variáveis de ambiente dedicadas.
- **SSL / HTTPS**: Renovação automática via Certbot com suporte a domínios principais e subdomínios `static` e `media`.

---

## 🧪 Testes Automatizados

O projeto inclui suíte completa de testes com `pytest`:

```bash
pip install pytest
pytest
```
*Cobertura: 69 testes unitários validando tabelas multi-distro, sintaxe Jinja2, tarefas do Fabric e simulação de novas contas Python, PHP e NPM.*
