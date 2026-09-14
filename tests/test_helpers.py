import pytest
from fabric import Connection


def test_create_password_respects_length(server_fabfile):
    assert len(server_fabfile.create_password(12)) == 12
    assert len(server_fabfile.create_password(20)) == 20


def test_create_password_uses_expected_charset(server_fabfile):
    allowed = set(
        "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!@#%^*_-+="
    )
    senha = server_fabfile.create_password(200)
    assert set(senha) <= allowed


def test_create_password_is_random(server_fabfile):
    passwords = {server_fabfile.create_password(16) for _ in range(20)}
    assert len(passwords) > 1


def test_create_password_has_minimum_length(server_fabfile):
    """tamanho < 4 é elevado pra 4, já que as 4 categorias obrigatórias precisam de espaço."""
    assert len(server_fabfile.create_password(1)) == 4


@pytest.mark.parametrize("tamanho", [12, 16, 20, 50])
def test_create_password_always_has_all_character_classes(server_fabfile, tamanho):
    """Repete várias vezes pra garantir que a mistura de categorias não depende de sorte
    (diferente da versão antiga, que sorteava tudo de um pool único)."""
    lower = set("abcdefghijklmnopqrstuvwxyz")
    upper = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    digits = set("0123456789")
    special = set("!@#%^*_-+=")

    for _ in range(50):
        senha = server_fabfile.create_password(tamanho)
        assert len(senha) == tamanho
        assert any(c in lower for c in senha), senha
        assert any(c in upper for c in senha), senha
        assert any(c in digits for c in senha), senha
        assert any(c in special for c in senha), senha


@pytest.mark.parametrize("color_fn", ["green", "red", "yellow", "white"])
def test_color_helpers_wrap_text_in_ansi_codes(server_fabfile, color_fn):
    fn = getattr(server_fabfile, color_fn)
    result = fn("mensagem")
    assert "mensagem" in result
    assert result.startswith("\033[")
    assert result.endswith("\033[0m")


@pytest.mark.parametrize(
    "user_input,default,expected",
    [
        ("y", True, True),
        ("n", True, False),
        ("yes", False, True),
        ("no", False, False),
        ("", True, True),
        ("", False, False),
    ],
)
def test_confirm(server_fabfile, monkeypatch, user_input, default, expected):
    monkeypatch.setattr("builtins.input", lambda prompt="": user_input)
    assert server_fabfile.confirm("continuar?", default=default) is expected


def test_config_supports_attribute_and_item_access(server_fabfile):
    cfg = server_fabfile.Config(foo="bar")
    assert cfg.foo == "bar"
    assert cfg["foo"] == "bar"

    cfg.baz = "qux"
    assert cfg["baz"] == "qux"


def test_config_missing_attribute_raises_attribute_error(server_fabfile):
    cfg = server_fabfile.Config()
    with pytest.raises(AttributeError):
        cfg.nao_existe


def test_get_connection_is_memoized(server_fabfile):
    server_fabfile.get_connection.cache_clear()
    conn1 = server_fabfile.get_connection()
    conn2 = server_fabfile.get_connection()
    assert conn1 is conn2
    server_fabfile.get_connection.cache_clear()


def test_write_file_uploads_utf8_bytes_not_str(server_fabfile, monkeypatch):
    # regressão: paramiko calcula o tamanho do put() a partir de .tell() do
    # arquivo enviado -- com StringIO (modo texto), .tell() conta
    # caracteres, não bytes. Os templates de server/inc/ têm comentários em
    # português com acento (ex: "versão" em nginx_server.conf), que ocupam
    # mais bytes que caracteres em UTF-8, e o put falhava com
    # "OSError: size mismatch in put!". write_file() precisa mandar um
    # BytesIO já codificado em UTF-8.
    captured = {}

    def fake_put(_self, local, remote=None, **kwargs):
        captured["local"] = local

    monkeypatch.setattr(Connection, "put", fake_put)
    monkeypatch.setattr(Connection, "sudo", lambda _self, *a, **kw: None)
    server_fabfile.get_connection.cache_clear()
    server_fabfile.cfg.conta = "acme"
    server_fabfile.cfg.dominio = "acme.com.br"
    server_fabfile.cfg.nginx_user = "www-data"

    try:
        server_fabfile.write_file("nginx_server.conf", "/etc/nginx/nginx.conf")
    finally:
        server_fabfile.get_connection.cache_clear()

    content = captured["local"].read()
    assert isinstance(content, bytes)
    assert "versão" in content.decode("utf-8")
