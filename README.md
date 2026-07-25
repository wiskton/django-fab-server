# 🚀 django-fab-server

**Fabric 3.x + Python 3 para provisionar servidores e fazer deploy de projetos Django/PHP**

Suporta 🐧 **Ubuntu · Debian · Fedora · CentOS Stream/RHEL · Arch Linux**

## 🧭 Como funciona

É um `fabfile.py` que acessa o servidor via SSH e instala/configura tudo que
um site em Django (python) ou PHP precisa: nginx, banco de dados, supervisor
(gunicorn) ou php-fpm, FTP.

## 📋 Índice

- [📁 Estrutura de pastas](#estrutura-de-pastas)
- [✅ Requisitos](#requisitos)
- [⚙️ Instalação](#instalação)
- [🐧 Distros suportadas](#distros-suportadas)
- [📜 Comandos disponíveis](#comandos-disponíveis)
- [🌐 Exemplo: criando um site novo](#exemplo-criando-um-site-novo)
- [🔒 Segurança](#segurança)
- [🧪 Testes](#testes)
- [🐳 Docker](#docker)
- [🏗️ Estrutura interna](#estrutura-interna)

## 📁 Estrutura de pastas

| Pasta         | O que tem |
|---------------|-----------|
| `server/`     | `fabfile.py` que **provisiona** o servidor (`newserver`, `newaccount`, `nginx-restart`...) |
| `server/inc/` | templates (nginx, supervisor, proftpd/vsftpd) usados pelo fabfile acima |
| `client/`     | `fabfile.py` **"cliente"**: copie sozinho para dentro do SEU projeto Django/PHP para fazer deploy (`fab deploy`, `fab config`...) |
| `html/`       | documentação de uso ([NEWDEV.md](html/NEWDEV.md), [NEWSERVER.md](html/NEWSERVER.md)) |
| `tests/`      | testes automatizados (pytest) dos dois fabfiles |

> `server/` e `client/` são independentes — `client/fabfile.py` não importa
> nada de `server/`, porque ele é feito para ser copiado, sozinho, para
> dentro de outro repositório (o do seu projeto Django/PHP).

## ✅ Requisitos

- Servidor Ubuntu, Debian, Fedora, CentOS Stream/RHEL ou Arch Linux
- Python 3.10+
- pip
- `Fabric==3.2.3`
- `Jinja2==3.1.6`

## ⚙️ Instalação

```bash
# 1. clonar o projeto
git clone git@github.com:willemallan/django-fab-server.git
cd django-fab-server

# 2. (debian/ubuntu) garantir pip + venv
sudo apt install python3-pip python3-venv

# 3. criar e ativar um ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# 4. instalar as dependências
pip install -r requirements.txt
```

Os comandos de provisionamento ficam em `server/`. Aponte o fab para o
servidor do seu projeto copiando o template e editando `user`, `host` e
`chave` (esse arquivo é seu, local, e **nunca é commitado**):

```bash
cd server
cp local_settings-template.py local_settings.py
```

Como esse repositório pode ser reaproveitado para provisionar servidores de
vários projetos diferentes, basta manter um `server/local_settings.py`
próprio (não versionado) em cada cópia/clone, apontando para o servidor
daquele projeto. Os comandos `fab ...` abaixo devem ser rodados de dentro de
`server/`.

## 🐧 Distros suportadas

`local_settings.py` também define a distro do servidor em `os_family`, usada
para escolher o gerenciador de pacotes certo:

```python
os_family = "debian"  # "debian" (Ubuntu/Debian), "fedora",
                       # "rhel" (CentOS Stream/RHEL/Rocky/Alma) ou "arch"
```

| `os_family` | Distros              | Gerenciador | Banco de dados | FTP |
|-------------|----------------------|:-----------:|:---------------:|:---:|
| `debian`    | Ubuntu, Debian       | `apt`       | MySQL           | proftpd |
| `fedora`    | Fedora               | `dnf`       | MariaDB         | proftpd |
| `rhel`      | CentOS Stream, RHEL, Rocky, Alma | `dnf` (+ EPEL) | MariaDB | proftpd |
| `arch`      | Arch Linux, Manjaro  | `pacman`    | MariaDB         | **vsftpd** |

⚠️ **Diferenças que valem a pena conhecer** (ver tabelas `_..._BY_FAMILY` em
`server/fabfile.py`):

- **MariaDB fora do Debian/Ubuntu** — os repositórios oficiais de
  Fedora/RHEL/Arch não empacotam o MySQL da Oracle. No Arch o `fabfile`
  também inicializa o datadir (`mariadb-install-db`) automaticamente antes
  do primeiro start.
- **vsftpd no Arch** — `proftpd` não tem pacote oficial lá (só via AUR), então
  `fab newserver` instala e configura `vsftpd` em vez de proftpd nesse caso.
- **PHP no CentOS Stream/RHEL** — usa a versão padrão do `php-fpm` do
  AppStream (sem habilitar o repositório Remi), que pode ser mais antiga que
  o PHP 8.3 usado em Ubuntu/Debian/Fedora/Arch.

## 📜 Comandos disponíveis

```bash
cd server
fab --list
```

> O Fabric 3.x usa nomes com hífen no lugar de underscore (`newaccount` vira
> `newaccount`, mas `mysql_restart` vira `mysql-restart`, por exemplo).

| Categoria | Comandos |
|-----------|----------|
| 🖥️ **Servidor (setup completo)** | `newserver` · `newaccount` · `delaccount` · `listaccount` |
| 📦 **Pacotes** | `update-server` · `upgrade-server` · `build-server` · `python-server` · `mysql-server` · `git-server` · `others-server` · `aptget` |
| 🗄️ **MySQL/MariaDB** | `newbase` · `dropbase` · `mysql-start` · `mysql-stop` · `mysql-restart` |
| 🌐 **Nginx** | `nginx-start` · `nginx-stop` · `nginx-restart` · `nginx-reload` |
| 🧩 **Supervisor / app** | `supervisor-start` · `supervisor-stop` · `supervisor-restart` · `start-server` · `stop-server` · `restart-server` |
| 📁 **FTP** | `proftpd-restart` (vsftpd no Arch) |
| 👤 **Usuários / acesso** | `adduser` · `userdel` · `login` · `upload-public-key` |
| 💻 **Máquina local** | `newdev` · `newproject` · `update-local` · `upgrade-local` · `build-local` · `python-local` · `mysql-local` · `git-local` |
| 🔁 **Atalhos** | `restart` (reinicia nginx + supervisor) · `reboot` |

<details>
<summary>Ver descrição completa de cada comando</summary>

    adduser              Criar um usuário no servidor
    aptget               Instala um pacote no servidor (apt/dnf/pacman conforme os_family)
    build-local          Instalar build-essential
    build-server         Instalar build-essential e outros pacotes importantes no servidor
    delaccount           Deletar conta no servidor
    dropbase             Deletar banco de dados no servidor
    git-local            Instalando git
    git-server           Instalar git no servidor
    listaccount          Lista usuários do servidor
    login                Acessa o servidor
    mysql-local          Instalando MySQL
    mysql-restart        Restart mysql no servidor
    mysql-server         Instalar MySQL no servidor
    mysql-start          start mysql no servidor
    mysql-stop           stop mysql no servidor
    newaccount           Criar uma nova conta do usuário no servidor
    newbase              Criar banco de dados e usuário no servidor
    newdev               Configura uma maquina local (conforme os_family) para trabalhar python/django
    newproject           Criar novo projeto local
    newserver            Configurar e instalar todos pacotes necessários para servidor
    nginx-reload         Reload nginx no servidor
    nginx-restart        Restart nginx no servidor
    nginx-start          Start nginx no servidor
    nginx-stop           Stop nginx no servidor
    others-server        Instalar nginx, supervisor e php-fpm
    proftpd-restart      restart proftpd (ou vsftpd, no Arch)
    python-local         Instalando todos pacotes necessários
    python-server        Instalar todos pacotes necessários do python no servidor
    reboot               Reinicia o servidor
    restart              Reiniciar servicos no servidor
    restart-server       Restart aplicação no servidor
    start-server         Start aplicação no servidor
    stop-server          Stop aplicação no servidor
    supervisor-restart   Restart supervisor no servidor
    supervisor-start     Start supervisor no servidor
    supervisor-stop      Stop supervisor no servidor
    update-local         Atualizando pacotes
    update-server        Atualizando pacotes no servidor
    upgrade-local        Atualizando programas
    upgrade-server       Atualizar programas no servidor
    upload-public-key    Faz o upload da chave ssh para o servidor
    userdel              Deletar usuário no servidor

`create_password`, `log` e `write_file` eram listados como comandos no
Fabric 1.x só porque a CLI antiga listava qualquer função do módulo. No
Fabric 3.x eles continuam existindo como funções internas usadas pelos
comandos acima, mas não aparecem mais em `fab --list` por não serem
operações standalone.
</details>

## 🌐 Exemplo: criando um site novo

`fab newaccount` (rodado de dentro de `server/`) cria uma conta linux
isolada, o banco de dados e os arquivos de configuração (nginx + supervisor
ou nginx + php-fpm) para um site novo:

```bash
cd server
fab newaccount
```

### 🐍 Site em Django (python)

```
Digite o nome da conta: meusite
Digite o domínio do site (sem www): meusite.com.br
Escolha a linguagem: 1
Digite o número de uma porta que não está listada acima: 8060
Digite o nome da pasta onde está o settings/wsgi. ( Ex: app, config, [nome-do-projeto] ): meusite
Digite a senha do ROOT do MySQL: ********
Permitir acesso remoto a este banco (usuário 'meusite'@'%')? [y/N] n
```

O comando cria `/home/meusite` com um virtualenv em `env/`, grava
`nginx.conf` e `supervisor.ini` (aponta para `meusite.wsgi:application` via
gunicorn, na porta 8060) e um banco de dados `meusite` (por padrão só
acessível localmente — veja [Segurança](#segurança)). No final ele imprime
o usuário/senha ssh e do banco — **anote-os**.

Depois disso, envie o código do projeto Django para `/home/meusite/project`
(por exemplo com o `client/fabfile.py` — veja `fab config` e `fab deploy` em
[html/NEWSERVER.md](html/NEWSERVER.md)), garantindo que o pacote com o
`wsgi.py` tenha o mesmo nome informado acima (`meusite`), instale as
dependências no virtualenv e reinicie:

```bash
fab supervisor-restart
fab nginx-restart
```

### 🐘 Site em PHP

```
Digite o nome da conta: meusitephp
Digite o domínio do site (sem www): meusitephp.com.br
Escolha a linguagem: 2
Digite a senha do ROOT do MySQL: ********
Permitir acesso remoto a este banco (usuário 'meusitephp'@'%')? [y/N] n

IMPORTANTE!!! Para o funcionamento dos projetos em php com nginx é necessário que se
altere o arquivo php.ini
Alterar cgi.fix_pathinfo para 0 - Pressione ENTER para continuar..
```

O comando cria `/home/meusitephp/public_html/`, grava o `nginx.conf`
apontando para o socket certo do php-fpm da distro e o banco de dados
`meusitephp`. Basta enviar os arquivos PHP do site para
`/home/meusitephp/public_html/` (via `scp`/`rsync`/git) e reiniciar:

```bash
fab nginx-restart
```

## 🔒 Segurança

**MySQL/MariaDB**

- `fab newbase`/`fab newaccount` só criam o usuário `'conta'@'localhost'`
  por padrão. O usuário `'conta'@'%'` (acessível de qualquer host) só é
  criado se você responder "sim" ao prompt "Permitir acesso remoto a este
  banco?" — menos superfície de ataque por padrão.
- Nenhuma senha ou comando SQL (`CREATE USER`, `ALTER USER`...) é passado na
  linha de comando do `mysql`. Em um servidor com mais de um usuário,
  qualquer processo visível via `ps aux` conseguiria ler uma senha passada
  assim. Em vez disso, o fabfile envia o SQL (e, quando necessário, a senha
  de autenticação via um `--defaults-extra-file`) por SFTP para um arquivo
  temporário com permissão `600`, apagado logo depois de usado.
- Evite alterar o `bind-address` do MySQL para liberar acesso externo a
  menos que seja estritamente necessário — prefira manter o banco acessível
  só via `localhost`/socket e liberar acesso remoto caso a caso pelo
  firewall. (Debian/Ubuntu: `/etc/mysql/mysql.conf.d/mysqld.cnf`.)

**Nginx**

Os templates em `server/inc/` (`nginx.conf`, `nginx_php.conf`,
`nginx_server.conf`) já saem com:

- `server_tokens off;` — não expõe a versão do nginx nas respostas/erros.
- `location ~ /\. { deny all; }` — bloqueia acesso a arquivos ocultos
  (`.env`, `.git`, `.htaccess`...) na raiz do site.
- `autoindex off;` em `static`/`media` — não expõe a lista de arquivos do
  projeto (troque para `on` manualmente se precisar navegar).
- Headers básicos (`X-Content-Type-Options: nosniff`,
  `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy`).
- `fastcgi_param HTTP_PROXY "";` no site PHP — mitiga a vulnerabilidade
  "httpoxy" (CVE-2016-5385 e relacionadas).
- `proxy_set_header X-Forwarded-Proto $scheme;` no proxy para o Django —
  necessário para o app detectar requisições HTTPS atrás do nginx
  (`SECURE_PROXY_SSL_HEADER`).

## 🧪 Testes

O projeto tem testes automatizados (pytest) que validam a lógica local dos
fabfiles: geração de senha, confirmação, renderização dos templates Jinja2
de `server/inc/`, a lista de comandos exposta por `fab --list`, a cobertura
de pacotes/serviços por distro e um teste que simula a criação completa de
uma conta/site (`fab newaccount`) gravando os comandos que seriam enviados
ao servidor — inclusive checando que nenhuma senha/SQL vaza pela linha de
comando — sem precisar de um servidor de verdade (os métodos
`run`/`sudo`/`put` da conexão SSH são simulados).

```bash
pip install -r requirements.txt
pip install pytest
pytest
```

## 🐳 Docker

Também é possível rodar os dois fabfiles dentro de um container (Python
3.12), sem precisar instalar Python/Fabric na máquina local:

```bash
docker compose build
```

```bash
# fabfile.py de server/ (provisiona o servidor)
docker compose run --rm fab --list
docker compose run --rm fab newserver

# fabfile.py de client/ (deploy do seu projeto)
docker compose run --rm fab-client --list
docker compose run --rm fab-client deploy
```

Os dois serviços já têm `fab` como `entrypoint` (sem precisar repetir
`fab fab ...`) e montam o repositório (`.:/code`) e o seu `~/.ssh` (somente
leitura) como volumes — assim `local_settings.py`, chaves SSH e edições nos
fabfiles valem na hora, sem precisar rebuildar a imagem a cada mudança.

## 🏗️ Estrutura interna

Cada fabfile é um único arquivo (`server/fabfile.py` provisiona servidores;
`client/fabfile.py` é feito para ser copiado, sozinho, para dentro de outro
projeto — por isso os dois não compartilham código entre si). Dentro de cada
um, a lógica repetida foi extraída em helpers privados (prefixo `_`, não
aparecem em `fab --list`):

- `get_connection()` — cria a `Connection` SSH uma única vez por execução
  (memoizada com `functools.lru_cache`) e é reaproveitada por todos os
  comandos remotos daquele fabfile.
- `server/fabfile.py`: `_install(c, packages)`/`_install_local(c, packages)`
  centralizam a instalação de pacotes conforme `cfg.os_family`
  (apt/dnf/pacman); `_ensure_epel(c)` habilita o repositório EPEL quando
  necessário (RHEL/CentOS Stream); `_systemctl(service, action)` centraliza
  `systemctl start/stop/restart/reload`; `_mysql_exec(sql, password=...)`
  centraliza (e protege, veja [Segurança](#segurança)) os comandos
  MySQL/MariaDB; `write_file(...)` substitui o antigo `upload_template` do
  Fabric 1.x.
- `client/fabfile.py`: `remote_project()` é um context manager que devolve a
  conexão já posicionada dentro do diretório do projeto no servidor (`with
  remote_project() as conn:`), evitando repetir `get_connection()` +
  `conn.cd(project_path)` em cada tarefa remota.
