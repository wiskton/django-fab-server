"""Testes do suporte multi-distro do server/fabfile.py (Ubuntu/Debian,
Fedora, CentOS Stream/RHEL, Arch Linux) -- garante que nenhuma família fica
sem pacote/serviço mapeado e que `_install`/`_ensure_epel` chamam o
gerenciador de pacotes certo, sem precisar de um servidor real de cada
distro."""
import pytest
from fabric import Connection
from invoke import Context

_FAMILIES = ("debian", "fedora", "rhel", "arch")


class _FakeResult:
    def __init__(self, ok):
        self.ok = ok

_BY_FAMILY_TABLES = (
    "_BUILD_PACKAGES_BY_FAMILY",
    "_PYTHON_PACKAGES_BY_FAMILY",
    "_DB_PACKAGES_BY_FAMILY",
    "_DB_SERVICE_BY_FAMILY",
    "_PHP_PACKAGES_BY_FAMILY",
    "_PHP_FPM_SOCK_BY_FAMILY",
    "_PHP_INI_PATH_BY_FAMILY",
    "_NGINX_USER_BY_FAMILY",
    "_SUPERVISOR_SERVICE_BY_FAMILY",
    "_SUPERVISOR_CONF_PATH_BY_FAMILY",
    "_FTP_BY_FAMILY",
    "_CERTBOT_PACKAGES_BY_FAMILY",
    "_NODE_PACKAGES_BY_FAMILY",
)


@pytest.fixture()
def _reset_os_family(server_fabfile):
    try:
        yield
    finally:
        server_fabfile.cfg.os_family = "debian"
        server_fabfile._ensure_epel_once.cache_clear()


@pytest.mark.parametrize("table_name", _BY_FAMILY_TABLES)
def test_by_family_tables_cover_every_family(server_fabfile, table_name):
    table = getattr(server_fabfile, table_name)
    assert set(table.keys()) == set(_FAMILIES), (
        "{0} não cobre todas as famílias suportadas".format(table_name)
    )


def test_ftp_by_family_uses_vsftpd_only_on_arch(server_fabfile):
    ftp = server_fabfile._FTP_BY_FAMILY
    assert ftp["arch"]["package"] == "vsftpd"
    assert ftp["arch"]["template"] == "vsftpd.conf"
    for family in ("debian", "fedora", "rhel"):
        assert ftp[family]["package"] == "proftpd"


def test_db_service_by_family_is_mariadb_outside_debian(server_fabfile):
    service = server_fabfile._DB_SERVICE_BY_FAMILY
    assert service["debian"] == "mysql"
    for family in ("fedora", "rhel", "arch"):
        assert service[family] == "mariadb"


@pytest.mark.parametrize(
    "family,expected_prefix",
    [
        ("debian", "apt -y install"),
        ("fedora", "dnf -y install"),
        ("rhel", "dnf -y install"),
        ("arch", "pacman -S --noconfirm --needed"),
    ],
)
def test_install_dispatches_to_the_right_package_manager(
    server_fabfile, monkeypatch, _reset_os_family, family, expected_prefix
):
    sudo_calls = []
    monkeypatch.setattr(
        Connection,
        "sudo",
        lambda _self, command, *a, **kw: sudo_calls.append(command),
    )
    server_fabfile.get_connection.cache_clear()
    server_fabfile.cfg.os_family = family

    server_fabfile._install(None, "algum-pacote")

    assert sudo_calls == ["{0} algum-pacote".format(expected_prefix)]
    server_fabfile.get_connection.cache_clear()


def test_install_rejects_unknown_os_family(server_fabfile, _reset_os_family):
    server_fabfile.cfg.os_family = "solaris"
    with pytest.raises(ValueError):
        server_fabfile._install(None, "algum-pacote")


@pytest.mark.parametrize("family", ["debian", "fedora", "arch"])
def test_ensure_epel_is_noop_outside_rhel(
    server_fabfile, monkeypatch, _reset_os_family, family
):
    sudo_calls = []
    monkeypatch.setattr(
        Connection,
        "sudo",
        lambda _self, command, *a, **kw: sudo_calls.append(command),
    )
    server_fabfile.get_connection.cache_clear()
    server_fabfile.cfg.os_family = family

    server_fabfile._ensure_epel_once.cache_clear()
    server_fabfile._ensure_epel(None)

    assert sudo_calls == []
    server_fabfile.get_connection.cache_clear()


def test_ensure_epel_installs_epel_release_on_rhel(
    server_fabfile, monkeypatch, _reset_os_family
):
    sudo_calls = []
    monkeypatch.setattr(
        Connection,
        "sudo",
        lambda _self, command, *a, **kw: sudo_calls.append(command),
    )
    server_fabfile.get_connection.cache_clear()
    server_fabfile.cfg.os_family = "rhel"

    server_fabfile._ensure_epel_once.cache_clear()
    server_fabfile._ensure_epel(None)

    assert sudo_calls == ["dnf -y install epel-release"]
    server_fabfile.get_connection.cache_clear()


def test_ensure_epel_accepts_unhashable_context(
    server_fabfile, monkeypatch, _reset_os_family
):
    # regressão: o Context do Fabric/Invoke não é hashable (TypeError:
    # unhashable type: 'Context' em produção, com `fab newserver` de
    # verdade) -- _ensure_epel não pode usar lru_cache direto sobre `c`
    sudo_calls = []
    monkeypatch.setattr(
        Connection,
        "sudo",
        lambda _self, command, *a, **kw: sudo_calls.append(command),
    )
    server_fabfile.get_connection.cache_clear()
    server_fabfile.cfg.os_family = "rhel"
    server_fabfile._ensure_epel_once.cache_clear()

    server_fabfile._ensure_epel({})  # dict, assim como Context, não é hashable

    assert sudo_calls == ["dnf -y install epel-release"]
    server_fabfile.get_connection.cache_clear()


@pytest.mark.parametrize(
    "family,expected_check",
    [
        ("debian", "dpkg -s mysql-server"),
        ("fedora", "rpm -q mariadb-server"),
        ("rhel", "rpm -q mariadb-server"),
        ("arch", "pacman -Qi mariadb"),
    ],
)
def test_package_installed_uses_the_right_check_per_family(
    server_fabfile, monkeypatch, _reset_os_family, family, expected_check
):
    run_calls = []

    def fake_run(_self, command, **kwargs):
        run_calls.append((command, kwargs))
        return _FakeResult(ok=True)

    monkeypatch.setattr(Connection, "run", fake_run)
    server_fabfile.get_connection.cache_clear()
    server_fabfile.cfg.os_family = family

    main_package = server_fabfile._DB_PACKAGES_BY_FAMILY[family].split()[0]
    assert server_fabfile._package_installed(main_package) is True

    command, kwargs = run_calls[0]
    assert command == expected_check
    assert kwargs.get("warn") is True
    assert kwargs.get("hide") is True
    server_fabfile.get_connection.cache_clear()


def test_mysql_server_skips_install_and_password_when_already_installed(
    server_fabfile, monkeypatch, _reset_os_family
):
    # regressão: rodar `fab newserver`/`fab mysql-server` de novo num
    # servidor que já tem o banco instalado não pode gerar/trocar a senha
    # do root -- a senha anotada da primeira vez pararia de funcionar
    server_fabfile.cfg.os_family = "debian"
    server_fabfile.cfg.db_password = ""

    sudo_calls = []
    monkeypatch.setattr(
        Connection, "sudo", lambda _self, cmd, *a, **kw: sudo_calls.append(cmd)
    )
    monkeypatch.setattr(
        Connection, "run", lambda _self, cmd, **kw: _FakeResult(ok=True)
    )

    def _fail_if_asked(prompt=""):
        raise AssertionError("não deveria pedir senha/confirmação: {0}".format(prompt))

    monkeypatch.setattr("builtins.input", _fail_if_asked)
    server_fabfile.get_connection.cache_clear()

    try:
        server_fabfile.mysql_server(Context())
    finally:
        server_fabfile.get_connection.cache_clear()
        server_fabfile.cfg.db_password = ""

    assert sudo_calls == []
    assert server_fabfile.cfg.db_password == ""
