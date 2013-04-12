# -*- coding: utf-8 -*-
from fabric.api import *


# --------------------------------------------------------
# ALTERAR CONFIGURAÇÕES BASEADAS NO SEUS SERVIDOR
# --------------------------------------------------------

username = 'root'
ip = '127.0.0.1'
prod_server = '{0}@{1}'.format(username, ip)
project_path = '/home/'


# --------------------------------------------------------
# SERVIDOR
# --------------------------------------------------------

def newserver():
    """Configurando e instalando todos pacotes necessários para servidor"""
    log('Configurando e instalando todos pacotes necessários para servidor')
    update_server()
    upgrade_server()

    # pacotes
    build_server()
    python_server()
    mysql_server()
    git_server()
    server_server()

    # atualizando
    update_server()
    upgrade_server()

    # altera o arquivo nginx.conf
    run('mv /etc/nginx/nginx.conf /etc/nginx/nginx_backup.conf')
    local('scp inc/nginx_server.conf {0}:/etc/nginx'.format(prod_server))
    run('mv /etc/nginx/nginx_server.conf /etc/nginx/nginx.conf')
    nginx_restart()

    # altera o arquivo supervisor.conf
    run('mv /etc/supervisor/supervisord.conf /etc/supervisor/supervisord_backup.conf')
    local('scp inc/supervisord_server.conf {0}:/etc/supervisor/'.format(prod_server))
    run('mv /etc/supervisor/supervisord_server.conf /etc/supervisor/supervisord.conf')
    supervisor_restart()


# cria projeto local
def newproject():
    """ Criando novo projeto """
    log('Criando novo projeto')

    conta = raw_input('Digite o nome do projeto: ')

    local('echo "clonando projeto padrão do bitbucket - django 1.4"')
    local('git clone git@github.com:willemallan/django14.git ~/projetos/{0}'.format(conta))
    local('cd ~/projetos/{0}/app'.format(conta))
    local('mkvirtualenv {0}'.format(conta))
    local('setvirtualenvproject')
    local('pip install -r ../requirements.txt')
    local('rm -rf ~/projetos/{0}/.git'.format(conta))
    local('rm -rf README.md')
    local('git init')
    local('git remote add origin ssh://git@bitbucket.org/willemarf/{0}.git'.format(conta))

# cria uma conta no servidor
def novaconta():
    """Criando uma nova conta do usuário"""
    log('Criando uma nova conta do usuário')

    # criando usuario
    conta = raw_input('Digite o nome da conta: ')

    # cria usuario no linux
    user_senha = gera_senha(12)
    adduser(conta, user_senha)

    run('mkdir /home/{0}/logs'.format(conta))
    run('touch /home/{0}/logs/access.log'.format(conta))
    run('touch /home/{0}/logs/error.log'.format(conta))
    run('virtualenv /home/{0}/env --no-site-packages'.format(conta))
    local('scp inc/nginx.conf {0}:/home/{1}'.format(prod_server, conta))
    local('scp inc/supervisor.conf {0}:/home/{1}'.format(prod_server, conta))

    # cria banco e usuario no banco
    banco_senha = gera_senha(12)
    newbase(conta, banco_senha)

    # da permissao para o usuario no diretorio
    run('sudo chown -R {0}:{0} /home/{0}'.format(conta))

    # log para salvar no docs
    log('Anotar dados da conta: {0}'.format(conta))
    print 'USUÁRIO senha: {0}'.format(user_senha)
    print 'BANCO senha: {0}'.format(banco_senha)

# cria usuario no servidor
def adduser(conta=None, user_senha=None):
    """Criando usuário"""

    if not user_senha:
        user_senha = gera_senha(12)
    print 'senha usuário: {0}'.format(user_senha)

    if not conta:
        conta = raw_input('Digite o nome do banco: ')

    log('Criando usuário {0}'.format(conta))
    run('sudo adduser {0}'.format(conta))


# deleta uma conta no servidor
def delconta():
    """Deletando conta"""
    conta = raw_input('Digite o nome da conta: ')
    log('Deletando conta {0}'.format(conta))
    userdel(conta)
    dropbase(conta)


# MYSQL - cria usuario e banco de dados
def newbase(conta=None, banco_senha=None):
    """NEW DATABASE"""

    if not banco_senha:
        banco_senha = gera_senha(12)
    print 'Senha gerada para o banco: {0}'.format(banco_senha)

    if not conta:
        conta = raw_input('Digite o nome do banco: ')
    log('NEW DATABASE {0}'.format(conta))

    run("echo CREATE DATABASE {0} | mysql -u root -p".format(conta))
    run("echo \"CREATE USER '{0}'@'localhost' IDENTIFIED BY '{1}'\" | mysql -u root -p".format(conta, banco_senha))
    run("echo \"GRANT ALL PRIVILEGES ON {0} . * TO '{0}'@'localhost'\" | mysql -u root -p".format(conta))


# MYSQL - deleta o usuario e o banco de dados
def dropbase(conta=None):
    """DROP DATABASE"""
    if not conta:
        conta = raw_input('Digite o nome do banco: ')
    run("echo DROP DATABASE {0} | mysql -u root -p".format(conta))
    run("echo \"DROP USER '{0}'@'localhost'\" | mysql -u root -p".format(conta))

# LINUX - deleta o usuario
def userdel(conta=None):
    """Deletando usuário"""
    if not conta:
        conta = raw_input('Digite o nome do usuario: ')
    log('Deletando usuário {0}'.format(conta))
    run('sudo userdel -r {0}'.format(conta))


# update no servidor
def update_server():
    """Atualizando pacotes"""
    log('Atualizando pacotes')
    run('sudo apt-get update')

# upgrade no servidor
def upgrade_server():
    """Atualizando programas"""
    log('Atualizando programas')
    run('sudo apt-get upgrade')


def build_server():
    """Instalando build-essential"""
    log('instalando build-essential gcc++')
    run('sudo apt-get install build-essential automake')
    run('sudo apt-get install libxml2-dev libxslt-dev')
    run('sudo apt-get install libjpeg-dev libjpeg8-dev zlib1g-dev libfreetype6 libfreetype6-dev')


def python_server():
    """Instalando todos pacotes necessários"""
    log('Instalando todos pacotes necessários')
    run('sudo apt-get install python python-dev python-setuptools python-mysqldb python-pip python-virtualenv')
    run('pip install -U distribute')


def mysql_server():
    """Instalando MySQL"""
    log('Instalando MySQL')
    run('sudo apt-get install mysql-server libmysqlclient-dev')


def git_server():
    """Instalando git"""
    log('Instalando git')
    run('sudo apt-get install git')

def outros_server():
    """Instalando nginx e supervisor"""
    log('Instalando nginx e supervisor')
    run('sudo apt-get install nginx supervisor')


def login():
    """Acessa o servidor"""
    local("ssh %s" % prod_server)


def upload_public_key():
    """faz o upload da chave ssh para o servidor"""
    log('Adicionando chave publica no servidor')
    ssh_file = '~/.ssh/id_rsa.pub'
    target_path = '~/.ssh/uploaded_key.pub'
    put(ssh_file, target_path)
    run('echo `cat ~/.ssh/uploaded_key.pub` >> ~/.ssh/authorized_keys && rm -f ~/.ssh/uploaded_key.pub')


# RESTART
def restart():
    """reiniciando servicos"""
    log('reiniciando servicos')
    nginx_stop()
    nginx_start()
    nginx_restart()
    nginx_reload()
    supervisor_stop()
    supervisor_start()
    supervisor_restart()


# SUPERVISOR APP
def start_server():
    """inicia aplicação"""
    conta = raw_input('Digite o nome da app: ')
    log('inicia aplicação')
    run('sudo supervisorctl start %s' % conta)


def stop_server():
    """para aplicação"""
    conta = raw_input('Digite o nome da app: ')
    log('para aplicação')
    run('sudo supervisorctl stop %s' % conta)


def restart_server():
    """reinicia aplicação"""
    conta = raw_input('Digite o nome da app: ')
    log('reinicia aplicação')
    run('sudo supervisorctl restart %s' % conta)


# SUPERVISOR
def supervisor_start():
    """start supervisor"""
    log('start supervisor')
    run('sudo /etc/init.d/supervisor start')


def supervisor_stop():
    """stop supervisor"""
    log('stop supervisor')
    run('sudo /etc/init.d/supervisor stop')


def supervisor_restart():
    """restart supervisor"""
    log('restart supervisor')
    run('sudo /etc/init.d/supervisor restart')


# NGINX
def nginx_start():
    """start NGINX"""
    log('start NGINX')
    run('sudo /etc/init.d/nginx start')


def nginx_stop():
    """stop NGINX"""
    log('stop NGINX')
    run('sudo /etc/init.d/nginx stop')


def nginx_restart():
    """restart NGINX"""
    log('restart NGINX')
    run('sudo /etc/init.d/nginx restart')


def nginx_reload():
    """reload NGINX"""
    log('reload NGINX')
    run('sudo /etc/init.d/nginx reload')


# --------------------------------------------------------
# LOCAL
# --------------------------------------------------------

# configura uma maquina local ubuntu
def newdev():
    """Configura uma maquina local Ubuntu para trabalhar python/django"""
    log('Configura uma computador Ubuntu para trabalhar python/django')
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
    log('Atualizando pacotes')
    local('sudo apt-get update')

# upgrade no local
def upgrade_local():
    """Atualizando programas"""
    log('Atualizando programas')
    local('sudo apt-get upgrade')


def build_local():
    """Instalando build-essential"""
    log('instalando build-essential gcc++')
    local('sudo apt-get install build-essential automake')
    local('sudo apt-get install libxml2-dev libxslt-dev')
    local('sudo apt-get install libjpeg-dev libjpeg8-dev zlib1g-dev libfreetype6 libfreetype6-dev')


def python_local():
    """Instalando todos pacotes necessários"""
    log('Instalando todos pacotes necessários')
    local('sudo apt-get install python python-dev python-setuptools python-mysqldb python-pip python-virtualenv')
    local('pip install -U distribute')


def mysql_local():
    """Instalando MySQL"""
    log('Instalando MySQL')
    local('sudo apt-get install mysql-server libmysqlclient-dev')


def git_local():
    """Instalando git"""
    log('Instalando git')
    local('sudo apt-get install git')


# --------------------------------------------------------
# GLOBAL
# --------------------------------------------------------

# gera senha
def gera_senha(tamanho=12):
    """Gera uma senha - parametro tamanho"""
    from random import choice
    caracters = '0123456789abcdefghijlmnopqrstuwvxzkABCDEFGHIJLMNOPQRSTUWVXZK_#'
    senha = ''
    for char in xrange(tamanho):
        senha += choice(caracters)
    return senha


def log(message):
    print """
==============================================================
%s
==============================================================
    """ % message
