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
