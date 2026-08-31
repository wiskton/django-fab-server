# -*- coding: utf-8 -*-
import functools
from contextlib import contextmanager

from fabric import Connection, task

# Configurações do Servidor e Repositório
# Podem ser preenchidas aqui ou deixadas em branco (o script perguntará interativamente)
username = ""  # nome da conta criada no servidor, ex: "meusite"
host = ""  # IP ou domínio do servidor
repositorio = ""  # URL git do projeto, ex: "git@github.com:usuario/projeto.git"
branch = "main"


def _prompt_if_missing(name, prompt_text):
    """Se a variável global (username/host/repositorio) ainda estiver vazia, pergunta o valor."""
    value = globals()[name]
    while not value:
        value = input(prompt_text).strip()
    globals()[name] = value
    return value


def _ensure_server_config():
    _prompt_if_missing("username", "Nome da conta criada no servidor (ex: meusite): ")
    _prompt_if_missing("host", "IP ou domínio do servidor: ")


def _ensure_repositorio():
    _prompt_if_missing(
        "repositorio",
        "URL git do projeto (ex: git@github.com:usuario/projeto.git): ",
    )


def _prod_server():
    return f"{username}@{host}"


def _project_path():
    return f"/home/{username}/project"


def _env_path():
    return f"/home/{username}/env/bin/activate"


def confirm(question, default=True):
    suffix = "[Y/n]" if default else "[y/N]"
    resp = input(f"{question} {suffix} ").strip().lower()
    if not resp:
        return default
    return resp in ("y", "yes")


@functools.lru_cache(maxsize=1)
def get_connection():
    """Cria (uma única vez por execução) a conexão SSH com o servidor configurado."""
    _ensure_server_config()
    return Connection(host=host, user=username)


@contextmanager
def remote_project():
    """Conexão posicionada dentro do diretório do projeto no servidor."""
    conn = get_connection()
    with conn.cd(_project_path()):
        yield conn


def log(message):
    print(f"\n{'=' * 62}\n{message}\n{'=' * 62}\n")


def _bootstrap_project(conn):
    """Instala dependências, executa migrações, compila traduções e coleta arquivos estáticos."""
    with conn.cd(_project_path()):
        conn.run(f"source {_env_path()} && pip install -U pip")
        conn.run(f"source {_env_path()} && pip install -r requirements.txt")
        conn.run(f"source {_env_path()} && python manage.py migrate --noinput")
        res = conn.run(f"source {_env_path()} && python manage.py compilemessages", warn=True)
        if res.failed:
            log("AVISO: gettext não instalado no servidor. Para instalar, execute: fab install-gettext")
        conn.run(f"source {_env_path()} && python manage.py collectstatic --noinput")


@task
def install_gettext(c):
    """Instala o pacote gettext (msgfmt) no servidor Linux."""
    log("Instalando gettext no servidor")
    conn = get_connection()
    conn.sudo("apt-get update && apt-get install -y gettext", warn=True)


@task
def show_key(c):
    """Exibe ou gera a chave pública SSH do servidor para cadastrar no GitHub."""
    conn = get_connection()
    conn.run("mkdir -p ~/.ssh")
    conn.run("test -f ~/.ssh/id_rsa.pub || ssh-keygen -t rsa -b 4096 -N '' -f ~/.ssh/id_rsa")
    log("CHAVE PÚBLICA SSH DO SERVIDOR (Copie e adicione no GitHub > Deploy Keys):")
    conn.run("cat ~/.ssh/id_rsa.pub")


@task
def config(c):
    """Configura o servidor pela primeira vez (chaves SSH, clone e bootstrap)."""
    conn = get_connection()
    _ensure_repositorio()

    log("1. GERANDO CHAVE SSH E REGISTRANDO GITHUB NO KNOWN_HOSTS")
    conn.run("mkdir -p ~/.ssh")
    conn.run("test -f ~/.ssh/id_rsa.pub || ssh-keygen -t rsa -b 4096 -N '' -f ~/.ssh/id_rsa")
    conn.run("ssh-keyscan -t rsa,ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null || true")

    log("CHAVE PÚBLICA SSH:")
    conn.run("cat ~/.ssh/id_rsa.pub")
    input("\n➡ Copie a chave acima, adicione no GitHub > Settings > Deploy Keys > Add deploy key\nDepois tecle ENTER aqui para continuar...")

    log("2. CLONANDO REPOSITÓRIO")
    conn.run(f"test -d {_project_path()} || git clone {repositorio} {_project_path()}")

    log("3. PREPARANDO AMBIENTE E BANCO DE DADOS")
    _bootstrap_project(conn)
    log("Configuração inicial concluída! Execute: fab deploy")


@task
def reclone(c):
    """Apaga a pasta do projeto no servidor e clona novamente a partir do zero."""
    conn = get_connection()
    _ensure_repositorio()

    log("1. REGISTRANDO GITHUB NO KNOWN_HOSTS")
    conn.run("mkdir -p ~/.ssh")
    conn.run("ssh-keyscan -t rsa,ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null || true")

    if not confirm(f"ATENÇÃO: Deseja apagar {_project_path()} no servidor e clonar de novo?", default=False):
        log("Operação cancelada.")
        return

    log("2. CLONANDO NOVAMENTE O REPOSITÓRIO")
    conn.run(f"rm -rf {_project_path()}")
    conn.run(f"git clone {repositorio} {_project_path()}")

    log("3. PREPARANDO AMBIENTE E BANCO DE DADOS")
    _bootstrap_project(conn)
    restart(c)
    nginx_restart(c)
    log("✔ Projeto reclonado e configurado com sucesso!")


@task
def deploy(c):
    """Executa o ciclo completo de deploy em produção."""
    log("Iniciando deploy da aplicação")
    pull(c)
    push(c)
    remote_pull(c)
    update_requirements(c)
    remote_migrate_all(c)
    translate_remote(c)
    collectstatic(c)
    restart(c)


@task
def server(c):
    """Inicia o servidor de desenvolvimento local na porta 8000."""
    log("Iniciando servidor de desenvolvimento do Django")
    c.run("python manage.py runserver 0.0.0.0:8000")


@task
def restart(c):
    """Reinicia o processo da aplicação gerenciado pelo Supervisor."""
    log("Reiniciando aplicação no Supervisor")
    conn = get_connection()
    conn.run(f"supervisorctl restart {username}")


@task
def fix_supervisor(c):
    """Atualiza o supervisor.ini com chdir, pythonpath e reinicia o Supervisor."""
    log(f"Atualizando /home/{username}/supervisor.ini no servidor")
    conn = get_connection()
    ini_content = f"""[program:{username}]
command=/home/{username}/env/bin/gunicorn --chdir /home/{username}/project --pythonpath /home/{username}/project -b 127.0.0.1:8002 config.wsgi:application
directory=/home/{username}/project
user={username}
autostart=true
autorestart=true
redirect_stderr=true
environment=PYTHONPATH="/home/{username}/project",LANG="pt_BR.UTF-8",LC_ALL="pt_BR.UTF-8"
"""
    conn.run(f"cat << 'EOF' > /home/{username}/supervisor.ini\n{ini_content}\nEOF")
    conn.sudo("supervisorctl reread", warn=True)
    conn.sudo("supervisorctl update", warn=True)
    conn.run(f"supervisorctl restart {username}")
    conn.run(f"supervisorctl status {username}")
    log("✔ Supervisor atualizado e aplicação iniciada com sucesso!")


@task
def nginx_restart(c):
    """Reinicia o Nginx no servidor."""
    conn = get_connection()
    result = conn.sudo("systemctl restart nginx", warn=True, hide=True)
    if result.failed:
        log("Não foi possível reiniciar o nginx diretamente (sem permissão sudo sem senha).")
    else:
        log("Nginx reiniciado com sucesso.")


@task
def nginx_reload(c):
    """Recarrega as configurações do Nginx."""
    log("Recarregando Nginx")
    conn = get_connection()
    conn.sudo("systemctl reload nginx", warn=True)


@task
def enable_ssl(c, dominio=None, root_user="root"):
    """Instala o Certbot e ativa SSL (HTTPS) gratuito da Let's Encrypt para o domínio."""
    import socket

    if not dominio:
        dominio = input("Digite o domínio para ativar o SSL (ex: meudominio.com ou futebol.meudominio.com): ").strip()

    log(f"Ativando SSL Let's Encrypt para {dominio}")

    # Valida quais subdomínios realmente respondem no DNS antes de chamar o Certbot
    candidatos = [dominio, f"www.{dominio}", f"static.{dominio}", f"media.{dominio}"]
    dominios_validos = []
    for d in candidatos:
        try:
            socket.gethostbyname(d)
            dominios_validos.append(d)
        except socket.error:
            pass

    if not dominios_validos:
        dominios_validos = [dominio]

    d_flags = " ".join([f"-d {d}" for d in dominios_validos])
    log(f"Domínios validados no DNS: {', '.join(dominios_validos)}")

    # Conecta como root para operações administrativas
    root_conn = Connection(host=host, user=root_user)
    root_conn.run("apt-get update && apt-get install -y certbot python3-certbot-nginx", warn=True)
    root_conn.run(
        f"certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email --expand {d_flags}"
    )
    root_conn.run("systemctl reload nginx", warn=True)
    log(f"✔ SSL ativado com sucesso para https://{dominio}!")


@task
def gunicorn(c):
    """Inicia o servidor de desenvolvimento local usando gunicorn."""
    log("Iniciando servidor de desenvolvimento local com gunicorn")
    c.run("gunicorn config.wsgi:application -w 4 -b 0.0.0.0:8000")


@task
def co(c):
    """Executa commit interativo local."""
    c.run("git commit -a")


@task
def commit_all(c):
    """Adiciona todos os arquivos e faz commit local."""
    c.run("git add .")
    c.run("git commit -a")


@task
def push(c):
    """Envia commits locais para o repositório remoto."""
    log("Enviando alterações locais para o GitHub")
    c.run(f"git push origin {branch}")


@task
def pull(c):
    """Atualiza a cópia local a partir do repositório remoto."""
    log("Atualizando cópia local")
    c.run(f"git pull origin {branch}")


@task
def commit_push(c, message=None):
    """Faz commit e push das alterações locais."""
    commit_all(c)
    pull(c)
    push(c)


@task
def remote_pull(c):
    """Atualiza a aplicação no servidor via git pull."""
    log("Atualizando código no servidor")
    with remote_project() as conn:
        conn.run(f"git pull origin {branch}")


@task
def cw(c):
    """Inicia o compass local no modo watch."""
    c.run("compass watch static")


@task
def compass_compile(c):
    """Compila o compass local."""
    c.run("compass compile static")


@task
def compress(c):
    """Comprime arquivos estáticos localmente."""
    c.run("python manage.py compress")


@task
def manage(c, cmd=""):
    """Executa um comando manage.py no servidor remoto."""
    if not cmd:
        cmd = input("Digite o comando para o manage.py (ex: migrate, check, dbshell): ").strip()
    with remote_project() as conn:
        conn.run(f"source {_env_path()} && python manage.py {cmd}", pty=True)


@task
def migrate(c):
    """Executa migrações do banco de dados no servidor."""
    log("Executando migrações no banco de dados")
    manage(c, "migrate --noinput")


@task
def createdb(c):
    """Sincroniza o banco de dados e executa migrações iniciais."""
    log("Criando e sincronizando banco de dados")
    manage(c, "migrate --noinput")


@task
def collectstatic(c):
    """Coleta e compacta arquivos estáticos no servidor."""
    log("Coletando arquivos estáticos")
    manage(c, "collectstatic --noinput")


@task
def remote_migrate_all(c):
    """Executa todas as migrações no servidor remoto."""
    log("Executando migrações em todas as aplicações")
    manage(c, "migrate --noinput")


@task
def translate(c):
    """Gera arquivos de tradução (.po) localmente."""
    c.run("python manage.py makemessages --all")


@task
def translate_remote(c):
    """Compila os arquivos de tradução (.mo) no servidor."""
    log("Compilando arquivos de tradução no servidor")
    conn = get_connection()
    with remote_project():
        conn.run(f"source {_env_path()} && python manage.py compilemessages", warn=True)


@task
def test(c):
    """Executa testes locais."""
    c.run("python manage.py test")


@task
def remote_test(c):
    """Executa os testes unitários no servidor remoto."""
    log("Executando testes no servidor")
    manage(c, "test")


@task
def revert(c):
    """Reverte o último commit na cópia local."""
    c.run("git reset --hard HEAD~1")


@task
def createsuperuser(c):
    """Cria um superusuário no servidor remoto."""
    log("Criando superusuário no servidor")
    with remote_project() as conn:
        conn.run(f"source {_env_path()} && python manage.py createsuperuser", pty=True)


@task
def update_requirements(c):
    """Atualiza as dependências do requirements.txt no servidor."""
    log("Atualizando dependências do Python no servidor")
    with remote_project() as conn:
        conn.run(f"source {_env_path()} && pip install -r requirements.txt")


@task
def upload_public_key(c, key_file="~/.ssh/id_rsa.pub"):
    """Envia sua chave SSH pública para o servidor remoto."""
    log("Enviando chave pública SSH para o servidor")
    conn = get_connection()
    conn.put(key_file, "/tmp/uploaded_key.pub")
    conn.run("mkdir -p ~/.ssh && cat /tmp/uploaded_key.pub >> ~/.ssh/authorized_keys && rm -f /tmp/uploaded_key.pub")
    conn.run("chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys")
    log("✔ Chave SSH autorizada com sucesso!")


@task
def login(c):
    """Abre uma sessão SSH interativa no servidor dedicado."""
    _ensure_server_config()
    c.run(f"ssh {username}@{host}", pty=True)
