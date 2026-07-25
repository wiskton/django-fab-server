import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load_module(path, name):
    """Carrega um fabfile.py como módulo Python isolado, sem precisar
    manipular sys.path (os dois fabfiles do projeto se chamam "fabfile")."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def server_fabfile():
    """O fabfile.py que provisiona o servidor (server/fabfile.py)."""
    return _load_module(ROOT / "server" / "fabfile.py", "server_fabfile")


@pytest.fixture(scope="session")
def client_fabfile():
    """O fabfile.py feito para ser copiado para dentro de outro projeto
    (client/fabfile.py)."""
    return _load_module(ROOT / "client" / "fabfile.py", "client_fabfile")


@pytest.fixture()
def inc_dir():
    return ROOT / "server" / "inc"
