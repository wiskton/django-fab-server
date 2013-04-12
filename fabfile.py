# -*- coding: utf-8 -*-
from fabric.api import *

username = 'root'
ip = ''

prod_server = '{0}@{1}'.format(username, ip)
project_path = '/home/'
env_path = '/home/'

env.hosts = [prod_server]


def newserver():
    """Configurando e instalando todos pacotes necessários para servidor"""
    log('Configurando e instalando todos pacotes necessários para servidor')
    update()
    upgrade()

    # pacotes
    build()
    python()
    mysql()
    outros()

    # atualizando
    update()
    upgrade()

    # altera o arquivo nginx.conf
    run('mv /etc/nginx/nginx.conf /etc/nginx/nginx_backup.conf')
    local('scp nginx_server.conf {0}:/etc/nginx'.format(prod_server))
    run('mv /etc/nginx/nginx_server.conf /etc/nginx/nginx.conf')
    nginx_restart()

    # altera o arquivo supervisor.conf
    run('mv /etc/supervisor/supervisord.conf /etc/supervisor/supervisord_backup.conf')
    local('scp supervisord_server.conf {0}:/etc/supervisor/'.format(prod_server))
    run('mv /etc/supervisor/supervisord_server.conf /etc/supervisor/supervisord.conf')
    supervisor_restart()

def newproject():
    """ Criando novo projeto """
    log('Criando novo projeto')

    conta = raw_input('Digite o nome do projeto: ')

    local('echo "clonando projeto padrão do bitbucket - django 1.4"')
    local('git clone git@bitbucket.org:willemarf/d14padrao.git ~/projetos/{0}'.format(conta))
    local('cd ~/projetos/{0}/app'.format(conta))
    local('mkvirtualenv {0}'.format(conta))
    local('setvirtualenvproject')
    local('pip install -r ../requirements.txt')
    local('rm -rf ~/projetos/{0}/.git'.format(conta))
    local('rm -rf README.md')
    local('git init')
    local('git remote add origin ssh://git@bitbucket.org/willemarf/{0}.git'.format(conta))

def novaconta():
    """Criando uma nova conta do usuário"""
    log('Criando uma nova conta do usuário')

    # criando usuario
    conta = raw_input('Digite o nome da conta: ')
    adduser(conta)

def gera_senha(tamanho):
    """Gera uma senha - parametro tamanho"""
    from random import choice
    caracters = '0123456789abcdefghijlmnopqrstuwvxzkABCDEFGHIJLMNOPQRSTUWVXZK_#'
    senha = ''
    for char in xrange(tamanho):
        senha += choice(caracters)
    return senha


def adduser(conta):
    """Criando usuário"""
    user_senha = gera_senha(12)
    banco_senha = gera_senha(12)
    print 'senha usuário: {0}'.format(user_senha)

    log('Criando usuário {0}'.format(conta))
    with cd(project_path):
        run('sudo adduser {0}'.format(conta))
        run('mkdir /home/{0}/logs'.format(conta))
        run('touch /home/{0}/logs/access.log'.format(conta))
        run('touch /home/{0}/logs/error.log'.format(conta))
        run('virtualenv /home/{0}/env --no-site-packages'.format(conta))
        local('scp nginx.conf {0}:/home/{1}'.format(prod_server, conta))
        local('scp supervisor.conf {0}:/home/{1}'.format(prod_server, conta))

        run("echo CREATE DATABASE {0} | mysql -u root -p".format(conta))
        run("echo \"CREATE USER '{0}'@'localhost' IDENTIFIED BY '{1}'\" | mysql -u root -p".format(conta, banco_senha))
        run("echo \"GRANT ALL PRIVILEGES ON {0} . * TO '{0}'@'localhost'\" | mysql -u root -p".format(conta))

        run('sudo chown -R {0}:{0} /home/{0}'.format(conta))

        log('Anotar dados da conta: {0}'.format(conta))
        print 'USUÁRIO senha: {0}'.format(user_senha)
        print 'BANCO senha: {0}'.format(banco_senha)

def newbase():
    """NEW DATABASE"""
    banco_senha = gera_senha(12)
    conta = raw_input('Digite o nome do banco: ')
    log('NEW DATABASE {0}'.format(conta))

    run("echo CREATE DATABASE {0} | mysql -u root -p".format(conta))
    run("echo \"CREATE USER '{0}'@'localhost' IDENTIFIED BY '{1}'\" | mysql -u root -p".format(conta, banco_senha))
    run("echo \"GRANT ALL PRIVILEGES ON {0} . * TO '{0}'@'localhost'\" | mysql -u root -p".format(conta))

def dropbase():
    """DROP DATABASE"""
    conta = raw_input('Digite o nome do banco: ')
    run("echo DROP DATABASE {0} | mysql -u root -p".format(conta))
    run("echo \"DROP USER '{0}'@'localhost'\" | mysql -u root -p".format(conta))

def userdel(conta):
    """Deletando usuário"""
    log('Deletando usuário {0}'.format(conta))
    with cd(project_path):
        run('sudo userdel -r {0}'.format(conta))

def delconta():
    """Deletando conta"""
    conta = raw_input('Digite o nome da conta: ')
    log('Deletando conta {0}'.format(conta))
    userdel(conta)
    run("echo DROP DATABASE {0} | mysql -u root -p".format(conta))
    run("echo \"DROP USER '{0}'@'localhost'\" | mysql -u root -p".format(conta))

def update():
    """Atualizando pacotes"""
    log('Atualizando pacotes')
    with cd(project_path):
        run('sudo apt-get update')


def upgrade():
    """Atualizando programas"""
    log('Atualizando programas')
    with cd(project_path):
        run('sudo apt-get upgrade')


def build():
    """Instalando build-essential"""
    log('instalando build-essential gcc++')
    with cd(project_path):
        run('sudo apt-get install build-essential automake')
        run('sudo apt-get install libxml2-dev libxslt-dev')
        run('sudo apt-get install libjpeg-dev libjpeg8-dev zlib1g-dev libfreetype6 libfreetype6-dev')

def python():
    """Instalando todos pacotes necessários"""
    log('Instalando todos pacotes necessários')
    with cd(project_path):
        run('sudo apt-get install python python-dev python-setuptools python-mysqldb python-pip python-virtualenv')
        run('pip install -U distribute')


def mysql():
    """Instalando MySQL"""
    log('Instalando MySQL')
    with cd(project_path):
        run('sudo apt-get install mysql-server libmysqlclient-dev')


def outros():
    """Instalando git, nginx e supervisor"""
    log('Instalando git, nginx e supervisor')
    with cd(project_path):
        run('sudo apt-get install git nginx supervisor')


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
    # supervisor_reload()


# SUPERVISOR
def start_server():
    """inicia aplicação"""
    conta = raw_input('Digite o nome da app: ')
    log('inicia aplicação')
    with cd(project_path):
        run('sudo supervisorctl start %s' % conta)

def stop_server():
    """para aplicação"""
    conta = raw_input('Digite o nome da app: ')
    log('para aplicação')
    with cd(project_path):
        run('sudo supervisorctl stop %s' % conta)

def restart_server():
    """reinicia aplicação"""
    conta = raw_input('Digite o nome da app: ')
    log('reinicia aplicação')
    with cd(project_path):
        run('sudo supervisorctl restart %s' % conta)

def supervisor_start():
    """start supervisor"""
    log('start supervisor')
    with cd(project_path):
        run('sudo /etc/init.d/supervisor start')

def supervisor_stop():
    """stop supervisor"""
    log('stop supervisor')
    with cd(project_path):
        run('sudo /etc/init.d/supervisor stop')

def supervisor_restart():
    """restart supervisor"""
    log('restart supervisor')
    with cd(project_path):
        run('sudo /etc/init.d/supervisor restart')

# def supervisor_reload():
#     """reload supervisor"""
#     log('reload supervisor')
#     with cd(project_path):
#         run('sudo /etc/init.d/supervisor reload')


# NGINX 
def nginx_start():
    """start NGINX"""
    log('start NGINX')
    with cd(project_path):
        run('sudo /etc/init.d/nginx start')

def nginx_stop():
    """stop NGINX"""
    log('stop NGINX')
    with cd(project_path):
        run('sudo /etc/init.d/nginx stop')

def nginx_restart():
    """restart NGINX"""
    log('restart NGINX')
    with cd(project_path):
        run('sudo /etc/init.d/nginx restart')

def nginx_reload():
    """reload NGINX"""
    log('reload NGINX')
    with cd(project_path):
        run('sudo /etc/init.d/nginx reload')


def log(message):
    print """
==============================================================
%s
==============================================================
    """ % message