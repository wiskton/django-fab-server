# -*- coding: utf-8 -*-
import os
from os.path import exists
from fabric.api import *
from fabric.colors import green, red, white, yellow
from fabric.contrib.console import confirm
from fabric.contrib.files import upload_template
from dotenv import load_dotenv
from pathlib import Path

try:
    dotenv_path = Path('variable.env')
    load_dotenv(dotenv_path=dotenv_path)
except ImportError:
    print("crie o arquivo variable.env utilizando o variable-template")

CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------
# ALTERAR CONFIGURAÇÕES BASEADAS NO SEUS SERVIDOR E MAQUINA LOCAL
# ----------------------------------------------------------------

# SERVIDOR
user = os.environ.get("SSH_USER", "root")
host = os.environ.get("SSH_HOST", "localhost")
key_pem = os.environ.get("SSH_PEM", "")  # caminho da chave pem nome_arquivo.pem

# LOCAL
git_user = os.environ.get("GIT_USER", "")
git_default_project = os.environ.get("GIT_DEFAULT_PROJECT", "")
folder_project_local = os.environ.get("DIR_PROJECTS", "")

# diretório do conf.d do supervisor
env.supervisor_conf_d_path = "/etc/supervisor/conf.d"

# nome da conta
env.conta = ""

# dominio da conta
env.dominio = ""

# linguagem 1-python 2-php
env.linguagem = ""

# senha do root do mysql
env.mysql_password = os.environ.get("MYSQL_ROOT_PW", "")

# porta para rodar o projeto
env.porta = ""

# diretório do sites-enable do nginx
env.nginx_sites_enable_path = "/etc/nginx/sites-enabled"

# endereco da chave
env.key_filename = key_pem

# verificando django1.7 para supervisor
env.django17 = False
env.pasta_settings = ""
env.db_password = ""

# --------------------------------------------------------

prod_server = "{0}@{1}".format(user, host)
project_path = "/home/"

env.hosts = [prod_server]

# --------------------------------------------------------
# SERVIDOR
# --------------------------------------------------------


def newserver():
    """Configurar e instalar todos pacotes necessários para servidor"""
    log("Configurar e instalar todos pacotes necessários para servidor", yellow)

    # gera uma chave no servidor para utilizar o comando upload_public_key
    # if not exists("~/.ssh/id_rsa.pub"):
    #     local('ssh-keygen')

    # upload_public_key()

    update_server()
    upgrade_server()

    # # pacotes
    build_server()
    python_server()
    mysql_server()
    git_server()
    others_server()

    # mysql
    mysql_restart()

    # nginx
    print(yellow("nginx - Alterando arquivo /etc/nginx/nginx.conf"))
    write_file("nginx_server.conf", "/etc/nginx/nginx.conf")
    nginx_restart()

    # proftpd
    print(yellow("proftpd - Alterando arquivo /etc/proftpd/proftpd.conf"))
    write_file("proftpd.conf", "/etc/proftpd/proftpd.conf")
    proftpd_restart()

    # supervisor
    print(yellow("supervisor - Alterando arquivo /etc/supervisor/supervisord.conf"))
    write_file("supervisord_server.conf", "/etc/supervisor/supervisord.conf")
    supervisor_restart()

    log("Anote a senha do banco de dados: {0}".format(env.db_password), green)

    log("Reiniciando a máquina", yellow)
    reboot()


# cria uma conta no servidor
def newaccount():
    """Criar uma nova conta do usuário no servidor"""
    log("Criar uma nova conta do usuário no servidor", yellow)

    # criando usuario
    if not env.conta:
        env.conta = input("Digite o nome da conta: ")
    if not env.dominio:
        env.dominio = input("Digite o domínio do site (sem www): ")
    if not env.linguagem:
        env.linguagem = input(
            "Linguagens disponíveis\n\n1) PYTHON\n2) PHP\n\nEscolha a linguagem: "
        )
        if not env.porta and int(env.linguagem) == 1:
            log(
                "ATENCAO!! VERIFIQUE AS PORTAS JÁ UTILIZADAS\nOBS: abaixo estão apenas as portas utilizadas pelas conexões tcp e sites, porém\noutro programa no servidor pode estar utilizando uma porta não listada abaixo.",
                yellow,
            )
            sudo("netstat -tulpn")
            env.porta = input(
                "Digite o número de uma porta que não está listada acima: "
            )
            if confirm("Este projeto está em django 1.7?"):
                env.django17 = True
                env.pasta_settings = input(
                    "Digite o nome da pasta onde está o settings. ( Ex: app, config, [nome-do-projeto] ):"
                )
                log(
                    "ATENÇÃO!! PARA DJANGO 1.7 A VERSÃO DO GUNICORN NO ENV DEVE SER 19++",
                    green,
                )
    if not env.mysql_password:
        env.mysql_password = input("Digite a senha do ROOT do MySQL: ")

    # cria usuario no linux
    user_senha = create_password(12)
    adduser(env.conta, user_senha)

    sudo("mkdir /home/{0}/logs".format(env.conta))
    sudo("touch /home/{0}/logs/access.log".format(env.conta))
    sudo("touch /home/{0}/logs/error.log".format(env.conta))

    if int(env.linguagem) == 1:
        sudo("virtualenv /home/{0}/env --no-site-packages".format(env.conta))
        write_file("nginx.conf", "/home/{0}/nginx.conf".format(env.conta))
        if env.django17:
            write_file(
                "supervisor_django17.ini", "/home/{0}/supervisor.ini".format(env.conta)
            )
        else:
            write_file("supervisor.ini", "/home/{0}/supervisor.ini".format(env.conta))
        write_file("bash_login", "/home/{0}/.bash_login".format(env.conta))
    else:

        log(
            """IMPORTANTE!!! Para o funcionamento dos projetos em php com nginx é necessário que se
                altere a linha 768 do arquivo /etc/php5/fpm/php.ini\n
                Execute o comando: sudo nano /etc/php5/fpm/php.ini\n
                Descomente e altere para 1 a var abaixo\n
                cgi.fix_pathinfo=0\n""",
            yellow,
        )

        input(
            "Descomentar e alterar cgi.fix_pathinfo=0 para cgi.fix_pathinfo=1 - Pressione ENTER para continuar.."
        )

        write_file("nginx_php.conf", "/home/{0}/nginx.conf".format(env.conta))
        sudo("mkdir /home/{0}/public_html/".format(env.conta))

    # cria banco e usuario no banco
    banco_senha = create_password(12)
    newbase(env.conta, banco_senha)

    # da permissao para o usuario no diretorio
    sudo("chown -R {0}:{0} /home/{0}".format(env.conta))

    nginx_restart()
    supervisor_restart()

    # log para salvar no docs
    log("Anotar dados da conta", green)
    print(
        green(
            "conta: {0} \n\n-- ssh\nuser: {0}\npw sugerido: {1} \n\n-- banco\nuser: {0}\npw: {2}".format(
                env.conta, user_senha, banco_senha
            )
        )
    )


def listaccount():
    """Lista usuários do servidor"""
    log("Lista usuários do servidor", yellow)
    with cd("/home/"):
        run("ls")


def aptget(lib=None):
    """Executa apt install no servidor ex: fab aptget:lib=python-pip"""
    log("Executa apt install no servidor", yellow)
    if not lib:
        lib = input("Digite o pacote para instalar: sudo apt install ")

    if lib:
        sudo("apt install {0}".format(lib))
    # sudo('aptget {0}'.format(display))


def write_file(filename, destination):

    upload_template(
        filename=filename,
        destination=destination,
        template_dir=os.path.join(CURRENT_PATH, "inc"),
        context=env,
        use_jinja=True,
        use_sudo=True,
        backup=True,
    )


# deleta uma conta no servidor
def delaccount():
    """Deletar conta no servidor"""
    conta = input("Digite o nome da conta: ")
    env.mysql_password = input("Digite a senha do ROOT do MySQL: ")
    log("Deletando conta {0}".format(conta), red)
    userdel(conta)
    dropbase(conta)


# cria usuario no servidor
def adduser(conta=None, user_senha=None):
    """Criar um usuário no servidor"""

    if not user_senha:
        user_senha = create_password(12)
    print("sugestao de Unix password: {0}".format(user_senha))

    if not conta:
        conta = input("Digite o nome do usuário: ")

    log("Criando usuário {0}".format(conta), green)
    sudo("adduser {0}".format(conta))
    # sudo('useradd -m -p pass=$(perl -e \'print crypt($ARGV[0], "password")\' \'{0}\') {1}'.format(user_senha, conta))
    print(
        "\n================================================================================"
    )


# MYSQL - cria usuario e banco de dados
def newbase(conta=None, banco_senha=None):
    """Criar banco de dados e usuário no servidor"""

    if not banco_senha:
        banco_senha = create_password(12)
    print("Senha gerada para o banco: {0}".format(banco_senha))

    if not conta:
        conta = input("Digite o nome do banco: ")
    log("NEW DATABASE {0}".format(conta), green)

    # cria acesso para o banco local
    sudo(
        "echo CREATE DATABASE {0} | mysql -u root -p{1}".format(
            conta, env.mysql_password
        )
    )
    sudo(
        "echo \"CREATE USER '{0}'@'localhost' IDENTIFIED BY '{1}'\" | mysql -u root -p{2}".format(
            conta, banco_senha, env.mysql_password
        )
    )
    sudo(
        "echo \"GRANT ALL PRIVILEGES ON {0} . * TO '{0}'@'localhost'\" | mysql -u root -p{1}".format(
            conta, env.mysql_password
        )
    )

    # cria acesso para o banco remoto
    sudo(
        "echo \"CREATE USER '{0}'@'%' IDENTIFIED BY '{1}'\" | mysql -u root -p{2}".format(
            conta, banco_senha, env.mysql_password
        )
    )
    sudo(
        "echo \"GRANT ALL PRIVILEGES ON {0} . * TO '{0}'@'%'\" | mysql -u root -p{1}".format(
            conta, env.mysql_password
        )
    )


# MYSQL - deleta o usuario e o banco de dados
def dropbase(conta=None):
    """Deletar banco de dados no servidor"""
    if not conta:
        conta = input("Digite o nome do banco: ")
    if not env.mysql_password:
        env.mysql_password = input("Digite a senha do ROOT do MySQL: ")
    sudo(
        "echo DROP DATABASE {0} | mysql -u root -p{1}".format(conta, env.mysql_password)
    )
    sudo(
        "echo \"DROP USER '{0}'@'localhost'\" | mysql -u root -p{1}".format(
            conta, env.mysql_password
        )
    )
    sudo(
        "echo \"DROP USER '{0}'@'%'\" | mysql -u root -p{1}".format(
            conta, env.mysql_password
        )
    )


# LINUX - deleta o usuario
def userdel(conta=None):
    """Deletar usuário no servidor"""
    if not conta:
        conta = input("Digite o nome do usuario: ")
    log("Deletando usuário {0}".format(conta), red)
    sudo("userdel -r {0}".format(conta))


# update no servidor
def update_server():
    """Atualizando pacotes no servidor"""
    log("Atualizando pacotes", yellow)
    sudo("apt -y update")


# upgrade no servidor
def upgrade_server():
    """Atualizar programas no servidor"""
    log("Atualizando programas", yellow)
    sudo("apt -y upgrade")


def build_server():
    """Instalar build-essential e outros pacotes importantes no servidor"""
    log("Instalando build-essential e outros pacotes", yellow)
    sudo("apt -y install build-essential automake")
    sudo("apt -y install libxml2-dev libxslt-dev")
    sudo(
        "apt -y install libjpeg-dev libjpeg8-dev zlib1g-dev libfreetype6 libfreetype6-dev"
    )

    # Then, on 32-bit Ubuntu, you should run:

    # sudo ln -s /usr/lib/i386-linux-gnu/libfreetype.so /usr/lib/
    # sudo ln -s /usr/lib/i386-linux-gnu/libz.so /usr/lib/
    # sudo ln -s /usr/lib/i386-linux-gnu/libjpeg.so /usr/lib/

    # Otherwise, on 64-bit Ubuntu, you should run:

    try:
        sudo("ln -s /usr/lib/x86_64-linux-gnu/libfreetype.so /usr/lib/")
        sudo("ln -s /usr/lib/x86_64-linux-gnu/libz.so /usr/lib/")
        sudo("ln -s /usr/lib/x86_64-linux-gnu/libjpeg.so /usr/lib/")
    except:
        pass


def python_server():
    """Instalar todos pacotes necessários do python no servidor"""
    log("Instalando todos pacotes necessários", yellow)
    sudo("sudo apt -y install libjpeg-dev libfreetype6 libfreetype6-dev zlib1g-dev")
    sudo("apt -y install python-pil libjpeg62 libjpeg62-dev")
    sudo("apt -y install python3 python3-dev python3-setuptools python3-mysqldb python3-pip python3-virtualenv")


def mysql_server():
    """Instalar MySQL no servidor"""
    log("Instalando MySQL", yellow)

    if confirm("Deseja que o script gere senha automatica para o mysql?"):
        db_password = create_password(12)
    else:
        db_password = input("Digite a senha root do mysql: ")

    env.db_password = db_password

    sudo(
        "echo mysql-server mysql-server/root_password password {0} | debconf-set-selections".format(
            db_password
        )
    )
    sudo(
        "echo mysql-server mysql-server/root_password_again password {0} | debconf-set-selections".format(
            db_password
        )
    )
    sudo("apt -q -y install mysql-server")
    sudo(
        "apt -y install libmysqlclient-dev"
    )  # nao perguntar senha do mysql pedir senha antes

    log("BANCO DE DADOS - PASSWORD", green)
    print("senha root mysql: {0}".format(db_password))
    resp = input("Após copiar a senha, clique ENTER para continuar!!!")


def git_server():
    """Instalar git no servidor"""
    log("Instalando git", yellow)
    sudo("apt -y install git")


def others_server():
    """Instalar nginx e supervisor"""
    log("Instalando nginx e supervisor", yellow)
    sudo("apt -y install nginx supervisor")
    sudo("apt -y install mercurial")
    try:
        sudo("apt -y install ruby rubygems")
    except:
        log("PACOTE DO RUBY GEMS FOI REMOVIDO DO PACKAGES DO UBUNTU", red)

    # ubuntu 12
    # sudo('apt -y install php5-fpm php5-suhosin php-apc php5-gd php5-imagick php5-curl')

    # ubuntu 14
    # sudo('apt -y install php5-fpm php-apc php5-mysql php5-gd php5-imagick php5-curl php5-cli')

    # ubuntu 17
    # sudo('apt -y install php7.0-fpm php7.0-apc php7.0-mysql php7.0-gd php7.0-imagick php7.0-curl php7.0-cli')
    # sudo('apt -y install proftpd') # standalone nao perguntar

    # ubuntu 20.04
    sudo("add-apt-repository universe")
    sudo(
        "apt -y install php7.4-fpm php7.4-apcu php7.4-mysql php7.4-gd php7.4-imagick php7.4-curl php7.4-cli"
    )
    sudo("apt -y install proftpd")  # standalone nao perguntar

    # ubuntu 14
    sudo("apt install ruby-dev")
    sudo("gem install compass")


def login():
    """Acessa o servidor"""
    if key_pem:
        local("ssh %s -i %s" % (prod_server, env.key_filename))
    else:
        local("ssh %s" % prod_server)


def upload_public_key():
    """Faz o upload da chave ssh para o servidor"""
    log("Adicionando chave publica no servidor", green)
    ssh_file = "~/.ssh/id_rsa.pub"
    target_path = "~/.ssh/uploaded_key.pub"
    put(ssh_file, target_path)
    run(
        "echo `cat ~/.ssh/uploaded_key.pub` >> ~/.ssh/authorized_keys && rm -f ~/.ssh/uploaded_key.pub"
    )


# RESTART
def restart():
    """Reiniciar servicos no servidor"""
    log("reiniciando servicos", yellow)
    nginx_stop()
    nginx_start()
    nginx_restart()
    nginx_reload()
    supervisor_stop()
    supervisor_start()


def reboot():
    """Reinicia o servidor"""
    log("reiniciando servidor", yellow)
    sudo("reboot")


def proftpd_restart():
    """restart proftpd"""
    log("restart proftpd", yellow)
    sudo("/etc/init.d/proftpd restart")


# SUPERVISOR APP
def start_server():
    """Start aplicação no servidor"""
    conta = input("Digite o nome da app: ")
    log("inicia aplicação", green)
    sudo("supervisorctl start %s" % conta)


def stop_server():
    """Stop aplicação no servidor"""
    conta = input("Digite o nome da app: ")
    log("para aplicação", red)
    sudo("supervisorctl stop %s" % conta)


def restart_server():
    """Restart aplicação no servidor"""
    conta = input("Digite o nome da app: ")
    log("reinicia aplicação", yellow)
    sudo("supervisorctl restart %s" % conta)


# SUPERVISOR
def supervisor_start():
    """Start supervisor no servidor"""
    log("start supervisor", green)
    sudo("/etc/init.d/supervisor start")


def supervisor_stop():
    """Stop supervisor no servidor"""
    log("stop supervisor", red)
    sudo("/etc/init.d/supervisor stop")


def supervisor_restart():
    """Restart supervisor no servidor"""
    log("restart supervisor", yellow)
    sudo("/etc/init.d/supervisor stop")
    sudo("/etc/init.d/supervisor start")
    # sudo('/etc/init.d/supervisor restart')


# NGINX
def nginx_start():
    """Start nginx no servidor"""
    log("start nginx", green)
    sudo("/etc/init.d/nginx start")


def nginx_stop():
    """Stop nginx no servidor"""
    log("stop nginx", red)
    sudo("/etc/init.d/nginx stop")


def nginx_restart():
    """Restart nginx no servidor"""
    log("restart nginx", yellow)
    sudo("/etc/init.d/nginx restart")


def nginx_reload():
    """Reload nginx no servidor"""
    log("reload nginx", yellow)
    sudo("/etc/init.d/nginx reload")


def mysql_restart():
    """Restart mysql no servidor"""
    log("restart mysql", yellow)
    sudo("/etc/init.d/mysql restart")


def mysql_start():
    """start mysql no servidor"""
    log("start mysql", green)
    sudo("/etc/init.d/mysql start")


def mysql_stop():
    """stop mysql no servidor"""
    log("stop mysql", red)
    sudo("/etc/init.d/mysql stop")


# --------------------------------------------------------
# LOCAL
# --------------------------------------------------------

# cria projeto local
def newproject():
    """ Criar novo projeto local """
    log("Criando novo projeto", yellow)
    log(
        "Cria a conta no bitbucket com o nome do projeto vázio que o script se encarregará do resto",
        red,
    )

    conta = input("Digite o nome do projeto: ")

    local('echo "clonando projeto %s"' % git_default_project)
    local(
        "git clone {0} {1}{2}".format(git_default_project, folder_project_local, conta)
    )
    local("cd {0}{1}".format(folder_project_local, conta))
    local("mkvirtualenv {0}".format(conta))
    local("setvirtualenvproject")
    local("pip install -r requirements.txt")
    local("rm -rf {0}{1}/.git".format(folder_project_local, conta))
    local("rm -rf README.md")
    local("git init")
    local(
        "git remote add origin git@bitbucket.org:{0}/{1}.git".format(
            git_user, conta
        )
    )


# configura uma maquina local ubuntu
def newdev():
    """Configura uma maquina local Ubuntu para trabalhar python/django"""
    log("Configura uma computador Ubuntu para trabalhar python/django", yellow)
    update_local()
    upgrade_local()

    # pacotes
    build_local()
    python_local()
    mysql_local()
    git_local()

    # atualizando
    update_local()
    upgrade_local()


# update no local
def update_local():
    """Atualizando pacotes"""
    log("Atualizando pacotes", yellow)
    local("sudo apt update")


# upgrade no local
def upgrade_local():
    """Atualizando programas"""
    log("Atualizando programas", yellow)
    local("sudo apt upgrade")


def build_local():
    """Instalar build-essential"""
    log("instalando build-essential gcc++", yellow)
    local("sudo apt -y install build-essential automake")
    local("sudo apt -y install libxml2-dev libxslt-dev")
    local(
        "sudo apt -y install libjpeg-dev libjpeg8-dev zlib1g-dev libfreetype6 libfreetype6-dev"
    )
    local("sudo apt -y install terminator")


def python_local():
    """Instalando todos pacotes necessários"""
    log("Instalando todos pacotes necessários", yellow)
    local(
        "sudo apt -y install python python-dev python-setuptools python-mysqldb python-pip python-virtualenv"
    )
    local("sudo pip install -U distribute")
    local("sudo pip install virtualenvwrapper")
    local("sudo apt install python-imaging")
    # local('cp ~/.bashrc ~/.bashrc_bkp')
    # local('cat ~/.bashrc inc/bashrc > ~/.bashrc')
    # local('source ~/.bashrc')


def mysql_local():
    """Instalando MySQL"""
    log("Instalando MySQL", yellow)
    local("sudo apt -y install mysql-server libmysqlclient-dev")


def git_local():
    """Instalando git"""
    log("Instalando git", yellow)
    local("sudo apt -y install git")


# --------------------------------------------------------
# GLOBAL
# --------------------------------------------------------

# gera senha
def create_password(tamanho=12):
    """Gera uma senha - parametro tamanho"""
    from random import choice

    caracters = "0123456789abcdefghijlmnopqrstuwvxzkABCDEFGHIJLMNOPQRSTUWVXZK_#"
    senha = ""
    for char in range(tamanho):
        senha += choice(caracters)
    return senha


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
