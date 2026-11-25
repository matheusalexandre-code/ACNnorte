"""Testes do login sem senha, autorização ADM e base compartilhada."""

from pathlib import Path

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

import src.auth_manager as auth
import src.storage_manager as storage
from src.ui_components import LOGIN_LOGO_PATH

ROOT = Path(__file__).resolve().parents[1]
MAIN_SCRIPT = str(ROOT / "src" / "main.py")


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """Isola usuários e dados operacionais do cadastro/dados reais."""
    auth_dir = tmp_path / "auth"
    data_dir = tmp_path / "data"
    monkeypatch.setattr(auth, "DATA_DIR", str(auth_dir))
    monkeypatch.setattr(auth, "USERS_FILE", str(auth_dir / "users.json"))
    monkeypatch.setattr(storage, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(storage, "CLIENTS_FILE", str(data_dir / "clients.json"))
    monkeypatch.setattr(storage, "VISITS_FILE", str(data_dir / "visits.json"))
    monkeypatch.setattr(storage, "PHOTOS_DIR", str(data_dir / "photos"))
    monkeypatch.delenv(auth.ADMIN_ACCESS_CODE_ENV, raising=False)
    auth.init_db()
    storage.init_storage()
    return auth, storage


def _admin_session(app):
    app.session_state["authenticated"] = True
    app.session_state["username"] = "Cláudio Norte"
    app.session_state["user_id"] = "usr_claudio_norte"
    app.session_state["user_role"] = "administrador"
    app.session_state["is_admin"] = True
    app.session_state["admin_authorized"] = True
    app.session_state["admin_authorized_at"] = "2026-11-24 22:00:00"
    return app


def _common_session(app):
    app.session_state["authenticated"] = True
    app.session_state["username"] = "Ana.norte"
    app.session_state["user_id"] = "usr_ana_norte"
    app.session_state["user_role"] = "usuario"
    app.session_state["is_admin"] = False
    app.session_state["admin_authorized"] = False
    return app


def _widget(elements, **criteria):
    for element in elements:
        if all(
            getattr(element, key, None) == value
            for key, value in criteria.items()
        ):
            return element
    raise AssertionError(f"Widget não encontrado: {criteria}")


# ---------------------------------------------------------------------------
# 1-3. Usuários iniciais, idempotência, identificadores e localização
# ---------------------------------------------------------------------------


def test_initial_users_are_created_once_with_stable_ids(isolated_store):
    users = auth.load_users()

    assert set(auth.DEFAULT_USER_NAMES).issubset(set(users))
    assert users["Ana.norte"]["user_id"] == "usr_ana_norte"
    assert users["Nadir Norte"]["user_id"] == "usr_nadir_norte"
    assert users["Cláudio Norte"]["user_id"] == "usr_claudio_norte"
    assert users["Ana.norte"]["is_admin"] is False
    assert users["Nadir Norte"]["is_admin"] is False
    assert users["Cláudio Norte"]["is_admin"] is True

    for _ in range(4):
        auth.init_db()
    assert len(auth.load_users()) == 3


def test_existing_users_are_preserved_and_role_conflict_is_corrected(
    isolated_store,
):
    users = auth.load_users()
    original_password = users["Ana.norte"]["password"]
    original_created_at = users["Ana.norte"]["created_at"]

    # Conflito real encontrado no cadastro local: Ana era administradora.
    users["Ana.norte"]["is_admin"] = True
    auth.save_users(users)
    auth.add_user("Ana Júlia")

    auth.init_db()
    after = auth.load_users()

    assert "Ana Júlia" in after
    assert after["Ana.norte"]["is_admin"] is False
    assert after["Ana.norte"]["password"] == original_password
    assert after["Ana.norte"]["created_at"] == original_created_at


def test_users_can_be_located_by_name_and_listed_for_login(isolated_store):
    auth.add_user("Ana Júlia")

    login_users = auth.list_login_users()
    names = [user["name"] for user in login_users]

    assert names == sorted(names, key=str.casefold)
    assert "Ana Júlia" in names
    assert all(user["id"] for user in login_users)

    key, record = auth.find_user_record("Nadir Norte")
    assert key == "Nadir Norte"
    assert record["user_id"] == "usr_nadir_norte"
    assert auth.get_active_user_by_id("usr_claudio_norte")["is_admin"] is True


def test_duplicate_and_empty_names_are_rejected(isolated_store):
    ok, message = auth.add_user("Nadir Norte")
    assert ok is False
    assert "já existe" in message.lower()

    ok, message = auth.add_user("   ")
    assert ok is False
    assert "nome" in message.lower()


# ---------------------------------------------------------------------------
# 4-8. Login sem senha, identificação, autorização e cadastro pelo ADM
# ---------------------------------------------------------------------------


def test_common_login_has_no_password_field_and_sets_identity(isolated_store):
    app = AppTest.from_file(MAIN_SCRIPT, default_timeout=60)
    app.run()

    labels = [widget.label for widget in app.text_input]
    assert "Pesquisar usuário" in labels
    assert "Senha" not in labels

    app.selectbox(key="login_user").set_value("usr_ana_norte")
    app.button(key="login_submit").click()
    app.run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["authenticated"] is True
    assert app.session_state["username"] == "Ana.norte"
    assert app.session_state["user_id"] == "usr_ana_norte"
    assert app.session_state["is_admin"] is False


def test_admin_code_is_validated_only_with_server_configuration(
    isolated_store, monkeypatch
):
    assert auth.admin_access_configured() is False
    assert auth.verify_admin_access_code("qualquer") is False

    monkeypatch.setenv(auth.ADMIN_ACCESS_CODE_ENV, "codigo-secreto")
    assert auth.admin_access_configured() is True
    assert auth.verify_admin_access_code("codigo-secreto") is True
    assert auth.verify_admin_access_code("codigo-errado") is False


def test_common_user_cannot_reach_admin_management(isolated_store):
    app = _common_session(AppTest.from_file(MAIN_SCRIPT, default_timeout=60))
    app.session_state["current_page"] = "Gerenciar Usuários"
    app.run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["current_page"] == "Dashboard"
    assert all(button.key != "nav_Gerenciar Usuários" for button in app.button)


def test_admin_can_register_common_user_without_password(isolated_store, monkeypatch):
    monkeypatch.setenv(auth.ADMIN_ACCESS_CODE_ENV, "codigo-secreto")
    app = _admin_session(AppTest.from_file(MAIN_SCRIPT, default_timeout=60))
    app.session_state["current_page"] = "Gerenciar Usuários"
    app.run()

    assert not app.exception, [error.value for error in app.exception]
    name_input = _widget(app.text_input, label="Nome do Usuário")
    name_input.input("Carlos Norte")
    _widget(app.button, label="Cadastrar Usuário").click()
    app.run()

    users = auth.load_users()
    assert "Carlos Norte" in users
    assert users["Carlos Norte"]["is_admin"] is False
    assert users["Carlos Norte"]["user_id"].startswith("usr_")
    assert any(
        user["name"] == "Carlos Norte" for user in auth.list_login_users()
    )


def test_forged_admin_session_without_authorization_is_denied(isolated_store):
    """Marcar is_admin no estado da sessão não basta sem autorização do servidor."""
    app = AppTest.from_file(MAIN_SCRIPT, default_timeout=60)
    app.session_state["authenticated"] = True
    app.session_state["username"] = "Cláudio Norte"
    app.session_state["user_id"] = "usr_claudio_norte"
    app.session_state["is_admin"] = True
    app.session_state["admin_authorized"] = False
    app.session_state["current_page"] = "Gerenciar Usuários"
    app.run()

    assert app.session_state["is_admin"] is False
    assert app.session_state["current_page"] == "Dashboard"


def test_logout_clears_identification_and_returns_to_login(isolated_store):
    app = AppTest.from_file(MAIN_SCRIPT, default_timeout=60)
    app.run()
    app.selectbox(key="login_user").set_value("usr_nadir_norte")
    app.button(key="login_submit").click()
    app.run()
    assert app.session_state["authenticated"] is True

    app.button(key="logout").click()
    app.run()

    assert app.session_state["authenticated"] is False
    assert app.session_state.get("user_id") is None
    assert app.selectbox(key="login_user") is not None


# ---------------------------------------------------------------------------
# 11-14. Compartilhamento e persistência dos registros
# ---------------------------------------------------------------------------


def test_clients_and_visits_are_shared_between_users(isolated_store):
    _auth, store = isolated_store
    ok, client_id, _message = store.add_client(
        "Empresa Norte",
        "00.000.000/0001-00",
        "Rua A, 1",
        "Responsável",
        "(91) 99999-9999",
        "contato@empresa.com",
    )
    assert ok is True

    ok, visit_id, _message = store.add_visit(
        client_id,
        "Ana.norte",
        "2026-11-24",
        "Finalizada",
        worker_name="Trabalhador Norte",
        sst_checklist={"elevacao": "ok"},
        sst_observations={"elevacao": "sem restrição"},
    )
    assert ok is True
    store.save_visit_signature(visit_id, "technical", name="Ana.norte")
    ok, _path, _message = store.save_worker_photo(
        visit_id, b"conteudo-foto", "foto.jpg"
    )
    assert ok is True

    # Outro usuário lê exatamente os mesmos registros, sem filtro por autor.
    clients_as_nadir = store.load_clients()
    visits_as_nadir = store.load_visits()

    assert client_id in clients_as_nadir
    assert visit_id in visits_as_nadir
    visit = visits_as_nadir[visit_id]
    assert visit["client_id"] == client_id
    assert visit["technician"] == "Ana.norte"
    assert visit["sst_checklist"]["elevacao"] == "ok"
    assert visit["sst_observations"]["elevacao"] == "sem restrição"
    assert visit["signatures"]["technical"]["name"] == "Ana.norte"
    assert Path(visit["worker"]["photo_path"]).exists()

    # Os dados continuam persistidos após recarregar do armazenamento local.
    assert visit_id in store.load_visits()
    assert client_id in store.load_clients()


# ---------------------------------------------------------------------------
# Logo oficial
# ---------------------------------------------------------------------------


def test_login_logo_is_the_original_jpeg_with_preserved_aspect():
    assert LOGIN_LOGO_PATH.exists()
    assert LOGIN_LOGO_PATH.suffix.lower() == ".jpeg"

    with Image.open(LOGIN_LOGO_PATH) as image:
        assert image.size == (1600, 405)
        assert abs(image.width / image.height - 3.95) < 0.02
        assert image.mode == "RGB"
