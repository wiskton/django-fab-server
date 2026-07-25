django-fab-server
=================

**Suporta Ubuntu, Debian, Fedora, CentOS Stream/RHEL e Arch Linux -- Python 3 e Fabric 3.x**

Como funciona?

<p>É um fabric que acessa o servidor e instala todas dependencias.</p>

Estrutura de pastas
====================

    server/     fabfile.py que PROVISIONA o servidor (newserver, newaccount, nginx-restart...)
    server/inc  templates (nginx, supervisor, proftpd) usados pelo fabfile acima
    client/     fabfile.py "cliente": copie sozinho para dentro do SEU projeto Django/PHP
                para fazer deploy (fab deploy, fab config...) nesse servidor
    html/       documentação de uso (NEWDEV.md, NEWSERVER.md)
    tests/      testes automatizados (pytest) dos dois fabfiles

`server/` e `client/` são independentes -- o `client/fabfile.py` não importa
nada de `server/`, porque ele é feito para ser copiado, sozinho, para dentro
de outro repositório (o do seu projeto Django/PHP).

requirements:

    servidor Ubuntu, Debian, Fedora, CentOS Stream/RHEL ou Arch Linux
    Python 3.10+
    pip
    Fabric==3.2.3
    Jinja2==3.1.6


Clone o projeto na máquina na sua pasta de projetos:

    git clone git@github.com:willemallan/django-fab-server.git


Instalando na máquina o pip em distribuições linux baseadas no debian:

    sudo apt install python3-pip python3-venv


Crie um ambiente virtual para isolar as dependências:

    python3 -m venv .venv
    source .venv/bin/activate

Entrar no diretório do django fab server e instalar as dependências:

    cd django-fab-server
    pip install -r requirements.txt


Os comandos de provisionamento de servidor ficam em `server/`. Entre lá e
aponte o fab para o servidor do seu projeto copiando o template e editando
`user`, `host` e `chave` (esse arquivo é seu, local, e nunca é commitado):

    cd server
    cp local_settings-template.py local_settings.py

Como esse repositório pode ser reaproveitado para provisionar servidores de
vários projetos diferentes, basta manter um `server/local_settings.py`
próprio (não versionado) em cada cópia/clone, apontando para o servidor
daquele projeto. Os comandos `fab ...` abaixo devem ser rodados de dentro de
`server/`.

Além de `user`/`host`/`chave`, o `local_settings.py` também define a distro
do servidor em `os_family`, usada para escolher o gerenciador de pacotes
(`apt`/`dnf`/`pacman`) e os nomes de pacotes/serviços certos:

    os_family = "debian"  # "debian" (Ubuntu/Debian), "fedora", "rhel"
                           # (CentOS Stream/RHEL/Rocky/Alma) ou "arch"

Diferenças conhecidas entre distros (ver `server/fabfile.py`, tabelas
`_..._BY_FAMILY`):

* **Banco de dados**: fora do Debian/Ubuntu o servidor instalado é o
  **MariaDB** (`mariadb-server`, serviço `mariadb`), não o MySQL da Oracle --
  os repositórios oficiais de Fedora/RHEL/Arch não empacotam o MySQL. No Arch
  também é necessário inicializar o datadir (`mariadb-install-db`) antes do
  primeiro start, o que o fabfile já faz automaticamente.
* **FTP**: o Arch não tem pacote oficial de `proftpd` (só via AUR), então lá
  o `fab newserver` instala e configura **vsftpd** em vez de proftpd. Nas
  demais distros continua sendo proftpd.
* **PHP**: no CentOS Stream/RHEL é instalada a versão padrão do `php-fpm` do
  AppStream (sem habilitar o repositório Remi), que pode ser mais antiga que
  o PHP 8.3 usado em Ubuntu/Debian/Fedora/Arch.
* **CentOS** aqui significa CentOS Stream (usa `dnf`, assim como
  RHEL/Rocky/AlmaLinux).


Configurando uma máquina para rodar python/django e mysql:

<ul>
    <li>
        <a href="html/NEWDEV.md"><b>Local</b></a> é para configurar uma maquina linux para trabalhar com python/django.
    </li>
    <li>
        <a href="html/NEWSERVER.md"><b>Servidor</b></a> é para configurar um servidor linux para rodar sites em python/django.
    </li>
</ul>


IMPORTANTE
==========

## Para dar permissão de acesso externo ao mysql altere o arquivo /etc/mysql/mysql.conf.d/mysqld.cnf ajustando a diretiva `bind-address = 127.0.0.1`. Evite fazer isso a menos que seja realmente necessário -- veja a seção Segurança abaixo.

## Para o funcionamento de projetos em PHP altere com sudo o arquivo /etc/php/8.3/fpm/php.ini - mude a diretiva `cgi.fix_pathinfo` para `0`

Listando os comandos (a partir de `server/`; o Fabric 3.x usa nomes com hífen no lugar de underscore):

    cd server
    fab --list

Comandos disponíveis:

    adduser              Criar um usuário no servidor
    aptget               Executa apt install no servidor ex: fab aptget --lib=...
    build-local          Instalar build-essential
    build-server         Instalar build-essential e outros pacotes importantes ...
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
    newdev               Configura uma maquina local Ubuntu para trabalhar pyth...
    newproject           Criar novo projeto local
    newserver            Configurar e instalar todos pacotes necessários para ...
    nginx-reload         Reload nginx no servidor
    nginx-restart        Restart nginx no servidor
    nginx-start          Start nginx no servidor
    nginx-stop           Stop nginx no servidor
    others-server        Instalar nginx, supervisor e php-fpm
    proftpd-restart      restart proftpd
    python-local         Instalando todos pacotes necessários
    python-server        Instalar todos pacotes necessários do python no servi...
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

`create_password`, `log` e `write_file` eram listados como comandos no Fabric
1.x só porque a CLI antiga listava qualquer função do módulo. No Fabric 3.x
eles continuam existindo como funções internas usadas pelos comandos acima,
mas não aparecem mais em `fab --list` por não serem operações standalone.


Exemplo: criando um site novo
==============================

`fab newaccount` (rodado de dentro de `server/`) cria uma conta linux
isolada, o banco de dados e os arquivos de configuração (nginx + supervisor
ou nginx + php-fpm) para um site novo:

    cd server
    fab newaccount

## Site em Django (python)

    Digite o nome da conta: meusite
    Digite o domínio do site (sem www): meusite.com.br
    Escolha a linguagem: 1
    Digite o número de uma porta que não está listada acima: 8060
    Digite o nome da pasta onde está o settings/wsgi. ( Ex: app, config, [nome-do-projeto] ): meusite
    Digite a senha do ROOT do MySQL: ********
    Permitir acesso remoto a este banco (usuário 'meusite'@'%')? [y/N] n

O comando cria `/home/meusite` com um virtualenv em `env/`, grava
`nginx.conf` e `supervisor.ini` (aponta para `meusite.wsgi:application` via
gunicorn, na porta 8060) e um banco de dados `meusite` no MySQL (por padrão
só acessível localmente -- veja Segurança). No final ele imprime o
usuário/senha ssh e do banco -- anote-os.

Depois disso, envie o código do projeto Django para `/home/meusite/project`
(por exemplo com o `client/fabfile.py` -- veja `fab config` e `fab deploy`
em [html/NEWSERVER.md](html/NEWSERVER.md)), garantindo que o pacote com o
`wsgi.py` tenha o mesmo nome informado acima (`meusite`), instale as
dependências no virtualenv e reinicie:

    fab supervisor-restart
    fab nginx-restart

## Site em PHP

    Digite o nome da conta: meusitephp
    Digite o domínio do site (sem www): meusitephp.com.br
    Escolha a linguagem: 2
    Digite a senha do ROOT do MySQL: ********
    Permitir acesso remoto a este banco (usuário 'meusitephp'@'%')? [y/N] n

    IMPORTANTE!!! Para o funcionamento dos projetos em php com nginx é necessário que se
    altere o arquivo /etc/php/8.3/fpm/php.ini
    Alterar cgi.fix_pathinfo para 0 - Pressione ENTER para continuar..

O comando cria `/home/meusitephp/public_html/`, grava o `nginx.conf` (com
`fastcgi_pass unix:/run/php/php8.3-fpm.sock`) e o banco de dados
`meusitephp` no MySQL. Basta enviar os arquivos PHP do site para
`/home/meusitephp/public_html/` (via `scp`/`rsync`/git) e reiniciar:

    fab nginx-restart


Segurança
=========

MySQL
-----

* `fab newbase`/`fab newaccount` só criam o usuário `'conta'@'localhost'`
  por padrão. O usuário `'conta'@'%'` (acessível de qualquer host) só é
  criado se você responder "sim" ao prompt "Permitir acesso remoto a este
  banco?" -- menos superfície de ataque por padrão.
* Nenhuma senha ou comando SQL (`CREATE USER`, `ALTER USER`...) é passado na
  linha de comando do `mysql`. Em um servidor com mais de um usuário,
  qualquer processo visível via `ps aux` conseguiria ler uma senha passada
  assim. Em vez disso, o fabfile envia o SQL (e, quando necessário, a senha
  de autenticação via um `--defaults-extra-file`) por SFTP para um arquivo
  temporário com permissão `600`, que é apagado logo depois de usado.
* Evite comentar o `bind-address` do MySQL para liberar acesso externo (veja
  a seção IMPORTANTE) a menos que seja estritamente necessário -- prefira
  manter o banco acessível só via `localhost`/socket e liberar acesso remoto
  caso a caso pelo firewall.

Nginx
-----

Os templates em `server/inc/` (`nginx.conf`, `nginx_php.conf`,
`nginx_server.conf`) já saem com:

* `server_tokens off;` -- não expõe a versão do nginx nas respostas/erros.
* `location ~ /\. { deny all; }` -- bloqueia acesso a arquivos ocultos
  (`.env`, `.git`, `.htaccess`...) que porventura estejam na raiz do site.
* `autoindex off;` nos diretórios de `static`/`media` -- não expõe a lista
  de arquivos do projeto (troque para `on` manualmente se precisar navegar).
* Headers básicos (`X-Content-Type-Options: nosniff`,
  `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy`).
* `fastcgi_param HTTP_PROXY "";` no site PHP -- mitiga a vulnerabilidade
  "httpoxy" (CVE-2016-5385 e relacionadas).
* `proxy_set_header X-Forwarded-Proto $scheme;` no proxy para o Django --
  necessário para o app detectar corretamente requisições HTTPS atrás do
  nginx (`SECURE_PROXY_SSL_HEADER`).


Testes
======

O projeto tem testes automatizados (pytest) que validam a lógica local dos
fabfiles (geração de senha, confirmação, renderização dos templates Jinja2
de `server/inc/` e a lista de comandos exposta por `fab --list`), além de um
teste que simula a criação completa de uma conta/site (`fab newaccount`)
gravando os comandos que seriam enviados ao servidor -- inclusive checando
que nenhuma senha/SQL vaza pela linha de comando -- sem precisar de um
servidor de verdade: os métodos `run`/`sudo`/`put` da conexão SSH são
simulados.

Instale as dependências de desenvolvimento e rode (a partir da raiz do
repositório):

    pip install -r requirements.txt
    pip install pytest
    pytest


Docker
======

Também é possível rodar o `fab` (de `server/`) dentro de um container
(Python 3.12):

    docker compose build
    docker compose run --rm fab fab --list


Estrutura interna
==================

Cada fabfile é um único arquivo (`server/fabfile.py` provisiona servidores;
`client/fabfile.py` é feito para ser copiado, sozinho, para dentro de outro
projeto -- por isso os dois não compartilham código entre si). Dentro de
cada um, a lógica repetida foi extraída em helpers privados (prefixo `_`,
não aparecem em `fab --list`) para evitar duplicar a mesma lógica em vários
comandos:

* `get_connection()` -- cria a `Connection` SSH uma única vez por execução
  (memoizada com `functools.lru_cache`) e é reaproveitada por todos os
  comandos remotos daquele fabfile.
* `server/fabfile.py`: `_systemctl(service, action)` centraliza os comandos
  `systemctl start/stop/restart/reload`; `_mysql_exec(sql, password=...)`
  centraliza (e protege, veja Segurança) os comandos MySQL; `write_file(...)`
  substitui o antigo `upload_template` do Fabric 1.x.
* `client/fabfile.py`: `remote_project()` é um context manager que devolve
  a conexão já posicionada dentro do diretório do projeto no servidor
  (`with remote_project() as conn:`), evitando repetir
  `get_connection()` + `conn.cd(project_path)` em cada tarefa remota.
