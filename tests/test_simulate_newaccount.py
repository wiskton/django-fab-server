"""Simula `fab newaccount` (criação de site/conta no servidor) sem tocar a
rede: Connection.run/sudo/put são substituídos por um gravador de comandos,
e as respostas do operador são simuladas via monkeypatch de input().

Serve como teste de integração do fluxo inteiro após a migração para
Fabric 3.x -- garante que a sequência de comandos remotos ainda faz sentido
de ponta a ponta (cria usuário linux, venv, nginx.conf, supervisor.ini,
banco de dados e reinicia os serviços) e que os dados sensíveis do MySQL
(senha root, SQL de CREATE USER/DATABASE) nunca vão na linha de comando.
"""
from fabric import Connection
from invoke import Context


class CommandRecorder:
    def __init__(self):
        self.sudo_calls = []
        self.run_calls = []
        self.put_calls = []  # (remote, content)

    def record_sudo(self):
        def _fn(_self, command, *args, **kwargs):
            self.sudo_calls.append(command)
            return None

        return _fn

    def record_run(self):
        def _fn(_self, command, *args, **kwargs):
            self.run_calls.append(command)
            return None

        return _fn

    def record_put(self):
        def _fn(_self, local, remote=None, **kwargs):
            content = None
            if hasattr(local, "read"):
                pos = local.tell()
                local.seek(0)
                content = local.read()
                local.seek(pos)
                if isinstance(content, bytes):
                    # write_file()/_mysql_exec() usam BytesIO (ver comentário
                    # em write_file) -- decodifica pra comparar como texto
                    content = content.decode("utf-8")
            self.put_calls.append((remote, content))
            return None

        return _fn


def test_simulate_new_python_site_creation(server_fabfile, monkeypatch):
    recorder = CommandRecorder()

    monkeypatch.setattr(Connection, "run", recorder.record_run())
    monkeypatch.setattr(Connection, "sudo", recorder.record_sudo())
    monkeypatch.setattr(Connection, "put", recorder.record_put())

    server_fabfile.get_connection.cache_clear()
    for attr in ("conta", "dominio", "linguagem", "porta", "pasta_settings", "mysql_password"):
        server_fabfile.cfg[attr] = ""

    respostas = iter(
        [
            "acmesite",       # nome da conta
            "acme.com.br",    # dominio
            "1",              # linguagem: python
            "8060",           # porta
            "config",         # pasta com o wsgi
            "senha-root-mysql",  # senha root do mysql
            "n",              # NÃO permitir acesso remoto ao banco (padrão seguro)
        ]
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(respostas))

    try:
        server_fabfile.newaccount(Context())
    finally:
        server_fabfile.get_connection.cache_clear()
        for attr in ("conta", "dominio", "linguagem", "porta", "pasta_settings", "mysql_password"):
            server_fabfile.cfg[attr] = ""

    print("\n--- comandos sudo simulados (fab newaccount) ---")
    for cmd in recorder.sudo_calls:
        print(" $", cmd)
    print("--- arquivos enviados (write_file / mysql) ---")
    for remote, content in recorder.put_calls:
        preview = (content or "").replace("\n", " ")[:80]
        print(" ->", remote, ":", preview)

    # criou o usuário linux e a estrutura de logs
    assert "adduser acmesite" in recorder.sudo_calls
    assert "mkdir /home/acmesite/logs" in recorder.sudo_calls

    # criou o virtualenv python3 (não o antigo `virtualenv --no-site-packages`)
    assert "python3 -m venv /home/acmesite/env" in recorder.sudo_calls

    # enviou os 3 arquivos de configuração esperados para o fluxo python
    destinations = {remote for remote, _content in recorder.put_calls}
    assert any(d.startswith("/tmp/nginx.conf") for d in destinations)
    assert any(d.startswith("/tmp/supervisor.ini") for d in destinations)
    assert any(d.startswith("/tmp/.bash_login") for d in destinations)

    # o SQL do banco foi enviado por arquivo (SFTP), nunca na linha de comando
    sql_contents = [
        content for remote, content in recorder.put_calls if remote.endswith(".sql")
    ]
    assert any("CREATE DATABASE acmesite" in sql for sql in sql_contents)
    assert any("CREATE USER 'acmesite'@'localhost'" in sql for sql in sql_contents)

    # por padrão (resposta "n" ao prompt), NENHUM usuário remoto '@'%'' é criado
    assert not any("'acmesite'@'%'" in sql for sql in sql_contents)

    # a senha do root do mysql também nunca aparece na linha de comando: vai
    # em um --defaults-extra-file temporário
    assert not any("senha-root-mysql" in cmd for cmd in recorder.sudo_calls)
    cnf_contents = [
        content for remote, content in recorder.put_calls if remote.endswith(".cnf")
    ]
    assert any("password=senha-root-mysql" in cnf for cnf in cnf_contents)
    assert any("--defaults-extra-file=" in cmd for cmd in recorder.sudo_calls)

    # os arquivos temporários de SQL/senha são sempre removidos depois de usados
    sql_paths = [remote for remote, _content in recorder.put_calls if remote.endswith(".sql")]
    cnf_paths = [remote for remote, _content in recorder.put_calls if remote.endswith(".cnf")]
    for path in sql_paths + cnf_paths:
        assert any(cmd == "rm -f {0}".format(path) for cmd in recorder.sudo_calls)

    # ajustou a permissão do diretório e reiniciou nginx + supervisor
    assert "chown -R acmesite:acmesite /home/acmesite" in recorder.sudo_calls
    assert "systemctl restart nginx" in recorder.sudo_calls
    assert "systemctl restart supervisor" in recorder.sudo_calls


def test_simulate_new_npm_ssr_site_creation(server_fabfile, monkeypatch):
    recorder = CommandRecorder()

    monkeypatch.setattr(Connection, "run", recorder.record_run())
    monkeypatch.setattr(Connection, "sudo", recorder.record_sudo())
    monkeypatch.setattr(Connection, "put", recorder.record_put())

    server_fabfile.get_connection.cache_clear()
    for attr in ("conta", "dominio", "linguagem", "porta", "npm_type", "npm_start_cmd", "mysql_password"):
        server_fabfile.cfg[attr] = ""

    respostas = iter(
        [
            "nodeapp",          # nome da conta
            "nodeapp.com.br",   # dominio
            "3",                # linguagem: NPM (Node.js)
            "1",                # tipo: 1) SSR / API
            "8070",             # porta
            "npm run start",    # comando start
            "senha-root-mysql", # senha root mysql
            "n",                # sem acesso remoto
        ]
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(respostas))

    try:
        server_fabfile.newaccount(Context())
    finally:
        server_fabfile.get_connection.cache_clear()
        for attr in ("conta", "dominio", "linguagem", "porta", "npm_type", "npm_start_cmd", "mysql_password"):
            server_fabfile.cfg[attr] = ""

    # criou usuario, logs e project
    assert "adduser nodeapp" in recorder.sudo_calls
    assert "mkdir /home/nodeapp/logs" in recorder.sudo_calls
    assert "mkdir -p /home/nodeapp/project" in recorder.sudo_calls

    # enviou os arquivos de configuracao esperados (nginx.conf a partir de nginx_node.conf e supervisor.ini)
    destinations = {remote for remote, _content in recorder.put_calls}
    assert any(d.startswith("/tmp/nginx.conf") for d in destinations)
    assert any(d.startswith("/tmp/supervisor.ini") for d in destinations)

    # supervisor.ini contém o comando e porta corretos
    supervisor_contents = [
        content for remote, content in recorder.put_calls if "supervisor.ini" in remote
    ]
    assert any("command=npm run start" in c for c in supervisor_contents)
    assert any('PORT="8070"' in c for c in supervisor_contents)

    # ajustou permissoes e reiniciou servicos
    assert "chown -R nodeapp:nodeapp /home/nodeapp" in recorder.sudo_calls
    assert "systemctl restart nginx" in recorder.sudo_calls
    assert "systemctl restart supervisor" in recorder.sudo_calls


def test_simulate_new_npm_static_site_creation(server_fabfile, monkeypatch):
    recorder = CommandRecorder()

    monkeypatch.setattr(Connection, "run", recorder.record_run())
    monkeypatch.setattr(Connection, "sudo", recorder.record_sudo())
    monkeypatch.setattr(Connection, "put", recorder.record_put())

    server_fabfile.get_connection.cache_clear()
    for attr in ("conta", "dominio", "linguagem", "porta", "npm_type", "npm_start_cmd", "mysql_password"):
        server_fabfile.cfg[attr] = ""

    respostas = iter(
        [
            "reactspa",         # nome da conta
            "reactspa.com.br",  # dominio
            "3",                # linguagem: NPM (Node.js)
            "2",                # tipo: 2) Frontend Estático / SPA
            "senha-root-mysql", # senha root mysql
            "n",                # sem acesso remoto
        ]
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(respostas))

    try:
        server_fabfile.newaccount(Context())
    finally:
        server_fabfile.get_connection.cache_clear()
        for attr in ("conta", "dominio", "linguagem", "porta", "npm_type", "npm_start_cmd", "mysql_password"):
            server_fabfile.cfg[attr] = ""

    # criou usuario, logs, dist e public_html
    assert "adduser reactspa" in recorder.sudo_calls
    assert "mkdir /home/reactspa/logs" in recorder.sudo_calls
    assert "mkdir -p /home/reactspa/project/dist" in recorder.sudo_calls
    assert "mkdir -p /home/reactspa/public_html" in recorder.sudo_calls

    # enviou nginx.conf a partir de nginx_npm_static.conf (e NÃO enviou supervisor.ini)
    destinations = {remote for remote, _content in recorder.put_calls}
    assert any(d.startswith("/tmp/nginx.conf") for d in destinations)
    assert not any(d.startswith("/tmp/supervisor.ini") for d in destinations)

    # nginx.conf tem root /home/reactspa/project/dist/
    nginx_contents = [
        content for remote, content in recorder.put_calls if "nginx.conf" in remote
    ]
    assert any("root /home/reactspa/project/dist/;" in c for c in nginx_contents)

    # ajustou permissoes e reiniciou servicos
    assert "chown -R reactspa:reactspa /home/reactspa" in recorder.sudo_calls
    assert "systemctl restart nginx" in recorder.sudo_calls


def test_simulate_new_php_site_creation(server_fabfile, monkeypatch):
    recorder = CommandRecorder()

    monkeypatch.setattr(Connection, "run", recorder.record_run())
    monkeypatch.setattr(Connection, "sudo", recorder.record_sudo())
    monkeypatch.setattr(Connection, "put", recorder.record_put())

    server_fabfile.get_connection.cache_clear()
    for attr in ("conta", "dominio", "linguagem", "porta", "mysql_password"):
        server_fabfile.cfg[attr] = ""

    respostas = iter(
        [
            "phpsite",          # nome da conta
            "phpsite.com.br",   # dominio
            "2",                # linguagem: PHP
            "",                 # enter para confirmação do cgi.fix_pathinfo
            "senha-root-mysql", # senha root mysql
            "n",                # sem acesso remoto
        ]
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(respostas))

    try:
        server_fabfile.newaccount(Context())
    finally:
        server_fabfile.get_connection.cache_clear()
        for attr in ("conta", "dominio", "linguagem", "porta", "mysql_password"):
            server_fabfile.cfg[attr] = ""

    # criou usuario, logs e public_html
    assert "adduser phpsite" in recorder.sudo_calls
    assert "mkdir /home/phpsite/logs" in recorder.sudo_calls
    assert "mkdir /home/phpsite/public_html/" in recorder.sudo_calls

    # enviou nginx.conf (a partir de nginx_php.conf) e NÃO supervisor.ini
    destinations = {remote for remote, _content in recorder.put_calls}
    assert any(d.startswith("/tmp/nginx.conf") for d in destinations)
    assert not any(d.startswith("/tmp/supervisor.ini") for d in destinations)

    # nginx.conf tem root /home/phpsite/public_html/ e fastcgi_pass
    nginx_contents = [
        content for remote, content in recorder.put_calls if "nginx.conf" in remote
    ]
    assert any("root /home/phpsite/public_html/;" in c for c in nginx_contents)
    assert any("fastcgi_pass" in c for c in nginx_contents)

    # ajustou permissoes e reiniciou servicos
    assert "chown -R phpsite:phpsite /home/phpsite" in recorder.sudo_calls
    assert "systemctl restart nginx" in recorder.sudo_calls

