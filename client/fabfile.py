# -*- coding: utf-8 -*-
import functools
from contextlib import contextmanager

from fabric import Connection, task

username = "__USER__"
host = "192.168.0.1"
repositorio = "git@bitbucket.org:__CONTA__/__REPOSITORIO__.git"

# -----------------------------------------------------------------------
prod_server = "%s@%s" % (username, host)
project_path = "/home/%s/project/" % username
env_path = "/home/%s/env/bin/activate" % username


@functools.lru_cache(maxsize=1)
def get_connection():
    """Cria (uma única vez por execução) a conexão SSH com o servidor configurado."""
    return Connection(host=host, user=username)


@contextmanager
def remote_project():
    """Conexão já posicionada dentro do diretório do projeto no servidor."""
    conn = get_connection()
    with conn.cd(project_path):
        yield conn


def log(message):
    print(
        """
==============================================================
%s
==============================================================
    """
        % message
    )


@task
def config(c):
    """configura o servidor pela primeira vez"""
    log("COPIAR CÓDIGO GERADO E COLOCAR NAS CHAVES DE IMPLANTAÇÃO DO PROJETO")
    conn = get_connection()
    conn.run("ssh-keygen && cat ~/.ssh/id_rsa.pub")
    input(
        "Após copiar a chave e adicionar as chaves no repositório, clique ENTER para continuar!!!"
    )
    conn.run("git clone %s project" % repositorio)
    with conn.prefix("source {0}".format(env_path)):
        conn.run("pip install -U pip")
        conn.run("pip install -r project/requirements.txt")
        conn.run("python project/manage.py migrate")
        conn.run("python project/manage.py collectstatic --noinput")
    log(
        "RODAR OS DOIS COMANDOS NO SERVIDOR PARA TESTAR SE TEM ALGUM ERRO NO PROJETO! \npython project/manage.py runserver 8060 \ngunicorn {0}.wsgi:application".format(
            username
        )
    )
    login(c)
    log("Executar agora o comando: fab deploy")


@task
def deploy(c):
    """faz o deploy da aplicação no servidor"""
    log("Iniciando deploy da aplicação")
    pull(c)
    push(c)
    remote_pull(c)
    collectstatic(c)
    remote_migrate_all(c)
    restart(c)


@task
def server(c):
    """inicia o servidor de desenvolvimento local"""
    log("Iniciando servidor de desenvolvimento do Django")
    c.run("python manage.py runserver 0.0.0.0:8000")


@task
def restart(c):
    """reiniciando aplicacao"""
    log("reiniciando aplicação")
    conn = get_connection()
    conn.run("supervisorctl stop %s" % username)
    conn.run("supervisorctl start %s" % username)


@task
def gunicorn(c):
    """inicia o servidor de desenvolvimento local usando gunicorn"""
    log("Iniciando servidor de desenvolvimento do Django com gunicorn")
    c.run("gunicorn app.wsgi:application -w 10 -b 0.0.0.0:8000")


@task
def co(c):
    """commit local"""
    c.run("git commit -a")


@task
def commit_all(c):
    """commit local"""
    c.run("git add .")
    c.run("git commit -a")


@task
def push(c):
    """git push local"""
    log("Enviando alterações")
    c.run("git push origin master")


@task
def pull(c):
    """git pull local"""
    log("Atualizando cópia local")
    c.run("git pull origin master")


@task
def commit_push(c, message=None):
    """commit e push local"""
    if message:
        co(c)
        pull(c)
        push(c)


@task
def remote_pull(c):
    """git pull remoto"""
    log("Atualizando aplicação no servidor")
    with remote_project() as conn:
        conn.run("git pull origin master")


@task
def cw(c):
    """inicia o compass local no modo watch"""
    c.run("compass watch config/static")


@task
def compass_compile(c):
    """compila o compass remoto"""
    log("Compilando arquivos SASS")
    with remote_project() as conn:
        conn.run("compass compile -e production config/static")


@task
def manage(c, cmd=None):
    """executa comandos no manage.py remoto"""
    if cmd:
        conn = get_connection()
        conn.run("source {0}; python manage.py {1}".format(env_path, cmd))


@task
def collectstatic(c):
    """collectstatic remoto"""
    log("Coletando arquivos estáticos")
    with remote_project():
        manage(c, "collectstatic --noinput --ignore scss --ignore *.rb")


@task
def remote_migrate_all(c):
    """migrate remoto"""
    log("Executando migração remota do banco de dados")
    with remote_project():
        manage(c, "migrate")


@task
def test(c):
    """test local"""
    log("Executando teste")
    c.run("python manage.py test")


@task
def remote_test(c):
    """test remoto"""
    log("Executando teste remoto")
    with remote_project():
        manage(c, "test")


@task
def migrate(c):
    """migrate local"""
    log("Executando migração do banco de dados")
    c.run("python manage.py migrate")


@task
def compress(c):
    """compress remoto"""
    log("Compactando arquivos JavaScript e CSS")
    with remote_project():
        manage(c, "compress")


@task
def createsuperuser(c):
    """createsuperuser remoto"""
    log("Criando novo usuário no admin")
    with remote_project():
        manage(c, "createsuperuser")


@task
def createdb(c):
    """CREATE DATABASE"""
    log("Criando novo banco")
    c.run('mysql -u root -p --execute="CREATE DATABASE {0}"'.format(username))


@task
def revert(c):
    """Revert git via reset --hard @{1}"""
    log("Revertendo aplicação para o ultimo commit")
    with remote_project() as conn:
        conn.run("git reset --hard @{1}")


@task
def update_requirements(c):
    """instala as dependencias no servidor"""
    pull(c)
    push(c)
    remote_pull(c)
    with remote_project() as conn:
        conn.run("source {0}; pip install -r requirements.txt".format(env_path))


@task
def translate(c):
    """atualiza os arquivos de tradução e compila"""
    log("Atualizando traduções en, es")
    c.run(
        "django-admin makemessages --locale=en --ignore=templates/admin --ignore=config/settings.py"
    )
    c.run("django-admin compilemessages")


@task
def translate_remote(c):
    """compila tradução no servidor"""
    log("compilando tradução no servidor")
    with remote_project() as conn:
        conn.run("source {0}; django-admin compilemessages".format(env_path))


@task
def upload_public_key(c):
    """faz o upload da chave ssh para o servidor"""
    log("Adicionando chave publica no servidor")
    conn = get_connection()
    ssh_file = "~/.ssh/id_rsa.pub"
    target_path = "~/.ssh/uploaded_key.pub"
    conn.put(ssh_file, target_path)
    conn.run(
        "echo `cat ~/.ssh/uploaded_key.pub` >> ~/.ssh/authorized_keys && rm -f ~/.ssh/uploaded_key.pub"
    )


@task
def login(c):
    """acessa o servidor"""
    c.run("ssh %s" % prod_server)
