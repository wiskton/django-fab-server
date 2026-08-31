# -*- coding: utf-8 -*-
import functools
import os
from io import BytesIO

from fabric import Connection, task
from jinja2 import Environment, FileSystemLoader

CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------
# ALTERAR CONFIGURAÇÕES BASEADAS NO SEUS SERVIDOR E MAQUINA LOCAL
# Suporta servidores Ubuntu, Debian, Fedora, CentOS Stream/RHEL e Arch Linux
# -- veja a variável `os_family` abaixo
# ----------------------------------------------------------------

# SERVIDOR
user = "root"
host = "209.145.59.193"
chave = ""  # caminho da chave privada, ex: "~/.ssh/id_ed25519" (nome_arquivo.pem)
public_key = "~/.ssh/id_rsa.pub"  # chave publica usada por `fab upload-public-key`

# distro do servidor remoto: "debian" (Ubuntu/Debian), "fedora", "rhel"
# (CentOS Stream/RHEL/Rocky/Alma) ou "arch" (Arch Linux/Manjaro)
os_family = "debian"

# copiar as variaveis de cima e jogar no local_settings para substituir
try:
    from local_settings import *  # noqa: F401,F403
except ImportError:
    print("sem local_settings")

# LOCAL
bitbucket_user = "conta"
bitbucket_project_default = "projeto_padrao"
folder_project_local = "~/projetos/"

prod_server = "{0}@{1}".format(user, host)
project_path = "/home/"


class Config(dict):
    """Substitui o antigo `env` do Fabric 1.x (dict com acesso via atributo)."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


# configurações usadas nos templates de inc/ e nos comandos remotos
cfg = Config(
    supervisor_conf_d_path="/etc/supervisor/conf.d",
    conta="",
    dominio="",
    linguagem="",
    mysql_password="",
    porta="",
    nginx_sites_enable_path="/etc/nginx/sites-enabled",
    key_filename=chave,
    public_key=public_key,
    pasta_settings="",
    db_password="",
    os_family=os_family,
)


@functools.lru_cache(maxsize=1)
def get_connection():
    """Cria (uma única vez por execução) a conexão SSH com o servidor configurado."""
    connect_kwargs = {"key_filename": cfg.key_filename} if cfg.key_filename else {}
    return Connection(host=host, user=user, connect_kwargs=connect_kwargs)


# --------------------------------------------------------
# HELPERS DE TERMINAL
# substituem fabric.colors e fabric.contrib.console (removidos no Fabric 2+)
# --------------------------------------------------------


def _ansi(code):
    def _wrap(text):
        return "\033[{0}m{1}\033[0m".format(code, text)

    return _wrap


green = _ansi(32)
red = _ansi(31)
yellow = _ansi(33)
white = _ansi(37)


def confirm(question, default=True):
    suffix = "[Y/n]" if default else "[y/N]"
    resp = input("{0} {1} ".format(question, suffix)).strip().lower()
    if not resp:
        return default
    return resp in ("y", "yes")


def log(message, color=white):
    print(
        color(
            """
================================================================================
%s
================================================================================
    """
        )
        % message
    )


_jinja_env = Environment(loader=FileSystemLoader(os.path.join(CURRENT_PATH, "inc")))


def write_file(filename, destination):
    """Renderiza um template Jinja2 de inc/ e envia para o servidor.
    Substitui fabric.contrib.files.upload_template (removido no Fabric 2+)."""
    content = _jinja_env.get_template(filename).render(**cfg)

    conn = get_connection()
    remote_tmp = "/tmp/{0}".format(os.path.basename(destination))
    # BytesIO (não StringIO): o SFTP do paramiko calcula o tamanho do envio
    # com base em .tell() do arquivo em bytes -- com StringIO (texto) e
    # conteúdo com acentos (UTF-8 multi-byte, comum nos comentários em
    # português dos templates), a contagem de caracteres diverge da
    # contagem de bytes e o put falha com "size mismatch in put!".
    conn.put(BytesIO(content.encode("utf-8")), remote=remote_tmp)
    conn.sudo("test -f {0} && cp {0} {0}.bak || true".format(destination))
    conn.sudo("mv {0} {1}".format(remote_tmp, destination))


def _systemctl(service, action):
    """Executa uma ação do systemctl em um serviço no servidor."""
    get_connection().sudo("systemctl {0} {1}".format(action, service))


# --------------------------------------------------------
# MULTI-DISTRO: pacotes/serviços variam por `cfg.os_family`
# --------------------------------------------------------
#
# "debian" = Ubuntu/Debian (apt)
# "fedora" = Fedora (dnf, sem precisar de EPEL)
# "rhel"   = CentOS Stream/RHEL/Rocky/Alma (dnf, precisa de EPEL para
#            supervisor/mercurial/proftpd)
# "arch"   = Arch Linux/Manjaro (pacman)

_OS_FAMILIES = ("debian", "fedora", "rhel", "arch")

_BUILD_PACKAGES_BY_FAMILY = {
    "debian": "build-essential automake gettext libxml2-dev libxslt-dev "
    "libjpeg-dev zlib1g-dev libfreetype6-dev libwebp-dev",
    "fedora": "gcc gcc-c++ make automake gettext libxml2-devel libxslt-devel "
    "libjpeg-turbo-devel zlib-devel freetype-devel libwebp-devel",
    "rhel": "gcc gcc-c++ make automake gettext libxml2-devel libxslt-devel "
    "libjpeg-turbo-devel zlib-devel freetype-devel libwebp-devel",
    # base-devel é um grupo de pacotes; libs do Arch não separam runtime/dev
    "arch": "base-devel automake gettext libxml2 libxslt libjpeg-turbo zlib "
    "freetype2 libwebp",
}

_PYTHON_PACKAGES_BY_FAMILY = {
    "debian": "python3 python3-dev python3-venv python3-pip python3-pil python3-mysqldb",
    # venv já vem no python3 padrão do fedora/rhel, sem pacote separado
    "fedora": "python3 python3-devel python3-pip python3-pillow python3-mysqlclient",
    "rhel": "python3 python3-devel python3-pip python3-pillow python3-mysqlclient",
    "arch": "python python-pip python-pillow python-mysqlclient",
}

_DB_PACKAGES_BY_FAMILY = {
    "debian": "mysql-server libmysqlclient-dev",
    "fedora": "mariadb-server mariadb-devel",
    "rhel": "mariadb-server mariadb-devel",
    "arch": "mariadb mariadb-libs",
}

# fora do debian o servidor de banco é o MariaDB (não há MySQL da Oracle nos
# repositórios oficiais de fedora/rhel/arch)
_DB_SERVICE_BY_FAMILY = {
    "debian": "mysql",
    "fedora": "mariadb",
    "rhel": "mariadb",
    "arch": "mariadb",
}

_PHP_PACKAGES_BY_FAMILY = {
    "debian": "php8.3-fpm php8.3-mysql php8.3-gd php8.3-imagick php8.3-curl php8.3-cli",
    "fedora": "php-fpm php-mysqlnd php-gd php-pecl-imagick php-curl php-cli",
    # usa a versão padrão do dnf module (AppStream), sem habilitar Remi --
    # pode divergir da versão usada nas outras distros
    "rhel": "php-fpm php-mysqlnd php-gd php-pecl-imagick php-curl php-cli",
    # imagick não é empacotado oficialmente no Arch (só AUR)
    "arch": "php-fpm php-gd",
}

_PHP_FPM_SOCK_BY_FAMILY = {
    "debian": "/run/php/php8.3-fpm.sock",
    "fedora": "/run/php-fpm/www.sock",
    "rhel": "/run/php-fpm/www.sock",
    "arch": "/run/php-fpm/php-fpm.sock",
}

_PHP_INI_PATH_BY_FAMILY = {
    "debian": "/etc/php/8.3/fpm/php.ini",
    "fedora": "/etc/php.ini",
    "rhel": "/etc/php.ini",
    "arch": "/etc/php/php.ini",
}

# usuário que o worker do nginx usa (definido no pacote de cada distro)
_NGINX_USER_BY_FAMILY = {
    "debian": "www-data",
    "fedora": "nginx",
    "rhel": "nginx",
    "arch": "http",
}

# nome da unit do systemd -- o pacote empacotado fora do debian se chama
# "supervisord" (com "d" no final)
_SUPERVISOR_SERVICE_BY_FAMILY = {
    "debian": "supervisor",
    "fedora": "supervisord",
    "rhel": "supervisord",
    "arch": "supervisord",
}

_SUPERVISOR_CONF_PATH_BY_FAMILY = {
    "debian": "/etc/supervisor/supervisord.conf",
    "fedora": "/etc/supervisord.conf",
    "rhel": "/etc/supervisord.conf",
    "arch": "/etc/supervisord.conf",
}

# FTP: proftpd não tem pacote oficial no Arch (só AUR) -- usa vsftpd lá
_FTP_BY_FAMILY = {
    "debian": {
        "package": "proftpd",
        "template": "proftpd.conf",
        "destination": "/etc/proftpd/proftpd.conf",
        "service": "proftpd",
        "group": "nogroup",
    },
    "fedora": {
        "package": "proftpd",
        "template": "proftpd.conf",
        "destination": "/etc/proftpd/proftpd.conf",
        "service": "proftpd",
        "group": "nobody",
    },
    "rhel": {
        "package": "proftpd",
        "template": "proftpd.conf",
        "destination": "/etc/proftpd/proftpd.conf",
        "service": "proftpd",
        "group": "nobody",
    },
    "arch": {
        "package": "vsftpd",
        "template": "vsftpd.conf",
        "destination": "/etc/vsftpd.conf",
        "service": "vsftpd",
        "group": "nobody",
    },
}


def _install(c, packages):
    """Instala pacotes usando o gerenciador certo para `cfg.os_family`."""
    family = cfg.os_family
    conn = get_connection()
    if family == "debian":
        conn.sudo("apt -y install {0}".format(packages))
    elif family in ("fedora", "rhel"):
        conn.sudo("dnf -y install {0}".format(packages))
    elif family == "arch":
        conn.sudo("pacman -S --noconfirm --needed {0}".format(packages))
    else:
        raise ValueError(
            "os_family desconhecido: {0!r} (use um de {1})".format(family, _OS_FAMILIES)
        )


def _install_local(c, packages):
    """Instala pacotes na máquina local usando o gerenciador certo para
    `cfg.os_family` (equivalente a `_install`, mas via `c.run` local em vez
    de SSH)."""
    family = cfg.os_family
    if family == "debian":
        c.run("sudo apt -y install {0}".format(packages))
    elif family in ("fedora", "rhel"):
        c.run("sudo dnf -y install {0}".format(packages))
    elif family == "arch":
        c.run("sudo pacman -S --noconfirm --needed {0}".format(packages))
    else:
        raise ValueError(
            "os_family desconhecido: {0!r} (use um de {1})".format(family, _OS_FAMILIES)
        )


_PACKAGE_CHECK_BY_FAMILY = {
    "debian": "dpkg -s {0}",
    "fedora": "rpm -q {0}",
    "rhel": "rpm -q {0}",
    "arch": "pacman -Qi {0}",
}


def _package_installed(package):
    """Verifica se um pacote já está instalado no servidor."""
    check = _PACKAGE_CHECK_BY_FAMILY[cfg.os_family].format(package)
    result = get_connection().run(check, warn=True, hide=True)
    return result.ok


@functools.lru_cache(maxsize=1)
def _ensure_epel_once():
    if cfg.os_family == "rhel":
        get_connection().sudo("dnf -y install epel-release")


def _ensure_epel(c):
    """Habilita o repositório EPEL, necessário em RHEL/CentOS Stream/Rocky/
    Alma para instalar supervisor, mercurial e proftpd (fedora já traz esses
    pacotes nos repositórios padrão, sem precisar de EPEL).

    Memoizado sem depender de `c` -- o `Context` do Fabric/Invoke não é
    hashable, então não dá pra usar `functools.lru_cache` direto nele (ver
    TypeError: unhashable type: 'Context')."""
    _ensure_epel_once()


def _mysql_exec(sql, password=None):
    """Executa um SQL no servidor autenticando como root.

    O SQL (e a senha, quando informada) são enviados via SFTP para um
    arquivo temporário com permissão 600, em vez de irem na linha de
    comando: `mysql -u root -pSENHA --execute="..."` fica visível para
    qualquer usuário do servidor via `ps aux` (inclusive senhas de novos
    usuários/bancos, no CREATE USER/ALTER USER). Os arquivos são apagados
    logo em seguida.
    """
    conn = get_connection()
    token = create_password(8)
    sql_path = "/tmp/.fab_{0}.sql".format(token)
    conn.put(BytesIO(sql.encode("utf-8")), remote=sql_path)
    conn.sudo("chmod 600 {0}".format(sql_path))

    cnf_path = None
    defaults_flag = ""
    if password:
        cnf_path = "/tmp/.fab_{0}.cnf".format(token)
        conn.put(
            BytesIO("[client]\npassword={0}\n".format(password).encode("utf-8")),
            remote=cnf_path,
        )
        conn.sudo("chmod 600 {0}".format(cnf_path))
        defaults_flag = "--defaults-extra-file={0} ".format(cnf_path)

    try:
        conn.sudo("mysql {0}-u root < {1}".format(defaults_flag, sql_path))
    finally:
        conn.sudo("rm -f {0}".format(sql_path))
        if cnf_path:
            conn.sudo("rm -f {0}".format(cnf_path))


def create_password(tamanho=12):
    """Gera uma senha - parametro tamanho"""
    from random import choice

    caracters = "0123456789abcdefghijlmnopqrstuwvxzkABCDEFGHIJLMNOPQRSTUWVXZK_#"
    senha = ""
    for char in range(tamanho):
        senha += choice(caracters)
    return senha


# --------------------------------------------------------
# SERVIDOR
# --------------------------------------------------------


@task
def newserver(c):
    """Configurar e instalar todos pacotes necessários para servidor"""
    log("Configurar e instalar todos pacotes necessários para servidor", yellow)

    # gera uma chave no servidor para utilizar o comando upload_public_key
    # get_connection().run('ssh-keygen')

    update_server(c)
    upgrade_server(c)

    # pacotes
    build_server(c)
    python_server(c)
    mysql_server(c)
    git_server(c)
    others_server(c)

    # mysql
    mysql_restart(c)

    # nginx
    cfg.nginx_user = _NGINX_USER_BY_FAMILY[cfg.os_family]
    print(yellow("nginx - Alterando arquivo /etc/nginx/nginx.conf"))
    write_file("nginx_server.conf", "/etc/nginx/nginx.conf")
    nginx_restart(c)

    # ftp (proftpd, ou vsftpd no Arch)
    ftp = _FTP_BY_FAMILY[cfg.os_family]
    conn = get_connection()
    conn.sudo('grep -q $(hostname) /etc/hosts || echo "127.0.0.1 $(hostname)" >> /etc/hosts')
    conn.sudo("mkdir -p /var/log/proftpd /run/proftpd /etc/proftpd/conf.d")
    cfg.ftp_group = ftp.get("group", "nogroup")
    print(yellow("{0} - Alterando arquivo {1}".format(ftp["package"], ftp["destination"])))
    write_file(ftp["template"], ftp["destination"])
    proftpd_restart(c)

    # supervisor
    supervisor_conf_path = _SUPERVISOR_CONF_PATH_BY_FAMILY[cfg.os_family]
    print(yellow("supervisor - Alterando arquivo {0}".format(supervisor_conf_path)))
    write_file("supervisord_server.conf", supervisor_conf_path)
    supervisor_restart(c)

    if cfg.db_password:
        log("Anote a senha do banco de dados: {0}".format(cfg.db_password), green)

    log("Reiniciando a máquina", yellow)
    reboot(c)


@task
def newaccount(c):
    """Criar uma nova conta do usuário no servidor"""
    log("Criar uma nova conta do usuário no servidor", yellow)

    conn = get_connection()

    # criando usuario
    if not cfg.conta:
        cfg.conta = input("Digite o nome da conta: ")
    if not cfg.dominio:
        cfg.dominio = input("Digite o domínio do site (sem www): ")
    if not cfg.linguagem:
        cfg.linguagem = input(
            "Linguagens disponíveis\n\n1) PYTHON\n2) PHP\n\nEscolha a linguagem: "
        )
    if int(cfg.linguagem) == 1:
        if not cfg.porta:
            log(
                "ATENCAO!! VERIFIQUE AS PORTAS JÁ UTILIZADAS\nOBS: abaixo estão apenas as portas utilizadas pelas conexões tcp e sites, porém\noutro programa no servidor pode estar utilizando uma porta não listada abaixo.",
                yellow,
            )
            # `ss` (iproute2) no lugar do `netstat` (net-tools) -- vem
            # instalado por padrão em todas as distros suportadas, enquanto
            # o pacote net-tools foi descontinuado e não vem mais instalado
            # por padrão no Debian/Ubuntu/RHEL/Fedora recentes
            conn.sudo("ss -tulpn")
            cfg.porta = input(
                "Digite o número de uma porta que não está listada acima: "
            )
        if not cfg.pasta_settings:
            cfg.pasta_settings = input(
                "Digite o nome da pasta onde está o settings/wsgi. ( Ex: app, config, [nome-do-projeto] ):"
            )
    if not cfg.mysql_password:
        cfg.mysql_password = input("Digite a senha do ROOT do MySQL: ")

    # cria usuario no linux
    user_senha = create_password(12)
    adduser(c, cfg.conta, user_senha)

    conn.sudo("mkdir /home/{0}/logs".format(cfg.conta))
    conn.sudo("touch /home/{0}/logs/access.log".format(cfg.conta))
    conn.sudo("touch /home/{0}/logs/error.log".format(cfg.conta))

    if int(cfg.linguagem) == 1:
        conn.sudo("python3 -m venv /home/{0}/env".format(cfg.conta))
        write_file("nginx.conf", "/home/{0}/nginx.conf".format(cfg.conta))
        write_file("supervisor.ini", "/home/{0}/supervisor.ini".format(cfg.conta))
        write_file("bash_login", "/home/{0}/.bash_login".format(cfg.conta))
    else:
        php_ini = _PHP_INI_PATH_BY_FAMILY[cfg.os_family]
        log(
            """IMPORTANTE!!! Para o funcionamento dos projetos em php com nginx é necessário que se
                altere o arquivo {0}\n
                Execute o comando: sudo nano {0}\n
                Descomente e altere para 0 a var abaixo\n
                cgi.fix_pathinfo=0\n""".format(
                php_ini
            ),
            yellow,
        )

        input(
            "Alterar cgi.fix_pathinfo para 0 - Pressione ENTER para continuar.."
        )

        cfg.php_fpm_sock = _PHP_FPM_SOCK_BY_FAMILY[cfg.os_family]
        write_file("nginx_php.conf", "/home/{0}/nginx.conf".format(cfg.conta))
        conn.sudo("mkdir /home/{0}/public_html/".format(cfg.conta))

    # cria banco e usuario no banco
    banco_senha = create_password(12)
    newbase(c, cfg.conta, banco_senha)

    # da permissao para o usuario no diretorio
    conn.sudo("chown -R {0}:{0} /home/{0}".format(cfg.conta))

    nginx_restart(c)
    supervisor_restart(c)

    # log para salvar no docs
    log("Anotar dados da conta", green)
    print(
        green(
            "conta: {0} \n\n-- ssh\nuser: {0}\npw sugerido: {1} \n\n-- banco\nuser: {0}\npw: {2}".format(
                cfg.conta, user_senha, banco_senha
            )
        )
    )


@task
def listaccount(c):
    """Lista usuários do servidor"""
    log("Lista usuários do servidor", yellow)
    conn = get_connection()
    with conn.cd("/home/"):
        conn.run("ls")


@task
def aptget(c, lib=None):
    """Instala um pacote no servidor (apt/dnf/pacman conforme os_family) ex: fab aptget --lib=python3-pip"""
    log("Instalando pacote no servidor", yellow)
    if not lib:
        lib = input("Digite o pacote para instalar: ")

    if lib:
        _install(c, lib)


@task
def delaccount(c):
    """Deletar conta no servidor"""
    conta = input("Digite o nome da conta: ")
    cfg.mysql_password = input("Digite a senha do ROOT do MySQL: ")
    log("Deletando conta {0}".format(conta), red)
    userdel(c, conta)
    dropbase(c, conta)


@task
def adduser(c, conta=None, user_senha=None):
    """Criar um usuário no servidor"""

    if not user_senha:
        user_senha = create_password(12)
    print("sugestao de Unix password: {0}".format(user_senha))

    if not conta:
        conta = input("Digite o nome do usuário: ")

    log("Criando usuário {0}".format(conta), green)
    get_connection().sudo("adduser {0}".format(conta))
    print(
        "\n================================================================================"
    )


# MYSQL - cria usuario e banco de dados
@task
def newbase(c, conta=None, banco_senha=None):
    """Criar banco de dados e usuário no servidor"""

    if not banco_senha:
        banco_senha = create_password(12)
    print("Senha gerada para o banco: {0}".format(banco_senha))

    if not conta:
        conta = input("Digite o nome do banco: ")
    log("NEW DATABASE {0}".format(conta), green)

    _mysql_exec("CREATE DATABASE {0}".format(conta), password=cfg.mysql_password)

    # acesso local (usado pela aplicação rodando no próprio servidor)
    _mysql_exec(
        "CREATE USER '{0}'@'localhost' IDENTIFIED BY '{1}'".format(conta, banco_senha),
        password=cfg.mysql_password,
    )
    _mysql_exec(
        "GRANT ALL PRIVILEGES ON {0} . * TO '{0}'@'localhost'".format(conta),
        password=cfg.mysql_password,
    )

    # acesso remoto ('%') é uma superfície de ataque extra e só é criado se
    # pedido explicitamente -- por padrão o banco só é acessível localmente
    if confirm(
        "Permitir acesso remoto a este banco (usuário '{0}'@'%')? Não recomendado, "
        "só é necessário se algo fora deste servidor for conectar direto no MySQL.".format(
            conta
        ),
        default=False,
    ):
        _mysql_exec(
            "CREATE USER '{0}'@'%' IDENTIFIED BY '{1}'".format(conta, banco_senha),
            password=cfg.mysql_password,
        )
        _mysql_exec(
            "GRANT ALL PRIVILEGES ON {0} . * TO '{0}'@'%'".format(conta),
            password=cfg.mysql_password,
        )


# MYSQL - deleta o usuario e o banco de dados
@task
def dropbase(c, conta=None):
    """Deletar banco de dados no servidor"""
    if not conta:
        conta = input("Digite o nome do banco: ")
    if not cfg.mysql_password:
        cfg.mysql_password = input("Digite a senha do ROOT do MySQL: ")

    _mysql_exec("DROP DATABASE IF EXISTS {0}".format(conta), password=cfg.mysql_password)
    _mysql_exec(
        "DROP USER IF EXISTS '{0}'@'localhost'".format(conta), password=cfg.mysql_password
    )
    # o usuário '@'%'' só existe se o acesso remoto tiver sido habilitado na
    # criação (ver newbase); IF EXISTS evita erro caso ele nunca tenha existido
    _mysql_exec(
        "DROP USER IF EXISTS '{0}'@'%'".format(conta), password=cfg.mysql_password
    )


# LINUX - deleta o usuario
@task
def userdel(c, conta=None):
    """Deletar usuário no servidor"""
    if not conta:
        conta = input("Digite o nome do usuario: ")
    log("Deletando usuário {0}".format(conta), red)
    get_connection().sudo("userdel -r {0}".format(conta))


@task
def update_server(c):
    """Atualizando pacotes no servidor"""
    log("Atualizando pacotes", yellow)
    conn = get_connection()
    family = cfg.os_family
    if family == "debian":
        conn.sudo("apt -y update")
    elif family in ("fedora", "rhel"):
        conn.sudo("dnf makecache")
    elif family == "arch":
        # seguro aqui porque `newserver` sempre chama upgrade_server (pacman
        # -Su) logo em seguida -- rodar só "-Sy" isolado (sem upgrade) não é
        # recomendado no Arch (partial upgrade)
        conn.sudo("pacman -Sy --noconfirm")


@task
def upgrade_server(c):
    """Atualizar programas no servidor"""
    log("Atualizando programas", yellow)
    conn = get_connection()
    family = cfg.os_family
    if family == "debian":
        conn.sudo("apt -y upgrade")
    elif family in ("fedora", "rhel"):
        conn.sudo("dnf -y upgrade")
    elif family == "arch":
        conn.sudo("pacman -Su --noconfirm")


@task
def build_server(c):
    """Instalar build-essential e outros pacotes importantes no servidor"""
    log("Instalando build-essential e outros pacotes", yellow)
    _install(c, _BUILD_PACKAGES_BY_FAMILY[cfg.os_family])


@task
def python_server(c):
    """Instalar todos pacotes necessários do python no servidor"""
    log("Instalando todos pacotes necessários", yellow)
    _ensure_epel(c)
    _install(c, _PYTHON_PACKAGES_BY_FAMILY[cfg.os_family])


@task
def mysql_server(c):
    """Instalar MySQL no servidor"""
    family = cfg.os_family
    main_package = _DB_PACKAGES_BY_FAMILY[family].split()[0]

    if _package_installed(main_package):
        # já rodou antes nesse servidor -- não reinstala nem troca a senha
        # do root (senão a senha anotada da vez anterior para de funcionar)
        log(
            "MySQL/MariaDB já está instalado -- pulando instalação e "
            "senha do root (rode `fab mysql-restart` se só precisa "
            "reiniciar o serviço)",
            yellow,
        )
        return

    log("Instalando MySQL", yellow)

    if confirm("Deseja que o script gere senha automatica para o mysql?"):
        db_password = create_password(12)
    else:
        db_password = input("Digite a senha root do mysql: ")

    cfg.db_password = db_password

    conn = get_connection()
    _install(c, _DB_PACKAGES_BY_FAMILY[family])

    service = _DB_SERVICE_BY_FAMILY[family]
    if family == "arch":
        # o pacote do Arch não inicializa o datadir sozinho (ao contrário do
        # apt/dnf, que já deixam o mysql/mariadb rodando após a instalação)
        conn.sudo("mariadb-install-db --datadir=/var/lib/mysql --basedir=/usr")
    if family != "debian":
        # dnf/pacman não iniciam nem habilitam o serviço sozinhos
        _systemctl(service, "enable --now")

    # nas versões atuais do mysql-server/mariadb-server o usuário root usa
    # auth_socket (ou unix_socket) por padrão, sem senha via debconf;
    # definimos a senha explicitamente aqui. `sudo mysql` já autentica via
    # socket (usuário do SO = root), sem precisar de senha nesta primeira
    # chamada. Sintaxe portável entre MySQL e MariaDB (sem "WITH
    # caching_sha2_password", que não existe no MariaDB).
    _mysql_exec(
        "ALTER USER 'root'@'localhost' IDENTIFIED BY '{0}'; FLUSH PRIVILEGES;".format(
            db_password
        )
    )

    log("BANCO DE DADOS - PASSWORD", green)
    print("senha root mysql: {0}".format(db_password))
    input("Após copiar a senha, clique ENTER para continuar!!!")


@task
def git_server(c):
    """Instalar git no servidor"""
    log("Instalando git", yellow)
    _install(c, "git")


@task
def others_server(c):
    """Instalar nginx, supervisor e php-fpm"""
    log("Instalando nginx e supervisor", yellow)
    family = cfg.os_family
    conn = get_connection()
    _ensure_epel(c)

    _install(c, "nginx supervisor")
    _install(c, "mercurial")

    if family == "debian":
        conn.sudo("add-apt-repository -y universe")

    _install(c, _PHP_PACKAGES_BY_FAMILY[family])

    ftp = _FTP_BY_FAMILY[family]
    _install(c, ftp["package"])


@task
def login(c):
    """Acessa o servidor"""
    if chave:
        c.run("ssh %s -i %s" % (prod_server, cfg.key_filename))
    else:
        c.run("ssh %s" % prod_server)


@task
def upload_public_key(c):
    """Faz o upload da chave ssh para o servidor (precisa de uma conexão que
    já autentique -- veja o aviso em `fab --help upload-public-key`)"""
    log("Adicionando chave publica no servidor", green)
    conn = get_connection()
    target_path = "~/.ssh/uploaded_key.pub"
    conn.put(cfg.public_key, target_path)
    conn.run(
        "echo `cat ~/.ssh/uploaded_key.pub` >> ~/.ssh/authorized_keys && rm -f ~/.ssh/uploaded_key.pub"
    )


# RESTART
@task
def restart(c):
    """Reiniciar servicos no servidor"""
    log("reiniciando servicos", yellow)
    nginx_stop(c)
    nginx_start(c)
    nginx_restart(c)
    nginx_reload(c)
    supervisor_stop(c)
    supervisor_start(c)


@task
def reboot(c):
    """Reinicia o servidor"""
    log("reiniciando servidor", yellow)
    get_connection().sudo("reboot")


@task
def proftpd_restart(c):
    """restart proftpd (ou vsftpd, no Arch)"""
    service = _FTP_BY_FAMILY[cfg.os_family]["service"]
    log("restart {0}".format(service), yellow)
    _systemctl(service, "restart")


# SUPERVISOR APP
@task
def start_server(c):
    """Start aplicação no servidor"""
    conta = input("Digite o nome da app: ")
    log("inicia aplicação", green)
    get_connection().sudo("supervisorctl start %s" % conta)


@task
def stop_server(c):
    """Stop aplicação no servidor"""
    conta = input("Digite o nome da app: ")
    log("para aplicação", red)
    get_connection().sudo("supervisorctl stop %s" % conta)


@task
def restart_server(c):
    """Restart aplicação no servidor"""
    conta = input("Digite o nome da app: ")
    log("reinicia aplicação", yellow)
    get_connection().sudo("supervisorctl restart %s" % conta)


# SUPERVISOR
@task
def supervisor_start(c):
    """Start supervisor no servidor"""
    log("start supervisor", green)
    _systemctl(_SUPERVISOR_SERVICE_BY_FAMILY[cfg.os_family], "start")


@task
def supervisor_stop(c):
    """Stop supervisor no servidor"""
    log("stop supervisor", red)
    _systemctl(_SUPERVISOR_SERVICE_BY_FAMILY[cfg.os_family], "stop")


@task
def supervisor_restart(c):
    """Restart supervisor no servidor"""
    log("restart supervisor", yellow)
    _systemctl(_SUPERVISOR_SERVICE_BY_FAMILY[cfg.os_family], "restart")


# NGINX
@task
def nginx_start(c):
    """Start nginx no servidor"""
    log("start nginx", green)
    _systemctl("nginx", "start")


@task
def nginx_stop(c):
    """Stop nginx no servidor"""
    log("stop nginx", red)
    _systemctl("nginx", "stop")


@task
def nginx_restart(c):
    """Restart nginx no servidor"""
    log("restart nginx", yellow)
    _systemctl("nginx", "restart")


@task
def nginx_reload(c):
    """Reload nginx no servidor"""
    log("reload nginx", yellow)
    _systemctl("nginx", "reload")


@task
def mysql_restart(c):
    """Restart mysql no servidor"""
    log("restart mysql", yellow)
    _systemctl(_DB_SERVICE_BY_FAMILY[cfg.os_family], "restart")


@task
def mysql_start(c):
    """start mysql no servidor"""
    log("start mysql", green)
    _systemctl(_DB_SERVICE_BY_FAMILY[cfg.os_family], "start")


@task
def mysql_stop(c):
    """stop mysql no servidor"""
    log("stop mysql", red)
    _systemctl(_DB_SERVICE_BY_FAMILY[cfg.os_family], "stop")


# --------------------------------------------------------
# LOCAL
# --------------------------------------------------------


@task
def newproject(c):
    """Criar novo projeto local"""
    log("Criando novo projeto", yellow)
    log(
        "Cria a conta no bitbucket com o nome do projeto vázio que o script se encarregará do resto",
        red,
    )

    conta = input("Digite o nome do projeto: ")

    c.run('echo "clonando projeto %s"' % conta)
    c.run(
        "git clone {0} {1}{2}".format(
            bitbucket_project_default, folder_project_local, conta
        )
    )
    with c.cd("{0}{1}".format(folder_project_local, conta)):
        c.run("python3 -m venv env")
        c.run("pip install -r requirements.txt")
    c.run("rm -rf {0}{1}/.git".format(folder_project_local, conta))
    c.run("rm -rf README.md")
    c.run("git init")
    c.run(
        "git remote add origin git@bitbucket.org:{0}/{1}.git".format(
            bitbucket_user, conta
        )
    )


@task
def newdev(c):
    """Configura uma maquina local (conforme os_family) para trabalhar python/django"""
    log("Configura um computador para trabalhar python/django", yellow)
    update_local(c)
    upgrade_local(c)

    # pacotes
    build_local(c)
    python_local(c)
    mysql_local(c)
    git_local(c)

    # atualizando
    update_local(c)
    upgrade_local(c)


@task
def update_local(c):
    """Atualizando pacotes"""
    log("Atualizando pacotes", yellow)
    family = cfg.os_family
    if family == "debian":
        c.run("sudo apt -y update")
    elif family in ("fedora", "rhel"):
        c.run("sudo dnf makecache")
    elif family == "arch":
        # ver comentário em update_server sobre rodar -Sy antes do -Su
        c.run("sudo pacman -Sy --noconfirm")


@task
def upgrade_local(c):
    """Atualizando programas"""
    log("Atualizando programas", yellow)
    family = cfg.os_family
    if family == "debian":
        c.run("sudo apt -y upgrade")
    elif family in ("fedora", "rhel"):
        c.run("sudo dnf -y upgrade")
    elif family == "arch":
        c.run("sudo pacman -Su --noconfirm")


@task
def build_local(c):
    """Instalar build-essential"""
    log("instalando build-essential gcc++", yellow)
    _install_local(c, _BUILD_PACKAGES_BY_FAMILY[cfg.os_family])
    # terminator só é garantidamente empacotado no debian/fedora/arch
    if cfg.os_family != "rhel":
        _install_local(c, "terminator")


@task
def python_local(c):
    """Instalando todos pacotes necessários"""
    log("Instalando todos pacotes necessários", yellow)
    packages = {
        "debian": "python3 python3-dev python3-venv python3-pip python3-pil",
        "fedora": "python3 python3-devel python3-pip python3-pillow",
        "rhel": "python3 python3-devel python3-pip python3-pillow",
        "arch": "python python-pip python-pillow",
    }[cfg.os_family]
    _install_local(c, packages)


@task
def mysql_local(c):
    """Instalando MySQL"""
    log("Instalando MySQL", yellow)
    _install_local(c, _DB_PACKAGES_BY_FAMILY[cfg.os_family])


@task
def git_local(c):
    """Instalando git"""
    log("Instalando git", yellow)
    _install_local(c, "git")
