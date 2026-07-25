"""Testes do suporte multi-distro do server/fabfile.py (Ubuntu/Debian,
Fedora, CentOS Stream/RHEL, Arch Linux) -- garante que nenhuma família fica
sem pacote/serviço mapeado e que `_install`/`_ensure_epel` chamam o
gerenciador de pacotes certo, sem precisar de um servidor real de cada
distro."""
import pytest
from fabric import Connection

_FAMILIES = ("debian", "fedora", "rhel", "arch")

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
)


@pytest.fixture()
def _reset_os_family(server_fabfile):
    try:
        yield
    finally:
        server_fabfile.cfg.os_family = "debian"
        server_fabfile._ensure_epel.cache_clear()


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

    server_fabfile._ensure_epel.cache_clear()
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

    server_fabfile._ensure_epel.cache_clear()
    server_fabfile._ensure_epel(None)

    assert sudo_calls == ["dnf -y install epel-release"]
    server_fabfile.get_connection.cache_clear()
