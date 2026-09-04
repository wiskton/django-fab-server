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
    "fix-supervisor", "enable-ssl",
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
