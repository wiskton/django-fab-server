# -*- coding: utf-8 -*-
import functools
import os
from io import StringIO

from fabric import Connection, task
from jinja2 import Environment, FileSystemLoader

CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------
# ALTERAR CONFIGURAÇÕES BASEADAS NO SEUS SERVIDOR E MAQUINA LOCAL
# Testado para servidores Ubuntu 24.04 LTS
# ----------------------------------------------------------------

# SERVIDOR
user = "root"
host = "192.168.0.1"
chave = ""  # caminho da chave nome_arquivo.pem

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
    pasta_settings="",
    db_password="",
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
    conn.put(StringIO(content), remote=remote_tmp)
    conn.sudo("test -f {0} && cp {0} {0}.bak || true".format(destination))
    conn.sudo("mv {0} {1}".format(remote_tmp, destination))


def _systemctl(service, action):
    """Executa uma ação do systemctl em um serviço no servidor."""
    get_connection().sudo("systemctl {0} {1}".format(action, service))


_BUILD_PACKAGES = (
    "build-essential automake",
    "libxml2-dev libxslt-dev",
    "libjpeg-dev zlib1g-dev libfreetype6-dev libwebp-dev",
)


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
    conn.put(StringIO(sql), remote=sql_path)
    conn.sudo("chmod 600 {0}".format(sql_path))

    cnf_path = None
    defaults_flag = ""
    if password:
        cnf_path = "/tmp/.fab_{0}.cnf".format(token)
        conn.put(StringIO("[client]\npassword={0}\n".format(password)), remote=cnf_path)
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
    print(yellow("nginx - Alterando arquivo /etc/nginx/nginx.conf"))
    write_file("nginx_server.conf", "/etc/nginx/nginx.conf")
    nginx_restart(c)

    # proftpd
    print(yellow("proftpd - Alterando arquivo /etc/proftpd/proftpd.conf"))
    write_file("proftpd.conf", "/etc/proftpd/proftpd.conf")
    proftpd_restart(c)

    # supervisor
    print(yellow("supervisor - Alterando arquivo /etc/supervisor/supervisord.conf"))
    write_file("supervisord_server.conf", "/etc/supervisor/supervisord.conf")
    supervisor_restart(c)

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
            conn.sudo("netstat -tulpn")
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

        log(
            """IMPORTANTE!!! Para o funcionamento dos projetos em php com nginx é necessário que se
                altere o arquivo /etc/php/8.3/fpm/php.ini\n
                Execute o comando: sudo nano /etc/php/8.3/fpm/php.ini\n
                Descomente e altere para 0 a var abaixo\n
                cgi.fix_pathinfo=0\n""",
            yellow,
        )

        input(
            "Alterar cgi.fix_pathinfo para 0 - Pressione ENTER para continuar.."
        )

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
    """Executa apt install no servidor ex: fab aptget --lib=python3-pip"""
    log("Executa apt install no servidor", yellow)
    if not lib:
        lib = input("Digite o pacote para instalar: sudo apt install ")

    if lib:
        get_connection().sudo("apt install {0}".format(lib))


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
    get_connection().sudo("apt -y update")


@task
def upgrade_server(c):
    """Atualizar programas no servidor"""
    log("Atualizando programas", yellow)
    get_connection().sudo("apt -y upgrade")


@task
def build_server(c):
    """Instalar build-essential e outros pacotes importantes no servidor"""
    log("Instalando build-essential e outros pacotes", yellow)
    conn = get_connection()
    for packages in _BUILD_PACKAGES:
        conn.sudo("apt -y install {0}".format(packages))


@task
def python_server(c):
    """Instalar todos pacotes necessários do python no servidor"""
    log("Instalando todos pacotes necessários", yellow)
    conn = get_connection()
    conn.sudo(
        "apt -y install python3 python3-dev python3-venv python3-pip python3-pil python3-mysqldb"
    )


@task
def mysql_server(c):
    """Instalar MySQL no servidor"""
    log("Instalando MySQL", yellow)

    if confirm("Deseja que o script gere senha automatica para o mysql?"):
        db_password = create_password(12)
    else:
        db_password = input("Digite a senha root do mysql: ")

    cfg.db_password = db_password

    conn = get_connection()
    conn.sudo("apt -y install mysql-server libmysqlclient-dev")

    # nas versões atuais do mysql-server o usuário root usa auth_socket por
    # padrão (sem senha via debconf); definimos a senha explicitamente aqui.
    # `sudo mysql` já autentica via socket (usuário do SO = root), sem
    # precisar de senha nesta primeira chamada.
    _mysql_exec(
        "ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY '{0}'; FLUSH PRIVILEGES;".format(
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
    get_connection().sudo("apt -y install git")


@task
def others_server(c):
    """Instalar nginx, supervisor e php-fpm"""
    log("Instalando nginx e supervisor", yellow)
    conn = get_connection()
    conn.sudo("apt -y install nginx supervisor")
    conn.sudo("apt -y install mercurial")

    conn.sudo("add-apt-repository -y universe")
    conn.sudo(
        "apt -y install php8.3-fpm php8.3-mysql php8.3-gd php8.3-imagick php8.3-curl php8.3-cli"
    )
    conn.sudo("apt -y install proftpd")


@task
def login(c):
    """Acessa o servidor"""
    if chave:
        c.run("ssh %s -i %s" % (prod_server, cfg.key_filename))
    else:
        c.run("ssh %s" % prod_server)


@task
def upload_public_key(c):
    """Faz o upload da chave ssh para o servidor"""
    log("Adicionando chave publica no servidor", green)
    conn = get_connection()
    ssh_file = "~/.ssh/id_rsa.pub"
    target_path = "~/.ssh/uploaded_key.pub"
    conn.put(ssh_file, target_path)
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
    """restart proftpd"""
    log("restart proftpd", yellow)
    _systemctl("proftpd", "restart")


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
    _systemctl("supervisor", "start")


@task
def supervisor_stop(c):
    """Stop supervisor no servidor"""
    log("stop supervisor", red)
    _systemctl("supervisor", "stop")


@task
def supervisor_restart(c):
    """Restart supervisor no servidor"""
    log("restart supervisor", yellow)
    _systemctl("supervisor", "restart")


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
    _systemctl("mysql", "restart")


@task
def mysql_start(c):
    """start mysql no servidor"""
    log("start mysql", green)
    _systemctl("mysql", "start")


@task
def mysql_stop(c):
    """stop mysql no servidor"""
    log("stop mysql", red)
    _systemctl("mysql", "stop")


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
    """Configura uma maquina local Ubuntu para trabalhar python/django"""
    log("Configura uma computador Ubuntu para trabalhar python/django", yellow)
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
    c.run("sudo apt -y update")


@task
def upgrade_local(c):
    """Atualizando programas"""
    log("Atualizando programas", yellow)
    c.run("sudo apt -y upgrade")


@task
def build_local(c):
    """Instalar build-essential"""
    log("instalando build-essential gcc++", yellow)
    for packages in _BUILD_PACKAGES:
        c.run("sudo apt -y install {0}".format(packages))
    c.run("sudo apt -y install terminator")


@task
def python_local(c):
    """Instalando todos pacotes necessários"""
    log("Instalando todos pacotes necessários", yellow)
    c.run(
        "sudo apt -y install python3 python3-dev python3-venv python3-pip python3-pil"
    )


@task
def mysql_local(c):
    """Instalando MySQL"""
    log("Instalando MySQL", yellow)
    c.run("sudo apt -y install mysql-server libmysqlclient-dev")


@task
def git_local(c):
    """Instalando git"""
    log("Instalando git", yellow)
    c.run("sudo apt -y install git")
