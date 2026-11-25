import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

MAIN_SCRIPT = str(Path(__file__).resolve().parents[1] / "src" / "main.py")

PAGES = [
    "Dashboard",
    "Clientes",
    "Nova Visita",
    "Histórico de Visitas",
    "Fotografias",
    "Relatórios",
    "Alterar Senha",
    "Gerenciar Usuários",
]


@pytest.fixture(autouse=True)
def isolated_users(tmp_path, monkeypatch):
    """Mantém os testes de interface isolados do cadastro local real."""
    import src.auth_manager as auth

    monkeypatch.setattr(auth, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(auth, "USERS_FILE", str(tmp_path / "users.json"))
    monkeypatch.delenv(auth.ADMIN_ACCESS_CODE_ENV, raising=False)
    auth.init_db()
    yield


def _authenticated_app():
    app = AppTest.from_file(MAIN_SCRIPT, default_timeout=60)
    app.session_state["authenticated"] = True
    app.session_state["username"] = "Cláudio Norte"
    app.session_state["user_id"] = "usr_claudio_norte"
    app.session_state["user_role"] = "administrador"
    app.session_state["is_admin"] = True
    app.session_state["admin_authorized"] = True
    app.session_state["admin_authorized_at"] = "2026-11-24 22:00:00"
    return app


def test_login_screen_renders_passwordless_selection_with_official_logo():
    app = AppTest.from_file(MAIN_SCRIPT, default_timeout=60)
    app.run()
    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["authenticated"] is False

    labels = [widget.label for widget in app.text_input]
    assert "Pesquisar usuário" in labels
    assert "Senha" not in labels
    assert "E-mail ou usuário" not in labels
    assert app.selectbox(key="login_user") is not None

    markup = "\n".join(str(item.value) for item in app.markdown)
    assert "data:image/jpeg;base64" in markup


def test_login_blocks_empty_selection():
    app = AppTest.from_file(MAIN_SCRIPT, default_timeout=60)
    app.run()
    app.button(key="login_submit").click()
    app.run()
    assert not app.exception, [error.value for error in app.exception]
    assert any(
        "Selecione seu nome" in str(getattr(err, "value", ""))
        for err in app.error
    )


def test_common_user_logs_in_without_password():
    app = AppTest.from_file(MAIN_SCRIPT, default_timeout=60)
    app.run()
    app.selectbox(key="login_user").set_value("usr_ana_norte")
    app.button(key="login_submit").click()
    app.run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["authenticated"] is True
    assert app.session_state["username"] == "Ana.norte"
    assert app.session_state["user_id"] == "usr_ana_norte"
    assert app.session_state["is_admin"] is False
    assert app.session_state["admin_authorized"] is False
    assert app.session_state["current_page"] == "Dashboard"


def test_admin_login_requires_server_side_authorization(monkeypatch):
    monkeypatch.setenv("ACN_ADMIN_ACCESS_CODE", "segredo-adm")

    app = AppTest.from_file(MAIN_SCRIPT, default_timeout=60)
    app.run()
    app.selectbox(key="login_user").set_value("usr_claudio_norte")
    app.run()

    assert app.text_input(key="login_admin_code") is not None
    app.text_input(key="login_admin_code").input("codigo-errado")
    app.button(key="login_submit").click()
    app.run()

    assert app.session_state["authenticated"] is False
    assert any(
        "inválido" in str(getattr(err, "value", "")) for err in app.error
    )


def test_admin_login_with_valid_code_grants_admin_permission(monkeypatch):
    monkeypatch.setenv("ACN_ADMIN_ACCESS_CODE", "segredo-adm")

    app = AppTest.from_file(MAIN_SCRIPT, default_timeout=60)
    app.run()
    app.selectbox(key="login_user").set_value("usr_claudio_norte")
    app.run()
    app.text_input(key="login_admin_code").input("segredo-adm")
    app.button(key="login_submit").click()
    app.run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["authenticated"] is True
    assert app.session_state["user_id"] == "usr_claudio_norte"
    assert app.session_state["is_admin"] is True
    assert app.session_state["admin_authorized"] is True


def test_admin_login_is_blocked_when_server_secret_is_missing():
    app = AppTest.from_file(MAIN_SCRIPT, default_timeout=60)
    app.run()
    app.selectbox(key="login_user").set_value("usr_claudio_norte")
    app.run()
    app.button(key="login_submit").click()
    app.run()

    assert app.session_state["authenticated"] is False
    assert any(
        "não está configurada" in str(getattr(err, "value", ""))
        for err in app.error
    )


@pytest.mark.parametrize("page", PAGES)
def test_authenticated_pages_render(page):
    app = _authenticated_app()
    app.session_state["current_page"] = page
    app.run()
    assert not app.exception, [error.value for error in app.exception]


def test_sidebar_navigation_changes_page():
    app = _authenticated_app()
    app.run()
    app.button(key="nav_Clientes").click()
    app.run()
    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["current_page"] == "Clientes"


def test_main_registers_every_navigation_page():
    import src.main as main_module
    from src.ui_components import NAV_ITEMS

    assert set(main_module.PAGE_RENDERERS) == {item[0] for item in NAV_ITEMS}


def test_feature_registry_loads_all_modules():
    from src.features import available_features, initialize_features

    loaded = initialize_features()
    assert set(loaded) == set(available_features())
    assert all(hasattr(module, "__name__") for module in loaded.values())


def test_entry_points_import_from_foreign_cwd():
    root = Path(__file__).resolve().parents[1]
    entry_points = (root / "src" / "main.py", root / "main.py")
    code = (
        "import importlib.util;"
        "spec=importlib.util.spec_from_file_location('acn_import_probe', {!r});"
        "module=importlib.util.module_from_spec(spec);"
        "spec.loader.exec_module(module);"
        "print('OK')"
    )
    for entry in entry_points:
        result = subprocess.run(
            [sys.executable, "-c", code.format(str(entry))],
            cwd=tempfile.gettempdir(),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "OK" in result.stdout
