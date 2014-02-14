# -*- coding: utf-8 -*-
from fabric.api import *

username = '__USER__'
host = '192.168.0.1'
repositorio = 'git@bitbucket.org:__CONTA__/__REPOSITORIO__.git'

# -----------------------------------------------------------------------
prod_server = '%s@%s' % (username, host)
env.project_path = '/home/%s/project/' % username
env.env_path = '/home/%s/env/bin/activate' % username
env.hosts = [prod_server]

def config():
    log('COPIAR CÓDIGO GERADO E COLOCAR NAS CHAVES DE IMPLANTAÇÃO DO PROJETO')
    run('ssh-keygen && cat ~/.ssh/id_rsa.pub')
    resp = raw_input('Após copiar a chave e adicionar as chaves no repositório, clique ENTER para continuar!!!')
    run('git clone %s project' % repositorio)
    with prefix('source {0}'.format(env.env_path)):
        run('pip install -U distribute')
        run('pip install -r project/requirements.txt')
        run('python project/manage.py syncdb')
        run('python project/manage.py migrate')
        run('python project/manage.py collectstatic --noinput')
    log('RODAR OS DOIS COMANDOS NO SERVIDOR PARA TESTAR SE TEM ALGUM ERRO NO PROJETO! \npython project/manage.py runserver 8060 \npython project/manage.py run_gunicorn')
    login()
    log('Executar agora o comando: fab deploy servidor2 restart')

def deploy():
    """faz o deploy da aplicação no servidor"""
    log('Iniciando deploy da aplicação')
    # test()
    pull()
    push()
    remote_pull()
    # compass_compile()
    # compress()
    collectstatic()
    remote_migrate_all()
    # remote_test()
    restart()

def server():
    """inicia o servidor de desenvolvimento local"""
    log('Iniciando servidor de desenvolvimento do Django')
    local('python manage.py runserver 0.0.0.0:8000')

def restart():
    """reiniciando aplicacao"""
    log('reiniciando aplicação')
    run('supervisorctl stop %s' % username)
    run('supervisorctl start %s' % username)

def gunicorn():
    """inicia o servidor de desenvolvimento local usando gunicorn"""
    log('Iniciando servidor de desenvolvimento do Django com gunicorn')
    local('gunicorn app.wsgi:application -w 10 -b 0.0.0.0:8000')

def co():
    """commit local"""
    local('git commit -a')

def commit_all():
    """commit local"""
    local('git add .')
    local('git commit -a')

def commit_all():
    """commit local"""
    local('git add .')
    local('git commit -a')

def push():
    """git push local"""
    log("Enviando alterações")
    local('git push origin master')

def pull():
    """git pull local"""
    log("Atualizando cópia local")
    local('git pull origin master')


def commit_push(message=None):
    """commit e push local"""
    if message:
        co(message=message)
        pull()
        push()

def remote_pull():
    """git pull remoto"""
    log('Atualizando aplicação no servidor')
    with cd(env.project_path):
        run('git pull origin master')

def cw():
    """inicia o compass local no modo watch"""
    local('compass watch config/static')

def compass_compile():
    """compila o compassa remoto"""
    log('Compilando arquivos SASS')
    with cd(env.project_path):
        run('compass compile -e production config/static')

def manage(cmd=None):
    """executa comandos no manage.py remoto"""
    if cmd:
        run('source %s; python manage.py %s' % (env.env_path, cmd))

def collectstatic():
    """collectstatic remoto"""
    log('Coletando arquivos estáticos')
    with cd(env.project_path):
        manage('collectstatic --noinput --ignore scss --ignore *.rb')

def remote_migrate_all():
    """migrate remoto"""
    log('Executando migração remota do banco de dados')
    with cd(env.project_path):
        manage('migrate')

def test():
    """test remoto"""
    log('Executando teste')
    local('python manage.py test')

def remote_test():
    """test remoto"""
    log('Executando teste remoto')
    with cd(env.project_path):
        manage('test')

def test():
    """test local"""
    log('Executando teste')
    local('python manage.py test')

def migrate():
    """migrate local"""
    log('Executando migração do banco de dados')
    local('python manage.py migrate')

def compress():
    """compress remoto"""
    log('Compactando arquivos JavaScript e CSS')
    with cd(env.project_path):
        manage('compress')

def createsuperuser():
    """createsuperuser remoto"""
    log('Criando novo usuário no admin')
    with cd(env.project_path):
        manage('createsuperuser')

def createdb():
    """ CREATE DATABASE """
    log('Criando novo banco')
    local("echo CREATE DATABASE {0} | mysql -u root -p".format(username))

def revert():
    """ Revert git via reset --hard @{1} """
    log('Revertendo aplicação para o ultimo commit')
    with cd(env.project_path):
        run('git reset --hard @{1}')

def update_requirements():
    """instala as dependencias no servidor"""
    pull()
    push()
    remote_pull()
    with cd(env.project_path):
        run('source %s; pip install -r requirements.txt' % env.env_path )

def translate():
    "atualiza os arquivos de tradução e compila"
    log('Atualizando traduções en, es')
    local('django-admin.py makemessages --locale=en --ignore=templates/admin --ignore=config/settings.py')
    local('django-admin.py compilemessages')

def translate_remote():
    "compila tradução no servidor"
    log('compilando tradução no servidor')
    with cd(env.project_path):
        run('source %s; django-admin.py compilemessages')

def upload_public_key():
    """faz o upload da chave ssh para o servidor"""
    log('Adicionando chave publica no servidor')
    ssh_file = '~/.ssh/id_rsa.pub'
    target_path = '~/.ssh/uploaded_key.pub'
    put(ssh_file, target_path)
    run('echo `cat ~/.ssh/uploaded_key.pub` >> ~/.ssh/authorized_keys && rm -f ~/.ssh/uploaded_key.pub')

def login():
    local("ssh %s" % prod_server)

def log(message):
    print """
==============================================================
%s
==============================================================
    """ % message
