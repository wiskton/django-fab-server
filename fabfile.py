# -*- coding: utf-8 -*-
from fabric.api import *


# --------------------------------------------------------
# ALTERAR CONFIGURAÇÕES BASEADAS NO SEUS SERVIDOR
# --------------------------------------------------------

username = 'root'
ip = '192.168.1.111'
prod_server = '{0}@{1}'.format(username, ip)
project_path = '/home/'
# env_path = '/home/'

env.hosts = [prod_server]

# FALTA NGINX E SUPERVISOR PARA CADA USUARIO AUTOMATICO - CRIAR SCRIPT

# --------------------------------------------------------
# SERVIDOR
# --------------------------------------------------------

def newserver():
    """Configurar e instalar todos pacotes necessários para servidor"""
    log('Configurar e instalar todos pacotes necessários para servidor')
    update_server()
    upgrade_server()

    # pacotes
    build_server()
    python_server()
    mysql_server()
    git_server()
    outros_server()

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

# cria uma conta no servidor
def novaconta():
    """Criar uma nova conta do usuário no servidor"""
    log('Criar uma nova conta do usuário no servidor')

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
    # run("sed 's/willemallan/{0}/' /home/{0}/supervisor.conf > /home/{0}/supervisor.conf".format(conta))
    # run("sed 's/willemallan/{0}/' /home/{0}/nginx.conf > /home/{0}/nginx.conf".format(conta))
 
    # cria banco e usuario no banco
    banco_senha = gera_senha(12)
    newbase(conta, banco_senha)

    # da permissao para o usuario no diretorio
    run('sudo chown -R {0}:{0} /home/{0}'.format(conta))

    # log para salvar no docs
    log('Anotar dados da conta: {0}'.format(conta))
    print 'USUÁRIO senha: {0}'.format(user_senha)
    print 'BANCO senha: {0}'.format(banco_senha)


# deleta uma conta no servidor
def delconta():
    """Deletar conta no servidor"""
    conta = raw_input('Digite o nome da conta: ')
    log('Deletando conta {0}'.format(conta))
    userdel(conta)
    dropbase(conta)


# cria usuario no servidor
def adduser(conta=None, user_senha=None):
    """Criar um usuário no servidor"""

    if not user_senha:
        user_senha = gera_senha(12)
    print 'senha usuário: {0}'.format(user_senha)

    if not conta:
        conta = raw_input('Digite o nome do usuário: ')

    log('Criando usuário {0}'.format(conta))
    run('sudo adduser {0}'.format(conta))


# MYSQL - cria usuario e banco de dados
def newbase(conta=None, banco_senha=None):
    """Criar banco de dados e usuário no servidor"""

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
    """Deletar banco de dados no servidor"""
    if not conta:
        conta = raw_input('Digite o nome do banco: ')
    run("echo DROP DATABASE {0} | mysql -u root -p".format(conta))
    run("echo \"DROP USER '{0}'@'localhost'\" | mysql -u root -p".format(conta))


# LINUX - deleta o usuario
def userdel(conta=None):
    """Deletar usuário no servidor"""
    if not conta:
        conta = raw_input('Digite o nome do usuario: ')
    log('Deletando usuário {0}'.format(conta))
    run('sudo userdel -r {0}'.format(conta))


# update no servidor
def update_server():
    """Atualizando pacotes no servidor"""
    log('Atualizando pacotes')
    run('sudo apt-get update')

# upgrade no servidor
def upgrade_server():
    """Atualizar programas no servidor"""
    log('Atualizando programas')
    run('sudo apt-get upgrade')


def build_server():
    """Instalar build-essential e outros pacotes importantes no servidor"""
    log('Instalando build-essential e outros pacotes')
    run('sudo apt-get install build-essential automake')
    run('sudo apt-get install libxml2-dev libxslt-dev')
    run('sudo apt-get install libjpeg-dev libjpeg8-dev zlib1g-dev libfreetype6 libfreetype6-dev')


def python_server():
    """Instalar todos pacotes necessários do python no servidor"""
    log('Instalando todos pacotes necessários')
    run('sudo apt-get install python python-dev python-setuptools python-mysqldb python-pip python-virtualenv')
    run('pip install -U distribute')


def mysql_server():
    """Instalar MySQL no servidor"""
    log('Instalando MySQL')
    run('sudo apt-get install mysql-server libmysqlclient-dev')


def git_server():
    """Instalar git no servidor"""
    log('Instalando git')
    run('sudo apt-get install git')

def outros_server():
    """Instalar nginx e supervisor"""
    log('Instalando nginx e supervisor')
    run('sudo apt-get install nginx supervisor')


def login():
    """Acessa o servidor"""
    local("ssh %s" % prod_server)


def upload_public_key():
    """Faz o upload da chave ssh para o servidor"""
    log('Adicionando chave publica no servidor')
    ssh_file = '~/.ssh/id_rsa.pub'
    target_path = '~/.ssh/uploaded_key.pub'
    put(ssh_file, target_path)
    run('echo `cat ~/.ssh/uploaded_key.pub` >> ~/.ssh/authorized_keys && rm -f ~/.ssh/uploaded_key.pub')


# RESTART
def restart():
    """Reiniciar servicos no servidor"""
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
    """Start aplicação no servidor"""
    conta = raw_input('Digite o nome da app: ')
    log('inicia aplicação')
    run('sudo supervisorctl start %s' % conta)


def stop_server():
    """Stop aplicação no servidor"""
    conta = raw_input('Digite o nome da app: ')
    log('para aplicação')
    run('sudo supervisorctl stop %s' % conta)


def restart_server():
    """Restart aplicação no servidor"""
    conta = raw_input('Digite o nome da app: ')
    log('reinicia aplicação')
    run('sudo supervisorctl restart %s' % conta)


# SUPERVISOR
def supervisor_start():
    """Start supervisor no servidor"""
    log('start supervisor')
    run('sudo /etc/init.d/supervisor start')


def supervisor_stop():
    """Stop supervisor no servidor"""
    log('stop supervisor')
    run('sudo /etc/init.d/supervisor stop')


def supervisor_restart():
    """Restart supervisor no servidor"""
    log('restart supervisor')
    run('sudo /etc/init.d/supervisor restart')


# NGINX
def nginx_start():
    """Start nginx no servidor"""
    log('start nginx')
    run('sudo /etc/init.d/nginx start')


def nginx_stop():
    """Stop nginx no servidor"""
    log('stop nginx')
    run('sudo /etc/init.d/nginx stop')


def nginx_restart():
    """Restart nginx no servidor"""
    log('restart nginx')
    run('sudo /etc/init.d/nginx restart')


def nginx_reload():
    """Reload nginx no servidor"""
    log('reload nginx')
    run('sudo /etc/init.d/nginx reload')


# --------------------------------------------------------
# LOCAL
# --------------------------------------------------------

# cria projeto local
def newproject():
    """ Criar novo projeto local """
    log('Criando novo projeto local')

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
    """Instalar build-essential"""
    log('instalando build-essential gcc++')
    local('sudo apt-get install build-essential automake')
    local('sudo apt-get install libxml2-dev libxslt-dev')
    local('sudo apt-get install libjpeg-dev libjpeg8-dev zlib1g-dev libfreetype6 libfreetype6-dev')


def python_local():
    """Instalando todos pacotes necessários"""
    log('Instalando todos pacotes necessários')
    local('sudo apt-get install python python-dev python-setuptools python-mysqldb python-pip python-virtualenv')
    local('pip install -U distribute')
    local('pip install virtualenvwrapper')
    # local('cat ~/.bashrc inc/bashrc > ~/.bashrc')
    # local('source ~/.bashrc')

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
