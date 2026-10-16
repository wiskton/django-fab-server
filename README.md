# 🚀 django-fab-server

**Fabric 3.x + Python 3 para provisionar servidores e gerenciar deploys isolados de aplicações Django, Node.js e PHP**

Suporta 🐧 **Ubuntu · Debian · Fedora · CentOS Stream/RHEL · Arch Linux**

---

## 🧭 Visão Geral e Arquitetura

O **django-fab-server** é uma infraestrutura de automação sem Docker que permite executar e gerenciar com segurança dezenas de aplicações independentes (Django, Node.js SSR/SPA, PHP/Laravel) em um único servidor Linux com **Nginx + Gunicorn + Supervisor + Fabric**.

```
                           ┌───────────────────────────┐
                           │   Internet / Usuários     │
                           └─────────────┬─────────────┘
                                         │ Porta 80/443
                                         ▼
                           ┌───────────────────────────┐
                           │   Nginx (Proxy Reverso)   │
                           └──────┬─────────────┬──────┘
                   Proxy HTTP/WS  │             │  Proxy HTTP
           ┌──────────────────────┘             └──────────────────────┐
           ▼                                                           ▼
┌─────────────────────────────┐                         ┌─────────────────────────────┐
│  Projeto A (ex: acmesite)   │                         │  Projeto B (ex: nodeapp)    │
│  Usuário Linux: acmesite    │                         │  Usuário Linux: nodeapp     │
│  Home: /home/acmesite (750) │                         │  Home: /home/nodeapp (750)  │
│  Gunicorn (127.0.0.1:8060)  │                         │  Node.js (127.0.0.1:8070)   │
│  Supervisor: acmesite:*     │                         │  Supervisor: nodeapp:*      │
│  Deploy: SSH acmesite       │                         │  Deploy: SSH nodeapp        │
└──────────────┬──────────────┘                         └──────────────┬──────────────┘
               │ Controle Restrito                                     │ Controle Restrito
               ▼                                                       ▼
 ┌───────────────────────────────────────────────────────────────────────────────────┐
 │               Mecanismo Restrito: /usr/local/bin/supervisorctl-restricted         │
 │  • Permite apenas: start, stop, restart, status                                   │
 │  • Valida chamador e alvos (acmesite só gerencia acmesite; nodeapp só nodeapp)   │
 │  • Socket global (/var/run/supervisor.sock) protegido (0700, root:root)           │
 └─────────────────────────────────────────┬─────────────────────────────────────────┘
                                           │
                                           ▼
                             ┌────────────────────────────────┐
                             │      Supervisord Central       │
                             │  files = /home/*/supervisor.ini│
                             └────────────────────────────────┘
```

### Pilares de Isolamento e Segurança

1. **Isolamento de Usuários Linux e Dados na Home**:
   - Cada projeto possui um usuário Linux exclusivo com sua própria pasta `/home/{usuario}/`.
   - **Todos os arquivos e dados ficam na home do usuário**: as configurações do projeto (`supervisor.ini`, `nginx.conf`), ambiente virtual (`env/`), código (`project/`), chaves (`.ssh/`) e logs (`logs/`) permanecem estritamente dentro de `/home/{usuario}/`.
   - O Supervisor central lê os processos diretamente via `files = /home/*/supervisor.ini` e o Nginx via `include /home/*/nginx.conf;`, sem copiar arquivos para fora da home.
   - Permissões estritas `chmod 750 /home/{usuario}` impedem que um usuário visualize ou modifique arquivos de outro projeto.
   - O worker do Nginx (`www-data`, `nginx` ou `http`) é adicionado ao grupo do projeto para ler estáticos e mídia sem abrir o diretório para outros usuários.
   - Chaves SSH protegidas com `chmod 700 /home/{usuario}/.ssh` e `chmod 600 authorized_keys`.
   - `umask 027` definido no login garante que novos arquivos e `.env` nunca fiquem legíveis publicamente.

2. **Supervisor Central com Gerenciamento Restrito**:
   - Uma única instância do Supervisor gerencia todos os processos sem desperdício de memória RAM.
   - O socket unix `/var/run/supervisor.sock` é restrito com `chmod 0700` (root:root) — nenhum usuário comum tem acesso administrativo global.
   - Cada usuário recebe regra em `/etc/sudoers.d/{usuario}` autorizando **apenas** o script `/usr/local/bin/supervisorctl-restricted {usuario} *`.
   - O wrapper restrito bloqueia comandos globais (`shutdown`, `reload`, `update`, `all`) e impede que o Usuário A controle os processos do Usuário B.
   - Sinais de terminação elegantes (`stopsignal=QUIT` para Gunicorn, `TERM` para Celery e Node).
   - `stopasgroup=true` e `killasgroup=true` garantem encerramento de todos os processos filhos, evitando processos zumbis ou duplicados.
   - Rotação automática de logs (`maxbytes=10MB`, `backups=5`).

3. **Deploy Independente via SSH Sem Root**:
   - Deploys rotineiros conectam diretamente com o usuário do projeto via SSH (`fab deploy`).
   - Não requer credenciais de root para atualizar código, rodar migrações, compilar estáticos ou reiniciar a aplicação.
   - Deploys nunca executam `systemctl restart supervisor` ou `systemctl restart nginx`.
   - Falhas no deploy (ex: erro no `pip install` ou `migrate`) abortam a execução antes do restart.

---

## 📋 Índice

- [📁 Estrutura de Pastas](#-estrutura-de-pastas)
- [✅ Requisitos](#-requisitos)
- [⚙️ Instalação](#️-instalação)
- [🔑 Acesso SSH](#-acesso-ssh)
- [🐧 Distros Suportadas](#-distros-suportadas)
- [📜 Provisionamento do Servidor (`server/`)](#-provisionamento-do-servidor-server)
- [🚀 Deploy do Cliente (`client/`)](#-deploy-do-cliente-client)
- [🔄 Migração de Projetos Antigos](#-migração-de-projetos-antigos)
- [🌐 Exemplo Completo: Criando um Site](#-exemplo-completo-criando-um-site)
- [⚙️ Celery Worker e Beat](#️-celery-worker-e-beat)
- [🔒 Mecanismos de Segurança em Detalhe](#-mecanismos-de-segurança-em-detalhe)
- [🧪 Testes Automatizados](#-testes-automatizados)

---

## 📁 Estrutura de Pastas

| Pasta / Arquivo | Descrição |
|---|---|
| `server/` | `fabfile.py` para **administração e provisionamento** (`newserver`, `newaccount`, `migrate-account`...) |
| `server/inc/` | Templates Jinja2 (Nginx, Supervisor, Sudoers, FTP) e script `supervisorctl-restricted` |
| `client/` | `fabfile.py` **cliente**: copiado para dentro do seu projeto para gerenciar deploy independente (`fab deploy`, `fab restart`, `fab status`...) |
| `html/` | Documentação técnica ([NEWDEV.md](html/NEWDEV.md), [NEWSERVER.md](html/NEWSERVER.md)) |
| `tests/` | Suíte de testes unitários e de integração com pytest |

---

## ✅ Requisitos

- Servidor Linux com Ubuntu, Debian, Fedora, CentOS Stream/RHEL ou Arch Linux
- Python 3.10+
- `Fabric>=3.2.0`
- `Jinja2>=3.1.0`

---

## ⚙️ Instalação

```bash
# 1. Clonar o repositório
git clone git@github.com:wiskton/django-fab-server.git
cd django-fab-server

# 2. Criar e ativar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows

# 3. Instalar dependências
pip install -r requirements.txt
```

Para provisionar servidores, crie seu `server/local_settings.py`:

```bash
cd server
cp local_settings-template.py local_settings.py
```

Edite `server/local_settings.py` com o IP (`host`), usuário administrativo (`user = "root"`) e caminho da chave privada (`chave`).

---

## 🔑 Acesso SSH

Configure o acesso via chave SSH antes do primeiro provisionamento:

```bash
ssh-keygen -t ed25519 -C "admin@exemplo.com"
ssh-copy-id root@SEU_IP_DO_SERVIDOR
ssh root@SEU_IP_DO_SERVIDOR  # confirma login sem senha
```

---

## 🐧 Distros Suportadas

Configure a família do SO na variável `os_family` em `local_settings.py`:

```python
os_family = "debian"  # "debian" (Ubuntu/Debian), "fedora", "rhel" ou "arch"
```

| `os_family` | Distros | Gerenciador | Banco de Dados | FTP | Supervisor Conf |
|---|---|:---:|:---:|:---:|:---:|
| `debian` | Ubuntu, Debian | `apt` | MySQL | proftpd | `/home/*/supervisor.ini` |
| `fedora` | Fedora | `dnf` | MariaDB | proftpd | `/home/*/supervisor.ini` |
| `rhel` | CentOS Stream, RHEL, Rocky, Alma | `dnf` (+ EPEL) | MariaDB | proftpd | `/home/*/supervisor.ini` |
| `arch` | Arch Linux, Manjaro | `pacman` | MariaDB | vsftpd | `/home/*/supervisor.ini` |

---

## 📜 Provisionamento do Servidor (`server/`)

Execute dentro da pasta `server/`:

```bash
cd server
fab --list
```

### Comandos de Administração

| Comando | Descrição |
|---|---|
| `fab newserver` | Provisiona o servidor completo do zero (pacotes, Nginx, Supervisor com socket restrito, controller seguro, banco de dados, FTP) |
| `fab newaccount` | Cria uma nova conta de projeto com usuário Linux, pasta 750, venv, supervisor conf, sudoers e Nginx sem reiniciar outros projetos |
| `fab delaccount` | Exclui conta do Linux, banco de dados, regras de sudoers e configurações do Supervisor |
| `fab listaccount` | Lista as contas existentes em `/home/` |
| `fab migrate-account` | Migra uma conta existente para o modelo de isolamento seguro e controle restrito com backup prévio |
| `fab migrate-all-projects` | Detecta todos os projetos no servidor e migra um a um com backup automático |
| `fab rollback-migration` | Restaura as permissões anteriores e arquivos a partir do backup automático gerado na migração |
| `fab install-ssl` | Instala Certbot e ativa certificado Let's Encrypt para o domínio |
| `fab nginx-reload` | Valida com `nginx -t` e recarrega o Nginx sem derrubar conexões ativas |

---

## 🚀 Deploy do Cliente (`client/`)

Copie o arquivo `client/fabfile.py` para a raiz do seu projeto:

```bash
cp django-fab-server/client/fabfile.py meu-projeto/fabfile.py
```

Configure as variáveis no topo do `fabfile.py` do projeto ou responda aos prompts interativos:
- `username = "meusite"` (o mesmo criado no `newaccount`)
- `host = "IP_DO_SERVIDOR"`
- `branch = "main"`

### Comandos de Deploy (Sem Necessidade de Root)

```bash
# Setup inicial (chaves SSH, clone e bootstrap)
fab config

# Deploy unificado (auto-detecta Django, PHP ou Node.js)
fab deploy

# Deploys específicos por linguagem:
fab deploy-python   # git pull, venv pip install, migrate, collectstatic, restart restrito, health-check
fab deploy-npm      # git pull, npm ci/install, npm run build, restart restrito (se SSR), health-check
fab deploy-php      # git pull, composer install, artisan migrate/cache, health-check

# Consultar status dos processos do projeto no Supervisor:
fab status

# Reiniciar somente os processos do projeto no Supervisor:
fab restart

# Health-check HTTP contra o domínio configurado:
fab health-check
```

---

## 🔄 Migração de Projetos Antigos

Se você já possui um servidor em produção com múltiplos projetos em funcionamento:

### Migrar um Projeto Específico:
```bash
cd server
fab migrate-account
# Digite o nome da conta (ex: meusite)
```

O comando realiza automaticamente:
1. Criação de backup completo em `/home/{conta}/.backup_migration_{timestamp}/` (`supervisor.ini`, `nginx.conf`, `sudoers`).
2. Instalação do `/usr/local/bin/supervisorctl-restricted` em `/usr/local/bin` (0755, root:root).
3. Criação da regra restrita em `/etc/sudoers.d/{conta}` com permissão `0440` (validada com `visudo -cf`).
4. Ajuste de permissões de isolamento `chmod 750 /home/{conta}` e inclusão do usuário do Nginx no grupo da conta.
5. Validação e preservação da configuração diretamente em `/home/{conta}/supervisor.ini`.
6. Atualização no Supervisor via `supervisorctl reread && supervisorctl update` **sem reiniciar outros projetos**.
7. Teste de status executado como o próprio usuário da conta.

### Migrar Todos os Projetos de uma Vez:
```bash
cd server
fab migrate-all-projects
```

### Reverter em Caso de Imprevisto:
```bash
cd server
fab rollback-migration --conta=meusite
```

---

## 🌐 Exemplo Completo: Criando um Site

### 1. No Servidor (como administrador)
```bash
cd server
fab newaccount
```
Responda:
- **Nome da conta**: `apploja`
- **Domínio**: `loja.exemplo.com.br`
- **Linguagem**: `1` (PYTHON / Django)
- **Porta**: `8010`
- **Pasta wsgi/settings**: `config`

O script cria:
- Usuário Linux `apploja` com home `chmod 750`
- Grupo `apploja` com `www-data` associado
- Virtualenv Python 3 em `/home/apploja/env`
- Configuração Nginx em `/home/apploja/nginx.conf`
- Configuração Supervisor em `/home/apploja/supervisor.ini`
- Permissão de controle restrito em `/etc/sudoers.d/apploja`
- Banco de dados MySQL e usuário local `apploja`

### 2. No Repositório do Projeto (como desenvolvedor)
```bash
fab config
# Copie a chave SSH exibida para o GitHub > Deploy Keys
fab deploy
fab enable-ssl
```

---

## ⚙️ Celery Worker e Beat

Para projetos Python com tarefas assíncronas:
```bash
fab setup-celery
```
Configura Redis e gera os programas no Supervisor:
- `[program:{conta}]` (Gunicorn)
- `[program:{conta}_celery_worker]` (Celery Worker)
- `[program:{conta}_celery_beat]` (Celery Beat)
- `[group:{conta}]` (Grupo unificado)

Os comandos `fab restart` e `fab status` gerenciam o grupo `{conta}:*` de forma atômica e segura.

---

## 🔒 Mecanismos de Segurança em Detalhe

| Vetor de Risco | Medida Implementada |
|---|---|
| **Acesso entre projetos vizinhos** | `/home/{user}` configurado com `chmod 750` e `chown {user}:{user}`. Usuário B recebe *Permission Denied* ao tentar listar ou acessar arquivos de A. |
| **Controle abusivo do Supervisor** | Socket `/var/run/supervisor.sock` restrito com `0700` (root). Sem permissões gerais de `sudo supervisorctl`. Wrapper restrito valida chamador e limita ações a `start, stop, restart, status` sobre processos do próprio usuário. |
| **Paradas globais acidentais** | `shutdown`, `reload`, `update` e alvos globais (`all`, `*`) são estritamente bloqueados para usuários comuns. |
| **Processos zumbis / órfãos** | `stopasgroup=true` e `killasgroup=true` encerram a árvore inteira de processos na reinicialização. |
| **Injeção de comandos shell** | `supervisorctl-restricted` usa `subprocess.run` com array de argumentos (sem `shell=True`) e sanitização de regex. |
| **Exposição de arquivos sensíveis** | Nginx bloqueia arquivos ocultos (`.env`, `.git`). `umask 027` no login garante permissão `640` em novos arquivos. |

---

## 🧪 Testes Automatizados

A suíte de testes com `pytest` valida toda a segurança, controle restrito e templates:

```bash
pip install pytest
pytest
```

**114 testes passando (100% de sucesso)**, cobrindo:
- Autorização e rejeição de acessos indevidos no `supervisorctl-restricted`
- Validação estrita de alvos e sanitização contra shell injection
- Permissões de isolamento (750), sudoers (0440) e socket unix (0700)
- Preservação dos outros tenants durante deploy e newaccount
- Interrupção de deploy em caso de erro antes de reiniciar processos
- Recuperação automática em reinicialização do servidor (`autostart=true`)
- Reinicialização automática em caso de falha (`autorestart=true`)
- Suporte multi-distro (Debian, Ubuntu, Fedora, RHEL, Arch Linux)
