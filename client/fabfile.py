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
app_type = ""  # "python" (Django), "php" ou "npm" (Node.js/frontend) - auto-detecta se vazio


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


def _get_app_type(explicit_type=None, conn=None, interactive=True):
    """Identifica o tipo de aplicação: 'python', 'php' ou 'npm'."""
    if explicit_type:
        val = str(explicit_type).strip().lower()
        if val in ("1", "python", "py", "django"):
            return "python"
        if val in ("2", "php", "laravel"):
            return "php"
        if val in ("3", "npm", "node", "nodejs", "frontend"):
            return "npm"
        return val

    configured = globals().get("app_type", "").strip().lower()
    if configured:
        if configured in ("1", "python", "py", "django"):
            return "python"
        if configured in ("2", "php", "laravel"):
            return "php"
        if configured in ("3", "npm", "node", "nodejs", "frontend"):
            return "npm"

    # Detecção local
    import os
    if os.path.exists("manage.py") or os.path.exists("requirements.txt") or os.path.exists("Pipfile"):
        return "python"
    if os.path.exists("composer.json") or os.path.exists("artisan"):
        return "php"
    if os.path.exists("package.json"):
        return "npm"

    # Detecção remota
    if conn:
        for base in (f"/home/{username}/project", f"/home/{username}/public_html"):
            res = conn.run(f"test -f {base}/manage.py || test -f {base}/requirements.txt", warn=True, hide=True)
            if res.ok:
                return "python"
            res = conn.run(f"test -f {base}/composer.json || test -f {base}/artisan", warn=True, hide=True)
            if res.ok:
                return "php"
            res = conn.run(f"test -f {base}/package.json", warn=True, hide=True)
            if res.ok:
                return "npm"

    if not interactive:
        return "python"

    escolha = input(
        "Tipo de aplicação para deploy:\n1) Python / Django\n2) PHP\n3) NPM (Node.js)\nEscolha a linguagem [1]: "
    ).strip().lower()
    if escolha in ("2", "php"):
        return "php"
    if escolha in ("3", "npm", "node", "nodejs"):
        return "npm"
    return "python"


def _project_path(conn=None):
    if conn:
        res_pub = conn.run(f"test -d /home/{username}/public_html/.git", warn=True, hide=True)
        if res_pub.ok:
            return f"/home/{username}/public_html"
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
    target_path = _project_path(conn)
    with conn.cd(target_path):
        yield conn


def log(message):
    print(f"\n{'=' * 62}\n{message}\n{'=' * 62}\n")


def _bootstrap_project(conn, app_t=None):
    """Instala dependências e prepara o ambiente conforme a linguagem do projeto."""
    t = _get_app_type(explicit_type=app_t, conn=conn, interactive=False)
    target = _project_path(conn)
    with remote_project() as c_proj:
        if t == "python":
            c_proj.run(f"source {_env_path()} && pip install -U pip")
            c_proj.run(f"test -f requirements.txt && source {_env_path()} && pip install -r requirements.txt || true")
            c_proj.run(f"test -f manage.py && source {_env_path()} && python manage.py migrate --noinput || true")
            res = c_proj.run(f"test -f manage.py && source {_env_path()} && python manage.py compilemessages", warn=True)
            if res.failed:
                log("AVISO: gettext não instalado no servidor. Para instalar, execute: fab install-gettext")
            res_pkg = c_proj.run("test -f package.json", warn=True, hide=True)
            if res_pkg.ok:
                c_proj.run("npm install --no-audit && (grep -q '\"build\"' package.json && npm run build || true)", warn=True)
            c_proj.run(f"test -f manage.py && source {_env_path()} && python manage.py collectstatic --noinput || true")
        elif t == "php":
            if target == f"/home/{username}/project":
                res_pub = conn.run(f"test -d /home/{username}/project/public", warn=True, hide=True)
                pub_target = f"/home/{username}/project/public" if res_pub.ok else f"/home/{username}/project"
                conn.run(f"test -d /home/{username}/public_html/.git || (test -L /home/{username}/public_html || rm -rf /home/{username}/public_html)", warn=True)
                conn.run(f"test -e /home/{username}/public_html || ln -sfn {pub_target} /home/{username}/public_html", warn=True)

            res_comp = c_proj.run("test -f composer.json", warn=True, hide=True)
            if res_comp.ok:
                res_which = c_proj.run("which composer", warn=True, hide=True)
                if res_which.ok:
                    c_proj.run("composer install --no-dev --optimize-autoloader --no-interaction", warn=True)
                else:
                    log("AVISO: composer não encontrado no PATH do servidor.")
            res_pkg = c_proj.run("test -f package.json", warn=True, hide=True)
            if res_pkg.ok:
                c_proj.run("test -d node_modules || npm install --no-audit --no-fund", warn=True)
                c_proj.run("grep -q '\"build\"' package.json && npm run build || true", warn=True)
        elif t == "npm":
            c_proj.run("test -f package-lock.json && npm ci --prefer-offline --no-audit || npm install --no-audit", warn=True)
            res_build = c_proj.run("grep -q '\"build\"' package.json", warn=True, hide=True)
            if res_build.ok:
                c_proj.run("npm run build")
                c_proj.run("test -d build && (test -d dist || ln -s build dist) || true", warn=True)


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
def config(c, app_type=None):
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

    target = _project_path(conn)
    log("2. CLONANDO REPOSITÓRIO")
    conn.run(f"test -d {target}/.git || (rm -rf {target} && git clone {repositorio} {target})")

    log("3. PREPARANDO AMBIENTE E DEPENDÊNCIAS")
    _bootstrap_project(conn, app_t=app_type)
    log("Configuração inicial concluída! Execute: fab deploy")


@task
def reclone(c, app_type=None):
    """Apaga a pasta do projeto no servidor e clona novamente a partir do zero."""
    conn = get_connection()
    _ensure_repositorio()

    log("1. REGISTRANDO GITHUB NO KNOWN_HOSTS")
    conn.run("mkdir -p ~/.ssh")
    conn.run("ssh-keyscan -t rsa,ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null || true")

    target = _project_path(conn)
    if not confirm(f"ATENÇÃO: Deseja apagar {target} no servidor e clonar de novo?", default=False):
        log("Operação cancelada.")
        return

    log("2. CLONANDO NOVAMENTE O REPOSITÓRIO")
    conn.run(f"rm -rf {target}")
    conn.run(f"git clone {repositorio} {target}")

    log("3. PREPARANDO AMBIENTE E DEPENDÊNCIAS")
    _bootstrap_project(conn, app_t=app_type)
    restart(c)
    nginx_restart(c)
    log("✔ Projeto reclonado e configurado com sucesso!")


@task
def npm_install(c):
    """Instala dependências do NPM no servidor."""
    log("Instalando dependências do NPM no servidor")
    with remote_project() as conn:
        conn.run(
            "test -f package-lock.json && npm ci --prefer-offline --no-audit || npm install --no-audit"
        )


@task
def npm_build(c):
    """Executa 'npm run build' no servidor se package.json e o script existirem."""
    with remote_project() as conn:
        res = conn.run("test -f package.json", warn=True, hide=True)
        if res.ok:
            log("Verificando e compilando assets NPM no servidor")
            conn.run("test -d node_modules || npm install --no-audit --no-fund", warn=True)
            res_build = conn.run("grep -q '\"build\"' package.json 2>/dev/null", warn=True, hide=True)
            if res_build.ok:
                conn.run("npm run build")
                conn.run("test -d build && (test -d dist || ln -s build dist) || true", warn=True)


@task
def update_composer(c):
    """Atualiza dependências do Composer no servidor se composer.json existir."""
    with remote_project() as conn:
        res = conn.run("test -f composer.json", warn=True, hide=True)
        if res.ok:
            log("Atualizando dependências do Composer no servidor")
            res_c = conn.run("which composer", warn=True, hide=True)
            if res_c.ok:
                conn.run("composer install --no-dev --optimize-autoloader --no-interaction")
            else:
                log("AVISO: composer não encontrado no PATH do servidor.")


@task
def reload_php(c):
    """Recarrega os serviços PHP-FPM e Nginx no servidor."""
    log("Recarregando serviços PHP e Nginx")
    conn = get_connection()
    conn.sudo("systemctl reload 'php*-fpm' || systemctl reload php-fpm || true", warn=True)
    nginx_reload(c)


@task
def deploy_python(c):
    """Executa o ciclo completo de deploy para aplicações Python / Django."""
    log("Iniciando deploy da aplicação Python / Django")
    pull(c)
    push(c)
    remote_pull(c)
    update_requirements(c)
    npm_build(c)
    remote_migrate_all(c)
    translate_remote(c)
    collectstatic(c)
    restart(c)
    log("✔ Deploy Python / Django concluído com sucesso!")


@task
def deploy_php(c):
    """Executa o ciclo completo de deploy para aplicações PHP."""
    log("Iniciando deploy da aplicação PHP")
    pull(c)
    push(c)
    remote_pull(c)
    conn = get_connection()
    target = _project_path(conn)
    if target == f"/home/{username}/project":
        res_pub = conn.run(f"test -d /home/{username}/project/public", warn=True, hide=True)
        pub_target = f"/home/{username}/project/public" if res_pub.ok else f"/home/{username}/project"
        conn.run(f"test -d /home/{username}/public_html/.git || (test -L /home/{username}/public_html || rm -rf /home/{username}/public_html)", warn=True)
        conn.run(f"test -e /home/{username}/public_html || ln -sfn {pub_target} /home/{username}/public_html", warn=True)
    update_composer(c)
    npm_build(c)
    with remote_project() as c_proj:
        res_art = c_proj.run("test -f artisan", warn=True, hide=True)
        if res_art.ok:
            log("Executando comandos Artisan (Laravel)")
            c_proj.run("php artisan migrate --force", warn=True)
            c_proj.run("php artisan config:cache", warn=True)
            c_proj.run("php artisan route:cache", warn=True)
            c_proj.run("php artisan view:cache", warn=True)
    reload_php(c)
    log("✔ Deploy PHP concluído com sucesso!")


@task
def deploy_npm(c):
    """Executa o ciclo completo de deploy para aplicações NPM / Node.js."""
    log("Iniciando deploy da aplicação NPM / Node.js")
    pull(c)
    push(c)
    remote_pull(c)
    npm_install(c)
    npm_build(c)
    conn = get_connection()
    status = conn.run(f"supervisorctl status {username}", warn=True, hide=True)
    if status.ok and "ERROR (no such process)" not in status.stdout:
        restart(c)
    else:
        nginx_reload(c)
    log("✔ Deploy NPM / Node.js concluído com sucesso!")


@task
def deploy(c, app_type=None):
    """Executa o ciclo completo de deploy em produção (auto-detecta Python, PHP ou NPM)."""
    conn = get_connection()
    t = _get_app_type(explicit_type=app_type, conn=conn)
    log(f"Iniciando deploy para: {t.upper()}")
    if t == "python":
        deploy_python(c)
    elif t == "php":
        deploy_php(c)
    elif t == "npm":
        deploy_npm(c)
    else:
        log(f"Tipo de aplicação '{t}' não reconhecido. Use 'python', 'php' ou 'npm'.")


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
def fix_supervisor(c, app_type=None, port="8002", command=""):
    """Atualiza o supervisor.ini no servidor (suporta Python e Node.js/NPM) e reinicia."""
    t = _get_app_type(explicit_type=app_type, interactive=False)
    log(f"Atualizando /home/{username}/supervisor.ini no servidor ({t})")
    conn = get_connection()
    if t == "npm":
        cmd = command or "npm run start"
        ini_content = f"""[program:{username}]
command={cmd}
directory=/home/{username}/project
user={username}
autostart=true
autorestart=true
redirect_stderr=true
environment=PORT="{port}",NODE_ENV="production",PATH="/usr/local/bin:/usr/bin:/bin",LANG="pt_BR.UTF-8",LC_ALL="pt_BR.UTF-8"
"""
    else:
        cmd = command or f"/home/{username}/env/bin/gunicorn --chdir /home/{username}/project --pythonpath /home/{username}/project -b 127.0.0.1:{port} config.wsgi:application"
        ini_content = f"""[program:{username}]
command={cmd}
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
