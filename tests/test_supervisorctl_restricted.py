from importlib.machinery import SourceFileLoader
from pathlib import Path
import types
import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "server" / "inc" / "supervisorctl-restricted"


@pytest.fixture(scope="session")
def restricted_module():
    loader = SourceFileLoader("supervisorctl_restricted", str(SCRIPT_PATH))
    mod = types.ModuleType(loader.name)
    loader.exec_module(mod)
    return mod


def test_is_target_allowed_for_own_processes(restricted_module):
    # Processo direto com o mesmo nome do usuário
    assert restricted_module.is_target_allowed("userA", "userA") is True
    # Grupo inteiro do usuário
    assert restricted_module.is_target_allowed("userA", "userA:*") is True
    # Processos individuais do projeto
    assert restricted_module.is_target_allowed("userA", "userA_gunicorn") is True
    assert restricted_module.is_target_allowed("userA", "userA_worker") is True
    assert restricted_module.is_target_allowed("userA", "userA_beat") is True
    assert restricted_module.is_target_allowed("userA", "userA_node") is True
    # Subprocesso dentro de grupo
    assert restricted_module.is_target_allowed("userA", "userA:worker") is True


def test_is_target_forbidden_for_other_users_and_global_targets(restricted_module):
    # Proibido: outro usuário
    assert restricted_module.is_target_allowed("userA", "userB") is False
    assert restricted_module.is_target_allowed("userA", "userB:*") is False
    assert restricted_module.is_target_allowed("userA", "userB_gunicorn") is False
    assert restricted_module.is_target_allowed("userA", "userB:worker") is False

    # Proibido: alvos globais
    assert restricted_module.is_target_allowed("userA", "all") is False
    assert restricted_module.is_target_allowed("userA", "*") is False

    # Proibido: vazio ou tipos inválidos
    assert restricted_module.is_target_allowed("userA", "") is False
    assert restricted_module.is_target_allowed("userA", None) is False

    # Proibido: injeção de shell e caracteres perigosos
    assert restricted_module.is_target_allowed("userA", "userA; rm -rf /") is False
    assert restricted_module.is_target_allowed("userA", "userA && reboot") is False
    assert restricted_module.is_target_allowed("userA", "userA | cat") is False
    assert restricted_module.is_target_allowed("userA", "../userB") is False
    assert restricted_module.is_target_allowed("userA", "userA$USER") is False


def test_caller_authorization_userA_can_manage_userA(restricted_module, monkeypatch):
    monkeypatch.setattr(restricted_module, "get_calling_user", lambda: "userA")
    calls = []
    monkeypatch.setattr(
        restricted_module,
        "run_supervisorctl",
        lambda action, target: calls.append((action, target)) or 0,
    )

    exit_code = restricted_module.main(["userA", "restart", "userA:*"])
    assert exit_code == 0
    assert calls == [("restart", "userA:*")]


def test_caller_authorization_userA_cannot_manage_userB(restricted_module, monkeypatch, capsys):
    monkeypatch.setattr(restricted_module, "get_calling_user", lambda: "userA")
    calls = []
    monkeypatch.setattr(
        restricted_module,
        "run_supervisorctl",
        lambda action, target: calls.append((action, target)) or 0,
    )

    exit_code = restricted_module.main(["userB", "restart"])
    assert exit_code == 13  # Permission denied
    assert calls == []

    captured = capsys.readouterr()
    assert "ERRO DE SEGURANÇA" in captured.err
    assert "userA" in captured.err
    assert "userB" in captured.err


def test_caller_authorization_root_can_manage_any_project(restricted_module, monkeypatch):
    monkeypatch.setattr(restricted_module, "get_calling_user", lambda: "root")
    calls = []
    monkeypatch.setattr(
        restricted_module,
        "run_supervisorctl",
        lambda action, target: calls.append((action, target)) or 0,
    )

    exit_code = restricted_module.main(["userB", "restart", "userB_gunicorn"])
    assert exit_code == 0
    assert calls == [("restart", "userB_gunicorn")]


def test_caller_inferred_from_calling_user_when_omitted(restricted_module, monkeypatch):
    monkeypatch.setattr(restricted_module, "get_calling_user", lambda: "userA")
    calls = []
    monkeypatch.setattr(
        restricted_module,
        "run_supervisorctl",
        lambda action, target: calls.append((action, target)) or 0,
    )

    # Chamada: supervisorctl-restricted restart
    exit_code = restricted_module.main(["restart"])
    assert exit_code == 0
    assert calls == [("restart", "userA:*")]


def test_disallowed_actions_are_strictly_rejected(restricted_module, monkeypatch, capsys):
    monkeypatch.setattr(restricted_module, "get_calling_user", lambda: "userA")
    calls = []
    monkeypatch.setattr(
        restricted_module,
        "run_supervisorctl",
        lambda action, target: calls.append((action, target)) or 0,
    )

    for dangerous_action in ("shutdown", "reload", "update", "reread", "pid", "clear", "maint"):
        exit_code = restricted_module.main(["userA", dangerous_action])
        assert exit_code == 2
        assert calls == []
        captured = capsys.readouterr()
        assert "não permitida" in captured.err


def test_help_flag_displays_usage(restricted_module, capsys):
    assert restricted_module.main(["--help"]) == 0
    captured = capsys.readouterr()
    assert "Uso:" in captured.out
