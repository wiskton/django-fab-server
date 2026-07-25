from invoke import Collection, Task

EXPECTED_ROOT_TASKS = {
    "adduser", "aptget", "build-local", "build-server", "delaccount",
    "dropbase", "git-local", "git-server", "listaccount", "login",
    "mysql-local", "mysql-restart", "mysql-server", "mysql-start",
    "mysql-stop", "newaccount", "newbase", "newdev", "newproject",
    "newserver", "nginx-reload", "nginx-restart", "nginx-start",
    "nginx-stop", "others-server", "proftpd-restart", "python-local",
    "python-server", "reboot", "restart", "restart-server", "start-server",
    "stop-server", "supervisor-restart", "supervisor-start",
    "supervisor-stop", "update-local", "update-server", "upgrade-local",
    "upgrade-server", "upload-public-key", "userdel",
}

EXPECTED_PROJETO_TASKS = {
    "co", "collectstatic", "commit-all", "commit-push", "compass-compile",
    "compress", "config", "createdb", "createsuperuser", "cw", "deploy",
    "gunicorn", "login", "manage", "migrate", "pull", "push",
    "remote-migrate-all", "remote-pull", "remote-test", "restart", "revert",
    "server", "test", "translate", "translate-remote", "update-requirements",
    "upload-public-key",
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
