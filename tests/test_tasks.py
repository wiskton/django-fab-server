from invoke import Collection, Context, Task

EXPECTED_ROOT_TASKS = {
    "adduser", "aptget", "build-local", "build-server", "delaccount",
    "dropbase", "git-local", "git-server", "listaccount", "login",
    "mysql-local", "mysql-restart", "mysql-server", "mysql-start",
    "mysql-stop", "newaccount", "newbase", "newdev", "newproject",
    "newserver", "nginx-reload", "nginx-restart", "nginx-start",
    "nginx-stop", "node-server", "others-server", "proftpd-restart", "python-local",
    "python-server", "reboot", "restart", "restart-server", "start-server",
    "stop-server", "supervisor-restart", "supervisor-start",
    "supervisor-stop", "update-local", "update-server", "upgrade-local",
    "upgrade-server", "upload-public-key", "userdel", "install-ssl",
    "install-mysql-deps",
}

EXPECTED_PROJETO_TASKS = {
    "co", "collectstatic", "commit-all", "commit-push", "compass-compile",
    "compress", "config", "createdb", "createsuperuser", "cw", "deploy",
    "deploy-python", "deploy-php", "deploy-npm", "npm-install", "npm-build",
    "update-composer", "reload-php",
    "gunicorn", "login", "manage", "migrate", "nginx-restart", "nginx-reload",
    "pull", "push", "reclone", "remote-migrate-all", "remote-pull", "remote-test",
    "restart", "revert", "server", "test", "translate", "translate-remote",
    "update-requirements", "upload-public-key", "install-gettext", "show-key",
    "fix-supervisor", "enable-ssl", "install-redis", "setup-celery",
    "health-check",
}


def test_server_fabfile_exposes_expected_tasks(server_fabfile):
    collection = Collection.from_module(server_fabfile)
    assert set(collection.task_names) == EXPECTED_ROOT_TASKS


def test_server_fabfile_tasks_are_task_instances(server_fabfile):
    collection = Collection.from_module(server_fabfile)
    for name, task in collection.tasks.items():
        assert isinstance(task, Task)


def test_server_fabfile_tasks_have_docstrings(server_fabfile):
    collection = Collection.from_module(server_fabfile)
    # todos os comandos "de verdade" documentam o que fazem, exceto login
    # (obviamente auto explicativo) -- garante que ninguém apague as
    # docstrings usadas por `fab --list`.
    for name, task in collection.tasks.items():
        assert task.__doc__, "task {0} está sem docstring".format(name)


def test_client_fabfile_exposes_expected_tasks(client_fabfile):
    collection = Collection.from_module(client_fabfile)
    assert set(collection.task_names) == EXPECTED_PROJETO_TASKS


def test_client_fabfile_has_no_duplicate_definitions(client_fabfile):
    # regressão: o fabfile original tinha `commit_all` e `test` definidos
    # duas vezes (a segunda definição sobrescrevia a primeira silenciosamente)
    import ast
    import inspect

    source = inspect.getsource(client_fabfile)
    tree = ast.parse(source)
    top_level_defs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    duplicates = {name for name in top_level_defs if top_level_defs.count(name) > 1}
    assert not duplicates, "funções duplicadas no fabfile: {0}".format(duplicates)


def test_client_get_app_type_normalization(client_fabfile):
    assert client_fabfile._get_app_type("python") == "python"
    assert client_fabfile._get_app_type("django") == "python"
    assert client_fabfile._get_app_type("php") == "php"
    assert client_fabfile._get_app_type("laravel") == "php"
    assert client_fabfile._get_app_type("npm") == "npm"
    assert client_fabfile._get_app_type("node") == "npm"
    assert client_fabfile._get_app_type("nodejs") == "npm"


def test_client_get_app_type_uses_global_setting(client_fabfile, monkeypatch):
    monkeypatch.setattr(client_fabfile, "app_type", "npm")
    assert client_fabfile._get_app_type() == "npm"

    monkeypatch.setattr(client_fabfile, "app_type", "php")
    assert client_fabfile._get_app_type() == "php"


def test_client_deploy_dispatches_to_specific_deployer(client_fabfile, monkeypatch):
    calls = []
    monkeypatch.setattr(client_fabfile, "deploy_python", lambda c: calls.append("python"))
    monkeypatch.setattr(client_fabfile, "deploy_php", lambda c: calls.append("php"))
    monkeypatch.setattr(client_fabfile, "deploy_npm", lambda c: calls.append("npm"))

    fake_conn = object()
    monkeypatch.setattr(client_fabfile, "get_connection", lambda: fake_conn)

    client_fabfile.deploy(Context(), app_type="python")
    client_fabfile.deploy(Context(), app_type="php")
    client_fabfile.deploy(Context(), app_type="npm")

    assert calls == ["python", "php", "npm"]


class _FakeResult:
    def __init__(self, ok, stdout=""):
        self.ok = ok
        self.failed = not ok
        self.stdout = stdout


def test_project_has_celery_detects_requirements_txt(client_fabfile):
    class FakeConn:
        def run(self, cmd, warn=True, hide=True):
            return _FakeResult(ok="requirements.txt" in cmd)

    assert client_fabfile._project_has_celery(FakeConn(), "/home/site/project") is True


def test_project_has_celery_false_when_not_mentioned(client_fabfile):
    class FakeConn:
        def run(self, cmd, warn=True, hide=True):
            return _FakeResult(ok=False)

    assert client_fabfile._project_has_celery(FakeConn(), "/home/site/project") is False


def test_restart_falls_back_to_plain_program_name_when_group_missing(client_fabfile, monkeypatch):
    # regressão: antes do fallback, `fab restart` travava (Failure) num servidor
    # onde o Celery ainda não foi configurado via fix-supervisor/setup-celery, já
    # que o grupo "{username}:*" só existe depois disso.
    calls = []

    class FakeConn:
        def run(self, cmd, warn=False):
            calls.append(cmd)
            return _FakeResult(ok=":*" not in cmd)

    monkeypatch.setattr(client_fabfile, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(client_fabfile, "username", "meusite")

    client_fabfile.restart(Context())

    assert calls == [
        "supervisorctl restart meusite:*",
        "supervisorctl restart meusite",
    ]


def test_restart_does_not_fallback_when_group_restart_succeeds(client_fabfile, monkeypatch):
    calls = []

    class FakeConn:
        def run(self, cmd, warn=False):
            calls.append(cmd)
            return _FakeResult(ok=True)

    monkeypatch.setattr(client_fabfile, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(client_fabfile, "username", "meusite")

    client_fabfile.restart(Context())

    assert calls == ["supervisorctl restart meusite:*"]


def test_get_root_connection_defaults_to_root_user(client_fabfile, monkeypatch):
    monkeypatch.setattr(client_fabfile, "host", "203.0.113.10")
    monkeypatch.setattr(client_fabfile, "username", "meusite")
    client_fabfile.get_root_connection.cache_clear()

    conn = client_fabfile.get_root_connection()

    assert conn.user == "root"
    assert conn.host == "203.0.113.10"
    client_fabfile.get_root_connection.cache_clear()


def test_setup_celery_installs_redis_then_fixes_supervisor_with_celery_forced(client_fabfile, monkeypatch):
    calls = []
    monkeypatch.setattr(client_fabfile, "install_redis", lambda c: calls.append("redis"))
    monkeypatch.setattr(
        client_fabfile, "fix_supervisor", lambda c, celery=None: calls.append(("supervisor", celery))
    )

    client_fabfile.setup_celery(Context())

    assert calls == ["redis", ("supervisor", True)]


def test_detect_domain_ignores_static_and_media_server_names(client_fabfile):
    # ~/nginx.conf do template Python tem 3 blocos: static./media./o principal —
    # o principal vem por último e é o único que deve ser considerado.
    nginx_conf = (
        "server_name static.meusite.com;\n"
        "server_name media.meusite.com;\n"
        "server_name meusite.com www.meusite.com;\n"
    )
    main_line = [
        ln for ln in nginx_conf.splitlines()
        if "server_name " in ln and "static." not in ln and "media." not in ln
    ][0]

    class FakeConn:
        def run(self, cmd, warn=True, hide=True):
            return _FakeResult(ok=True, stdout=main_line)

    assert client_fabfile._detect_domain(FakeConn()) == "meusite.com"


def test_detect_domain_strips_leading_dot_from_php_template(client_fabfile):
    class FakeConn:
        def run(self, cmd, warn=True, hide=True):
            return _FakeResult(ok=True, stdout="server_name .meusite.com;")

    assert client_fabfile._detect_domain(FakeConn()) == "meusite.com"


def test_detect_domain_returns_none_when_nginx_conf_missing(client_fabfile):
    class FakeConn:
        def run(self, cmd, warn=True, hide=True):
            return _FakeResult(ok=False, stdout="")

    assert client_fabfile._detect_domain(FakeConn()) is None


def test_health_check_waits_then_reports_success_on_2xx(client_fabfile, monkeypatch):
    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

    calls = []

    class FakeConn:
        def run(self, cmd, warn=True, hide=True):
            calls.append(cmd)
            return _FakeResult(ok=True, stdout="200")

    monkeypatch.setattr(client_fabfile, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(client_fabfile, "_detect_domain", lambda conn: "meusite.com")

    result = client_fabfile.health_check(Context(), wait=1)

    assert result is True
    assert sleep_calls == [1]
    assert "meusite.com" in calls[0]
    assert "--resolve meusite.com:80:127.0.0.1" in calls[0]


def test_health_check_reports_failure_on_non_2xx_3xx(client_fabfile, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    class FakeConn:
        def run(self, cmd, warn=True, hide=True):
            return _FakeResult(ok=True, stdout="502")

    monkeypatch.setattr(client_fabfile, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(client_fabfile, "_detect_domain", lambda conn: "meusite.com")

    result = client_fabfile.health_check(Context(), wait=0)

    assert result is False


def test_health_check_skips_when_domain_not_detected(client_fabfile, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setattr(client_fabfile, "get_connection", lambda: object())
    monkeypatch.setattr(client_fabfile, "_detect_domain", lambda conn: None)

    result = client_fabfile.health_check(Context(), wait=0)

    assert result is None


def test_deploy_python_runs_health_check_at_the_end(client_fabfile, monkeypatch):
    calls = []
    for name in (
        "pull", "push", "remote_pull", "update_requirements", "npm_build",
        "remote_migrate_all", "translate_remote", "collectstatic", "restart",
    ):
        monkeypatch.setattr(client_fabfile, name, lambda c, n=name: calls.append(n))
    monkeypatch.setattr(client_fabfile, "health_check", lambda c: calls.append("health_check"))

    client_fabfile.deploy_python(Context())

    assert calls[-1] == "health_check"
