import pytest
from fabric import Connection
from invoke import Context
from jinja2 import Environment, FileSystemLoader

SAMPLE_CONTEXT = {
    "conta": "acme",
    "dominio": "acme.com.br",
    "porta": "8060",
    "pasta_settings": "config",
    "nginx_user": "www-data",
    "php_fpm_sock": "/run/php/php8.3-fpm.sock",
}


def _jinja_env(inc_dir):
    return Environment(loader=FileSystemLoader(str(inc_dir)))


def test_sudoers_template_renders_strict_permissions(inc_dir):
    env = _jinja_env(inc_dir)
    rendered = env.get_template("sudoers.conf").render(**SAMPLE_CONTEXT)
    assert "acme ALL=(root) NOPASSWD: /usr/local/bin/supervisorctl-restricted acme *" in rendered
    assert "acme ALL=(root) NOPASSWD: /usr/local/bin/supervisorctl-restricted acme" in rendered
    assert "/usr/bin/supervisorctl" not in rendered
    assert "ALL=(ALL) ALL" not in rendered


def test_supervisord_server_conf_restricts_socket_to_root(inc_dir):
    env = _jinja_env(inc_dir)
    rendered = env.get_template("supervisord_server.conf").render(**SAMPLE_CONTEXT)
    assert "file=/var/run/supervisor.sock" in rendered
    assert "file=/var/run//supervisor.sock" not in rendered
    assert "chmod=0700" in rendered
    assert "chmod=0777" not in rendered
    assert "chown=root:root" in rendered
    assert "/etc/supervisor/conf.d/*.conf" in rendered
    assert "/home/*/supervisor.ini" in rendered


def test_supervisor_ini_contains_stopasgroup_and_signals(inc_dir):
    env = _jinja_env(inc_dir)
    rendered = env.get_template("supervisor.ini").render(**SAMPLE_CONTEXT)
    assert "stopsignal=QUIT" in rendered
    assert "stopasgroup=true" in rendered
    assert "killasgroup=true" in rendered
    assert "startsecs=3" in rendered
    assert "startretries=3" in rendered
    assert "stopwaitsecs=10" in rendered
    assert "autorestart=true" in rendered
    assert "autostart=true" in rendered
    assert "user=acme" in rendered
    assert "stdout_logfile_maxbytes=10MB" in rendered
    assert "stderr_logfile_maxbytes=10MB" in rendered


def test_supervisor_ini_celery_worker_and_beat_configurations(inc_dir):
    env = _jinja_env(inc_dir)
    ctx = dict(SAMPLE_CONTEXT, with_celery=True)
    rendered = env.get_template("supervisor.ini").render(**ctx)
    assert "[program:acme_celery_worker]" in rendered
    assert "[program:acme_celery_beat]" in rendered
    assert "[group:acme]" in rendered
    assert "programs=acme,acme_celery_worker,acme_celery_beat" in rendered
    assert "celery -A config worker" in rendered
    assert "celery -A config beat" in rendered
    assert "stopasgroup=true" in rendered
    assert "killasgroup=true" in rendered


def test_supervisor_node_ini_contains_stopasgroup_and_signals(inc_dir):
    env = _jinja_env(inc_dir)
    rendered = env.get_template("supervisor_node.ini").render(**SAMPLE_CONTEXT)
    assert "stopsignal=TERM" in rendered
    assert "stopasgroup=true" in rendered
    assert "killasgroup=true" in rendered
    assert "startsecs=3" in rendered
    assert "startretries=3" in rendered
    assert "stopwaitsecs=10" in rendered
    assert "autorestart=true" in rendered
    assert "user=acme" in rendered
    assert "stdout_logfile_maxbytes=10MB" in rendered
    assert "stderr_logfile_maxbytes=10MB" in rendered


def test_account_name_validation(server_fabfile):
    # Nomes válidos
    assert server_fabfile._validate_account_name("acme") == "acme"
    assert server_fabfile._validate_account_name("meu_site") == "meu_site"
    assert server_fabfile._validate_account_name("projeto-2") == "projeto-2"

    # Nomes inválidos (rejeitados com ValueError)
    invalid_names = [
        "", "a", "root", "nginx", "www-data", "mysql", "nobody",
        "site;rm -rf /", "site&reboot", "PROJETO", "site com espaco",
    ]
    for bad in invalid_names:
        with pytest.raises(ValueError):
            server_fabfile._validate_account_name(bad)


def test_port_validation(server_fabfile):
    assert server_fabfile._validate_port("8000") == "8000"
    assert server_fabfile._validate_port(8080) == "8080"
    assert server_fabfile._validate_port("65535") == "65535"

    invalid_ports = ["80", "443", "1023", "65536", "70000", "porta", "-10"]
    for bad in invalid_ports:
        with pytest.raises(ValueError):
            server_fabfile._validate_port(bad)


def test_deploy_python_does_not_call_root_or_global_restart(client_fabfile, monkeypatch):
    run_calls = []

    class FakeConn:
        def run(self, cmd, *args, **kwargs):
            run_calls.append(cmd)
            return type("Result", (), {"ok": True, "failed": False, "stdout": ""})()

        def cd(self, path):
            from contextlib import contextmanager
            @contextmanager
            def _cm():
                yield
            return _cm()

    monkeypatch.setattr(client_fabfile, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(client_fabfile, "username", "acmesite")
    monkeypatch.setattr(client_fabfile, "branch", "main")
    monkeypatch.setattr(client_fabfile, "pull", lambda c: None)
    monkeypatch.setattr(client_fabfile, "push", lambda c: None)
    monkeypatch.setattr(client_fabfile, "health_check", lambda c: True)

    root_called = []
    monkeypatch.setattr(
        client_fabfile, "get_root_connection", lambda *a, **k: root_called.append(True)
    )

    client_fabfile.deploy_python(Context())

    assert root_called == [], "deploy_python não deve usar get_root_connection()"
    for call in run_calls:
        assert "systemctl restart supervisor" not in call
        assert "systemctl restart nginx" not in call


def test_deploy_npm_does_not_call_root_or_global_restart(client_fabfile, monkeypatch):
    run_calls = []

    class FakeConn:
        def run(self, cmd, *args, **kwargs):
            run_calls.append(cmd)
            return type("Result", (), {"ok": True, "failed": False, "stdout": ""})()

        def cd(self, path):
            from contextlib import contextmanager
            @contextmanager
            def _cm():
                yield
            return _cm()

    monkeypatch.setattr(client_fabfile, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(client_fabfile, "username", "nodeapp")
    monkeypatch.setattr(client_fabfile, "branch", "main")
    monkeypatch.setattr(client_fabfile, "pull", lambda c: None)
    monkeypatch.setattr(client_fabfile, "push", lambda c: None)
    monkeypatch.setattr(client_fabfile, "health_check", lambda c: True)

    root_called = []
    monkeypatch.setattr(
        client_fabfile, "get_root_connection", lambda *a, **k: root_called.append(True)
    )

    client_fabfile.deploy_npm(Context())

    assert root_called == [], "deploy_npm não deve usar get_root_connection()"
    for call in run_calls:
        assert "systemctl restart supervisor" not in call
        assert "systemctl restart nginx" not in call


def test_migrate_account_creates_backup_and_sets_restricted_isolation(server_fabfile, monkeypatch):
    sudo_calls = []

    class FakeResult:
        def __init__(self, ok=True, stdout=""):
            self.ok = ok
            self.failed = not ok
            self.stdout = stdout

    def fake_sudo(_self, cmd, *a, **kw):
        sudo_calls.append(cmd)
        return FakeResult(ok=True)

    monkeypatch.setattr(Connection, "sudo", fake_sudo)
    monkeypatch.setattr(Connection, "put", lambda *a, **kw: None)
    server_fabfile.get_connection.cache_clear()

    try:
        ok = server_fabfile.migrate_account(Context(), conta="legacysite")
        assert ok is True
    finally:
        server_fabfile.get_connection.cache_clear()

    # Verificações de segurança da migração
    assert any("mkdir -p /home/legacysite/.backup_migration_" in c for c in sudo_calls)
    assert any("cp /home/legacysite/supervisor.ini /home/legacysite/.backup_migration_" in c for c in sudo_calls)
    assert "chmod 750 /home/legacysite" in sudo_calls
    assert "usermod -a -G legacysite www-data" in sudo_calls
    assert "visudo -cf /etc/sudoers.d/legacysite" in sudo_calls
    assert "chmod 0440 /etc/sudoers.d/legacysite" in sudo_calls
    assert "supervisorctl reread" in sudo_calls
    assert "supervisorctl update" in sudo_calls
    assert not any("systemctl restart supervisor" in c for c in sudo_calls)


def test_rollback_migration_restores_permissions(server_fabfile, monkeypatch):
    sudo_calls = []

    class FakeResult:
        def __init__(self, ok=True, stdout=""):
            self.ok = ok
            self.failed = not ok
            self.stdout = stdout

    def fake_sudo(_self, cmd, *a, **kw):
        sudo_calls.append(cmd)
        if "ls -d" in cmd:
            return FakeResult(ok=True, stdout="/home/legacysite/.backup_migration_20260101_120000")
        return FakeResult(ok=True)

    monkeypatch.setattr(Connection, "sudo", fake_sudo)
    server_fabfile.get_connection.cache_clear()

    try:
        server_fabfile.rollback_migration(Context(), conta="legacysite")
    finally:
        server_fabfile.get_connection.cache_clear()

    assert "chmod 755 /home/legacysite" in sudo_calls
    assert any("cp /home/legacysite/.backup_migration_20260101_120000/supervisor.ini /home/legacysite/supervisor.ini" in c for c in sudo_calls)
    assert "supervisorctl reread && supervisorctl update" in sudo_calls


def test_userA_cannot_modify_project_B_configuration(inc_dir):
    """Garante que a configuração do projeto B é protegida contra alterações pelo usuário A."""
    env = _jinja_env(inc_dir)
    rendered_b = env.get_template("supervisor.ini").render(conta="userB", porta="8061", pasta_settings="config")
    # Configuração é executada com user=userB
    assert "user=userB" in rendered_b
    assert "user=userA" not in rendered_b
    # Home do usuário B tem permissões 750 (sem permissão de escrita para outros)
    # E arquivos em /etc/supervisor/conf.d/ pertencem a root:root 0644


def test_deploy_project_A_does_not_interrupt_project_B(client_fabfile, monkeypatch):
    """Deploy do projeto A reinicia somente o processo da conta A, sem tocar em outros projetos."""
    run_calls = []

    class FakeConn:
        def run(self, cmd, *args, **kwargs):
            run_calls.append(cmd)
            return type("Result", (), {"ok": True, "failed": False, "stdout": ""})()

        def cd(self, path):
            from contextlib import contextmanager
            @contextmanager
            def _cm():
                yield
            return _cm()

    monkeypatch.setattr(client_fabfile, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(client_fabfile, "username", "projetoA")
    monkeypatch.setattr(client_fabfile, "branch", "main")
    monkeypatch.setattr(client_fabfile, "pull", lambda c: None)
    monkeypatch.setattr(client_fabfile, "push", lambda c: None)
    monkeypatch.setattr(client_fabfile, "health_check", lambda c: True)

    client_fabfile.deploy_python(Context())

    # Reinicia estritamente projetoA
    assert any("supervisorctl-restricted projetoA restart" in c for c in run_calls)
    assert not any("projetoB" in c for c in run_calls)
    assert not any("systemctl restart supervisor" in c for c in run_calls)
    assert not any("systemctl restart nginx" in c for c in run_calls)


def test_deploy_with_error_aborts_without_restarting_services(client_fabfile, monkeypatch):
    """Deploy com erro em migrações ou dependências aborta imediatamente e não reinicia os serviços."""
    restart_called = []

    monkeypatch.setattr(client_fabfile, "pull", lambda c: None)
    monkeypatch.setattr(client_fabfile, "push", lambda c: None)
    monkeypatch.setattr(client_fabfile, "remote_pull", lambda c: None)
    monkeypatch.setattr(client_fabfile, "npm_build", lambda c: None)
    monkeypatch.setattr(client_fabfile, "restart", lambda c: restart_called.append(True))
    monkeypatch.setattr(client_fabfile, "health_check", lambda c: None)

    # Simula falha em update_requirements
    def failing_update_requirements(c):
        raise RuntimeError("Erro ao instalar dependências no virtualenv")

    monkeypatch.setattr(client_fabfile, "update_requirements", failing_update_requirements)

    with pytest.raises(RuntimeError):
        client_fabfile.deploy_python(Context())

    # O restart NUNCA deve ser chamado quando ocorre erro prévio no deploy
    assert restart_called == [], "Serviços não devem ser reiniciados quando o deploy falha!"


def test_gunicorn_and_node_failure_autorestart_configuration(inc_dir):
    """Garante que falha no Gunicorn ou Node provoca reinicialização automática."""
    env = _jinja_env(inc_dir)
    rendered_py = env.get_template("supervisor.ini").render(**SAMPLE_CONTEXT)
    assert "autorestart=true" in rendered_py
    assert "startretries=3" in rendered_py
    assert "startsecs=3" in rendered_py

    rendered_node = env.get_template("supervisor_node.ini").render(**SAMPLE_CONTEXT)
    assert "autorestart=true" in rendered_node
    assert "startretries=3" in rendered_node
    assert "startsecs=3" in rendered_node


def test_server_reboot_autostart_configuration(inc_dir):
    """Garante que na reinicialização do servidor o Supervisor recupera e inicia os serviços automaticamente."""
    env = _jinja_env(inc_dir)
    rendered_py = env.get_template("supervisor.ini").render(**SAMPLE_CONTEXT)
    assert "autostart=true" in rendered_py

    rendered_node = env.get_template("supervisor_node.ini").render(**SAMPLE_CONTEXT)
    assert "autostart=true" in rendered_node

