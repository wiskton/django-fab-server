# -*- coding: utf-8 -*-
import functools
import os
import re
import uuid
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
    npm_type="",
    npm_start_cmd="",
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

RESERVED_SYSTEM_USERS = {
    "root", "bin", "daemon", "sys", "adm", "sync", "games", "man", "lp", "mail",
    "news", "uucp", "proxy", "www-data", "backup", "list", "irc", "gnats", "nobody",
    "systemd", "nginx", "http", "mysql", "mariadb", "supervisor", "supervisord",
    "redis", "ftp", "sshd",
}


def _validate_account_name(conta):
    """Valida o nome da conta para garantir segurança e isolamento."""
    if not conta or not isinstance(conta, str):
        raise ValueError("Nome da conta não pode ser vazio.")
    conta = conta.strip()
    if not re.match(r"^[a-z0-9_-]{2,32}$", conta):
        raise ValueError(
            "Nome de conta inválido: '{0}'. Use de 2 a 32 caracteres contendo apenas "
            "letras minúsculas, números, sublinhado (_) ou hífen (-).".format(conta)
        )
    if conta in RESERVED_SYSTEM_USERS:
        raise ValueError("O nome de conta '{0}' é reservado pelo sistema.".format(conta))
    return conta


def _validate_domain(domain):
    """Valida formato de domínio."""
    if not domain or not isinstance(domain, str):
        raise ValueError("Domínio não pode ser vazio.")
    domain = domain.strip().lower()
    if not re.match(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$", domain):
        raise ValueError("Domínio inválido: '{0}'. Exemplo: meusite.com.br".format(domain))
    return domain


def _validate_port(port, conn=None):
    """Valida porta TCP e verifica se já está em uso."""
    try:
        p = int(str(port).strip())
    except (ValueError, TypeError):
        raise ValueError("Porta inválida: '{0}'. Informe um número entre 1024 e 65535.".format(port))
    if not (1024 <= p <= 65535):
        raise ValueError("Porta fora do intervalo permitido (1024-65535): {0}".format(p))

    if conn:
        res = conn.sudo("ss -tulpn 2>/dev/null | grep -E ':{0}\\b' || true".format(p), warn=True, hide=True)
        if res and getattr(res, "ok", False) and getattr(res, "stdout", "").strip():
            log("AVISO: A porta {0} já aparenta estar em uso por outro processo ativo no sistema!".format(p), yellow)
    return str(p)


def _install_supervisorctl_restricted(conn):
    """Instala ou atualiza o wrapper seguro supervisorctl-restricted em /usr/local/bin."""
    src_path = os.path.join(CURRENT_PATH, "inc", "supervisorctl-restricted")
    with open(src_path, "rb") as f:
        content = f.read()
    remote_tmp = "/tmp/supervisorctl-restricted.{0}.tmp".format(uuid.uuid4().hex)
    conn.put(BytesIO(content), remote=remote_tmp)
    conn.sudo("mv {0} /usr/local/bin/supervisorctl-restricted".format(remote_tmp))
    conn.sudo("chown root:root /usr/local/bin/supervisorctl-restricted")
    conn.sudo("chmod 755 /usr/local/bin/supervisorctl-restricted")


def write_file(filename, destination):
    """Renderiza um template Jinja2 de inc/ e envia para o servidor.
    Substitui fabric.contrib.files.upload_template (removido no Fabric 2+)."""
    content = _jinja_env.get_template(filename).render(**cfg)

    conn = get_connection()
    remote_tmp = "/tmp/{0}.{1}.tmp".format(os.path.basename(destination), uuid.uuid4().hex)
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
    "debian": "mysql-server libmysqlclient-dev default-libmysqlclient-dev build-essential pkg-config",
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

_SUPERVISOR_CONF_DIR_BY_FAMILY = {
    "debian": "/etc/supervisor/conf.d",
    "fedora": "/etc/supervisord.d",
    "rhel": "/etc/supervisord.d",
    "arch": "/etc/supervisor.d",
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

_CERTBOT_PACKAGES_BY_FAMILY = {
    "debian": "certbot python3-certbot-nginx",
    "fedora": "certbot python3-certbot-nginx",
    "rhel": "certbot python3-certbot-nginx",
    "arch": "certbot certbot-nginx",
}

_NODE_PACKAGES_BY_FAMILY = {
    "debian": "nodejs npm",
    "fedora": "nodejs npm",
    "rhel": "nodejs npm",
    "arch": "nodejs npm",
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
    """Gera uma senha aleatória e criptograficamente segura (módulo `secrets`, não
    `random`) com pelo menos 12 caracteres, garantindo sempre ao menos uma letra
    maiúscula, uma minúscula, um número e um caractere especial - em vez de sortear
    tudo de um pool único, onde por azar podia sair uma senha sem nenhum símbolo ou
    sem maiúscula. Os especiais usados (`!@#%^*_-+=`) evitam aspas, barra invertida,
    `$`, `` ` `` e `&`, que podem quebrar a senha ao serem interpoladas em comandos
    SQL/shell (ex: `CREATE USER ... IDENTIFIED BY '{senha}'`)."""
    import secrets

    tamanho = max(tamanho, 4)  # precisa de espaço pras 4 categorias obrigatórias

    minusculas = "abcdefghijklmnopqrstuvwxyz"
    maiusculas = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    numeros = "0123456789"
    especiais = "!@#%^*_-+="
    todos = minusculas + maiusculas + numeros + especiais

    senha_chars = [
        secrets.choice(minusculas),
        secrets.choice(maiusculas),
        secrets.choice(numeros),
        secrets.choice(especiais),
    ]
    senha_chars += [secrets.choice(todos) for _ in range(tamanho - len(senha_chars))]

    secrets.SystemRandom().shuffle(senha_chars)
    return "".join(senha_chars)


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
    node_server(c)
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
    supervisor_dir = _SUPERVISOR_CONF_DIR_BY_FAMILY[cfg.os_family]
    conn.sudo("mkdir -p {0}".format(supervisor_dir))
    _install_supervisorctl_restricted(conn)
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
    cfg.conta = _validate_account_name(cfg.conta)

    if not cfg.dominio:
        cfg.dominio = input("Digite o domínio do site (sem www): ")
    cfg.dominio = _validate_domain(cfg.dominio)

    if not cfg.linguagem:
        cfg.linguagem = input(
            "Linguagens disponíveis\n\n1) PYTHON\n2) PHP\n3) NPM (Node.js)\n\nEscolha a linguagem: "
        )
    lang_str = str(cfg.linguagem).strip().lower()
    if lang_str in ("1", "python"):
        lang_id = 1
    elif lang_str in ("2", "php"):
        lang_id = 2
    elif lang_str in ("3", "npm", "node", "nodejs"):
        lang_id = 3
    else:
        try:
            lang_id = int(lang_str)
        except ValueError:
            lang_id = 1

    if lang_id == 1:
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
        cfg.porta = _validate_port(cfg.porta, conn=conn)
        if not cfg.pasta_settings:
            cfg.pasta_settings = input(
                "Digite o nome da pasta onde está o settings/wsgi. ( Ex: app, config, [nome-do-projeto] ):"
            )
    elif lang_id == 3:
        if not getattr(cfg, "npm_type", None):
            cfg.npm_type = input(
                "Tipo de aplicação NPM:\n1) Node.js SSR / API (com Supervisor na porta TCP e proxy reverso Nginx)\n2) Frontend Estático / SPA (Nginx servindo pasta dist/build)\n\nEscolha o tipo [1]: "
            ).strip() or "1"
        npm_type_str = str(cfg.npm_type).strip().lower()
        if npm_type_str in ("1", "ssr", "node", "api"):
            npm_type_id = 1
        else:
            npm_type_id = 2
        cfg.npm_type = str(npm_type_id)

        if npm_type_id == 1:
            if not cfg.porta:
                log(
                    "ATENCAO!! VERIFIQUE AS PORTAS JÁ UTILIZADAS\nOBS: abaixo estão apenas as portas utilizadas pelas conexões tcp e sites, porém\noutro programa no servidor pode estar utilizando uma porta não listada abaixo.",
                    yellow,
                )
                conn.sudo("ss -tulpn")
                cfg.porta = input(
                    "Digite o número de uma porta que não está listada acima: "
                )
            cfg.porta = _validate_port(cfg.porta, conn=conn)
            if not getattr(cfg, "npm_start_cmd", None):
                cfg.npm_start_cmd = input(
                    "Comando para iniciar a aplicação [npm run start]: "
                ).strip() or "npm run start"

    if not cfg.mysql_password:
        cfg.mysql_password = input("Digite a senha do ROOT do MySQL: ")

    # cria usuario no linux
    user_senha = create_password(12)
    adduser(c, cfg.conta, user_senha)

    conn.sudo("mkdir /home/{0}/logs".format(cfg.conta))
    conn.sudo("touch /home/{0}/logs/access.log".format(cfg.conta))
    conn.sudo("touch /home/{0}/logs/error.log".format(cfg.conta))

    if lang_id == 1:
        conn.sudo("python3 -m venv /home/{0}/env".format(cfg.conta))
        write_file("nginx.conf", "/home/{0}/nginx.conf".format(cfg.conta))
        write_file("supervisor.ini", "/home/{0}/supervisor.ini".format(cfg.conta))
        write_file("bash_login", "/home/{0}/.bash_login".format(cfg.conta))
    elif lang_id == 2:
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
    elif lang_id == 3:
        npm_type_id = int(getattr(cfg, "npm_type", 1) or 1)
        if npm_type_id == 1:
            write_file("nginx_node.conf", "/home/{0}/nginx.conf".format(cfg.conta))
            write_file("supervisor_node.ini", "/home/{0}/supervisor.ini".format(cfg.conta))
            write_file("bash_login", "/home/{0}/.bash_login".format(cfg.conta))
            conn.sudo("mkdir -p /home/{0}/project".format(cfg.conta))
        else:
            write_file("nginx_npm_static.conf", "/home/{0}/nginx.conf".format(cfg.conta))
            conn.sudo("mkdir -p /home/{0}/project/dist".format(cfg.conta))
            conn.sudo("mkdir -p /home/{0}/public_html".format(cfg.conta))

    # cria banco e usuario no banco
    banco_senha = create_password(12)
    newbase(c, cfg.conta, banco_senha)

    # da permissao para o usuario no diretorio e aplica isolamento estrito (750)
    conn.sudo("chown -R {0}:{0} /home/{0}".format(cfg.conta))
    conn.sudo("chmod 750 /home/{0}".format(cfg.conta))
    conn.sudo("chmod 750 /home/{0}/logs".format(cfg.conta))
    conn.sudo("chmod 640 /home/{0}/logs/access.log /home/{0}/logs/error.log".format(cfg.conta))
    conn.sudo("mkdir -p /home/{0}/.ssh".format(cfg.conta))
    conn.sudo("chmod 700 /home/{0}/.ssh".format(cfg.conta))
    conn.sudo("touch /home/{0}/.ssh/authorized_keys".format(cfg.conta))
    conn.sudo("chmod 600 /home/{0}/.ssh/authorized_keys".format(cfg.conta))
    conn.sudo("chown -R {0}:{0} /home/{0}/.ssh".format(cfg.conta))

    # adiciona o usuario do nginx ao grupo da conta para permitir leitura de estáticos e sockets
    nginx_user = _NGINX_USER_BY_FAMILY[cfg.os_family]
    conn.sudo("usermod -a -G {0} {1}".format(cfg.conta, nginx_user))

    # instala controlador restrito e configura sudoers para privilegios minimos
    _install_supervisorctl_restricted(conn)
    write_file("sudoers.conf", "/etc/sudoers.d/{0}".format(cfg.conta))
    conn.sudo("chown root:root /etc/sudoers.d/{0}".format(cfg.conta))
    conn.sudo("chmod 0440 /etc/sudoers.d/{0}".format(cfg.conta))
    conn.sudo("visudo -cf /etc/sudoers.d/{0}".format(cfg.conta))

    # registra nova aplicação no supervisor sem reiniciar processos existentes
    # a configuração permanece diretamente em /home/{conta}/supervisor.ini
    if lang_id == 1 or (lang_id == 3 and npm_type_id == 1):
        conn.sudo("supervisorctl reread")
        conn.sudo("supervisorctl update")

    # testa configuracao do nginx e recarrega de forma transparente (sem interromper outros sites)
    conn.sudo("nginx -t")
    conn.sudo("systemctl reload nginx")

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
    conta = _validate_account_name(conta)
    log("Deletando usuário {0}".format(conta), red)
    conn = get_connection()
    supervisor_dir = _SUPERVISOR_CONF_DIR_BY_FAMILY.get(cfg.os_family, "/etc/supervisor/conf.d")
    conn.sudo("rm -f {0}/{1}.conf".format(supervisor_dir, conta), warn=True)
    conn.sudo("rm -f /etc/sudoers.d/{0}".format(conta))
    conn.sudo("supervisorctl stop {0}:*".format(conta), warn=True)
    conn.sudo("supervisorctl stop {0}".format(conta), warn=True)
    conn.sudo("userdel -r {0}".format(conta))
    conn.sudo("supervisorctl reread", warn=True)
    conn.sudo("supervisorctl update", warn=True)


@task
def migrate_account(c, conta=None):
    """Migra um projeto existente para o modelo de isolamento seguro e controle restrito."""
    conn = get_connection()
    if not conta:
        conta = input("Digite o nome da conta a migrar: ")
    conta = _validate_account_name(conta)

    res = conn.sudo("test -d /home/{0}".format(conta), warn=True)
    if res.failed:
        log("ERRO: Diretório /home/{0} não encontrado.".format(conta), red)
        return False

    log("Iniciando migração segura do projeto: {0}".format(conta), yellow)

    # 1. Backup de segurança com timestamp
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = "/home/{0}/.backup_migration_{1}".format(conta, ts)
    conn.sudo("mkdir -p {0}".format(backup_dir))
    conn.sudo("test -f /home/{0}/supervisor.ini && cp /home/{0}/supervisor.ini {1}/supervisor.ini || true".format(conta, backup_dir))
    conn.sudo("test -f /home/{0}/nginx.conf && cp /home/{0}/nginx.conf {1}/nginx.conf || true".format(conta, backup_dir))
    conn.sudo("test -f /etc/sudoers.d/{0} && cp /etc/sudoers.d/{0} {1}/sudoers || true".format(conta, backup_dir))
    log("Backup de segurança criado em {0}".format(backup_dir), green)

    # 2. Instalação do supervisorctl-restricted
    _install_supervisorctl_restricted(conn)

    # 3. Criação da regra de sudoers restrita
    cfg.conta = conta
    write_file("sudoers.conf", "/etc/sudoers.d/{0}".format(conta))
    conn.sudo("chown root:root /etc/sudoers.d/{0}".format(conta))
    conn.sudo("chmod 0440 /etc/sudoers.d/{0}".format(conta))
    conn.sudo("visudo -cf /etc/sudoers.d/{0}".format(conta))

    # 4. Ajuste de permissões de isolamento (750)
    conn.sudo("chown -R {0}:{0} /home/{0}".format(conta))
    conn.sudo("chmod 750 /home/{0}".format(conta))
    nginx_user = _NGINX_USER_BY_FAMILY[cfg.os_family]
    conn.sudo("usermod -a -G {0} {1}".format(conta, nginx_user))

    # Ajusta permissões em logs e .ssh
    conn.sudo("test -d /home/{0}/logs && chmod 750 /home/{0}/logs || true".format(conta))
    conn.sudo("test -d /home/{0}/logs && chmod 640 /home/{0}/logs/*.log 2>/dev/null || true".format(conta))
    conn.sudo("test -d /home/{0}/.ssh && chmod 700 /home/{0}/.ssh || true".format(conta))
    conn.sudo("test -f /home/{0}/.ssh/authorized_keys && chmod 600 /home/{0}/.ssh/authorized_keys || true".format(conta))

    # 5. Reread e update no Supervisor (sem reiniciar processos ativos dos demais projetos)
    # A configuracao permanece exclusivamente em /home/{conta}/supervisor.ini
    conn.sudo("supervisorctl reread")
    conn.sudo("supervisorctl update")

    # 7. Teste de status restrito
    log("Testando controle restrito do Supervisor:", green)
    conn.sudo("su - {0} -c 'sudo /usr/local/bin/supervisorctl-restricted {0} status'".format(conta), warn=True)

    log("✔ Projeto '{0}' migrado com sucesso para o modelo restrito!".format(conta), green)
    return True


@task
def migrate_all_projects(c):
    """Detecta todos os projetos existentes em /home/* e migra cada um com segurança."""
    conn = get_connection()
    log("Descobrindo contas existentes em /home...", yellow)
    res = conn.sudo("ls -1 /home", hide=True, warn=True)
    if res.failed or not res.stdout.strip():
        log("Nenhuma pasta de usuário encontrada em /home.", red)
        return

    users = [u.strip() for u in res.stdout.splitlines() if u.strip()]
    migrated = []
    for u in users:
        chk = conn.sudo("test -f /home/{0}/supervisor.ini || test -f /home/{0}/nginx.conf".format(u), warn=True, hide=True)
        if chk.ok:
            migrated.append(u)

    if not migrated:
        log("Nenhum projeto com supervisor.ini ou nginx.conf encontrado.", yellow)
        return

    print("Projetos detectados para migração:\n - " + "\n - ".join(migrated))
    if not confirm("Deseja migrar todos os projetos listados acima com backup automático?"):
        log("Migração cancelada.")
        return

    for u in migrated:
        migrate_account(c, conta=u)
    log("✔ Migração de todos os projetos concluída!", green)


@task
def rollback_migration(c, conta=None):
    """Reverte permissões e restaura configurações de backup caso ocorra algum problema."""
    conn = get_connection()
    if not conta:
        conta = input("Digite o nome da conta para rollback: ")
    conta = _validate_account_name(conta)

    log("Iniciando rollback para o projeto {0}...".format(conta), yellow)
    conn.sudo("chmod 755 /home/{0}".format(conta))

    res = conn.sudo("ls -d /home/{0}/.backup_migration_* 2>/dev/null | sort | tail -n 1".format(conta), hide=True, warn=True)
    if res.ok and res.stdout.strip():
        last_backup = res.stdout.strip()
        log("Restaurando arquivos a partir de {0}...".format(last_backup), yellow)
        conn.sudo("test -f {0}/supervisor.ini && cp {0}/supervisor.ini /home/{1}/supervisor.ini || true".format(last_backup, conta))
        conn.sudo("test -f {0}/sudoers && cp {0}/sudoers /etc/sudoers.d/{1} || true".format(last_backup, conta))
        conn.sudo("supervisorctl reread && supervisorctl update", warn=True)
        log("✔ Arquivos restaurados a partir do backup.", green)
    else:
        log("AVISO: Nenhum diretório de backup automático foi localizado.", yellow)

    log("Rollback concluído para {0}.".format(conta), green)


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
def node_server(c):
    """Instalar Node.js e NPM no servidor"""
    log("Instalando Node.js e NPM", yellow)
    _ensure_epel(c)
    _install(c, _NODE_PACKAGES_BY_FAMILY[cfg.os_family])


@task
def install_mysql_deps(c):
    """Instalar dependências necessárias para compilar mysqlclient no servidor"""
    log("Instalando dependências do MySQL para compilação do mysqlclient", yellow)
    family = cfg.os_family
    
    if family == "debian":
        _install(c, "default-libmysqlclient-dev build-essential pkg-config")
    elif family in ("fedora", "rhel"):
        _install(c, "mariadb-devel gcc gcc-c++ make")
    elif family == "arch":
        _install(c, "mariadb-libs base-devel")
    
    log("✔ Dependências do MySQL instaladas com sucesso!", green)


@task
def others_server(c):
    """Instalar nginx, supervisor, php-fpm e certbot (SSL)"""
    log("Instalando nginx, supervisor e certbot", yellow)
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

    _install(c, _CERTBOT_PACKAGES_BY_FAMILY[family])


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


@task
def install_ssl(c, dominio=None):
    """Instala Certbot e ativa Certificado SSL gratuito (Let's Encrypt) no Nginx"""
    log("Instalando e ativando Certificado SSL Let's Encrypt", green)
    conn = get_connection()
    family = cfg.os_family

    _ensure_epel(c)
    _install(c, _CERTBOT_PACKAGES_BY_FAMILY[family])

    if not dominio:
        dominio = input("Digite o domínio para ativar o SSL (ex: meudominio.com): ").strip()

    conn.sudo(
        "certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email -d {0} -d www.{0}".format(
            dominio
        )
    )
    conn.sudo("systemctl reload nginx")
    log("✔ SSL ativado com sucesso para https://{0}".format(dominio), green)

