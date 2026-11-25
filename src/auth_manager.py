import binascii
import hashlib
import hmac
import json
import os
import re
import unicodedata
import uuid
from datetime import datetime


DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
USERS_FILE = os.path.join(DATA_DIR, "users.json")

# Usuários iniciais obrigatórios. O identificador interno é estável e não muda
# quando o nome de exibição é alterado no futuro.
DEFAULT_USERS = (
    {"name": "Ana.norte", "user_id": "usr_ana_norte", "is_admin": False},
    {"name": "Nadir Norte", "user_id": "usr_nadir_norte", "is_admin": False},
    {"name": "Cláudio Norte", "user_id": "usr_claudio_norte", "is_admin": True},
)
DEFAULT_USER_NAMES = tuple(item["name"] for item in DEFAULT_USERS)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password: str, salt: bytes = None) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with salt."""
    if salt is None:
        salt = os.urandom(16)
    pwdhash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return (
        binascii.hexlify(salt).decode("ascii")
        + ":"
        + binascii.hexlify(pwdhash).decode("ascii")
    )


def verify_password(stored_password: str, provided_password: str) -> bool:
    """Verify a stored password against a provided password."""
    try:
        salt_hex, pwdhash_hex = stored_password.split(":")
        salt = binascii.unhexlify(salt_hex.encode("ascii"))
        pwdhash = binascii.unhexlify(pwdhash_hex.encode("ascii"))
        new_pwdhash = hashlib.pbkdf2_hmac(
            "sha256", provided_password.encode("utf-8"), salt, 100000
        )
        return hmac.compare_digest(pwdhash, new_pwdhash)
    except Exception:
        return False


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value).strip("_").lower()
    return slug or "usuario"


def _existing_user_ids(users: dict, ignore_key: str | None = None) -> set[str]:
    ids = set()
    for key, record in users.items():
        if key == ignore_key or not isinstance(record, dict):
            continue
        value = str(record.get("user_id") or "").strip()
        if value:
            ids.add(value)
    return ids


def _make_user_id(name: str, users: dict | None = None, ignore_key: str | None = None) -> str:
    """Gera um identificador interno estável e único a partir do nome."""
    base = f"usr_{_slugify(name)}"
    used = _existing_user_ids(users or {}, ignore_key=ignore_key)
    if base not in used:
        return base
    digest = hashlib.sha256(
        str(name).strip().casefold().encode("utf-8")
    ).hexdigest()[:8]
    candidate = f"{base}_{digest}"
    if candidate not in used:
        return candidate
    return f"{base}_{uuid.uuid4().hex[:8]}"


def _find_user_key(users: dict, name: str) -> str | None:
    """Localiza uma chave de usuário por nome, sem diferenciar maiúsculas."""
    target = str(name or "").strip().casefold()
    if not target:
        return None
    for key, record in users.items():
        candidates = {str(key).strip().casefold()}
        if isinstance(record, dict):
            candidates.add(str(record.get("name") or "").strip().casefold())
        if target in candidates:
            return key
    return None


def _random_unusable_password() -> str:
    # Usuários sem senha recebem um hash de um segredo aleatório que não é
    # exposto nem conhecido, mantendo o formato legado do arquivo.
    return hash_password(os.urandom(32).hex())


def _ensure_user_fields(users: dict, key: str) -> bool:
    """Completa campos obrigatórios de um registro, preservando os demais."""
    record = users.get(key)
    if not isinstance(record, dict):
        users[key] = {
            "name": str(key),
            "user_id": _make_user_id(str(key), users, ignore_key=key),
            "password": _random_unusable_password(),
            "active": True,
            "is_admin": False,
            "created_at": _now(),
        }
        return True

    changed = False
    if not record.get("user_id"):
        record["user_id"] = _make_user_id(str(key), users, ignore_key=key)
        changed = True
    if not str(record.get("name") or "").strip():
        record["name"] = str(key)
        changed = True
    if "active" not in record:
        record["active"] = True
        changed = True
    if "is_admin" not in record:
        record["is_admin"] = False
        changed = True
    if "created_at" not in record:
        record["created_at"] = _now()
        changed = True
    if "password" not in record:
        record["password"] = _random_unusable_password()
        changed = True
    return changed


def _ensure_initial_users(users: dict) -> bool:
    """Garante os três usuários iniciais sem duplicar registros existentes."""
    changed = False
    for item in DEFAULT_USERS:
        name = item["name"]
        key = _find_user_key(users, name)
        if key is None:
            users[name] = {
                "name": name,
                "user_id": item["user_id"],
                "password": _random_unusable_password(),
                "active": True,
                "is_admin": bool(item["is_admin"]),
                "created_at": _now(),
            }
            changed = True
            continue

        if _ensure_user_fields(users, key):
            changed = True
        record = users[key]
        # Os três usuários iniciais têm papéis definidos pela especificação.
        # O ajuste preserva senha, data de criação e demais campos existentes.
        if bool(record.get("is_admin", False)) != bool(item["is_admin"]):
            record["is_admin"] = bool(item["is_admin"])
            changed = True
        if str(record.get("user_id") or "") != item["user_id"]:
            record["user_id"] = item["user_id"]
            changed = True

    for key in list(users.keys()):
        if _ensure_user_fields(users, key):
            changed = True
    return changed


def _load_users_raw() -> dict | None:
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return {}
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def init_db():
    """Garante o diretório e os usuários iniciais de forma idempotente."""
    os.makedirs(DATA_DIR, exist_ok=True)
    users = _load_users_raw()
    if users is None:
        # Não sobrescreve um arquivo corrompido; o erro será tratado no load.
        return
    changed = _ensure_initial_users(users)
    if changed or not os.path.exists(USERS_FILE):
        save_users(users)


def load_users() -> dict:
    init_db()
    users = _load_users_raw()
    return users if isinstance(users, dict) else {}


def save_users(users: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=4)


def _public_user(key: str, record: dict) -> dict:
    return {
        "key": key,
        "id": str(record.get("user_id") or ""),
        "name": str(record.get("name") or key).strip() or key,
        "is_admin": bool(record.get("is_admin", False)),
        "active": bool(record.get("active", True)),
    }


def list_login_users() -> list[dict]:
    """Lista usuários ativos reais do cadastro para a seleção no login."""
    users = load_users()
    items = [
        _public_user(key, record)
        for key, record in users.items()
        if isinstance(record, dict) and record.get("active", True)
    ]
    items.sort(key=lambda item: (item["name"].casefold(), item["id"]))
    return items


def find_user_record(identifier: str) -> tuple[str | None, dict | None]:
    """Localiza por ID interno ou por nome de exibição."""
    users = load_users()
    target = str(identifier or "").strip()
    if not target:
        return None, None
    for key, record in users.items():
        if not isinstance(record, dict):
            continue
        if str(record.get("user_id") or "") == target:
            return key, record
    key = _find_user_key(users, target)
    if key is None:
        return None, None
    record = users.get(key)
    return (key, record) if isinstance(record, dict) else (None, None)


def get_active_user_by_id(user_id: str) -> dict | None:
    _key, record = find_user_record(user_id)
    if isinstance(record, dict) and record.get("active", True):
        return record
    return None


def authenticate_user(username: str, password: str):
    """Autenticação legada por senha, preservada para compatibilidade."""
    users = load_users()
    key = _find_user_key(users, username)
    if key is None:
        return False, "Credenciais incorretas ou usuário não encontrado.", False
    user_data = users[key]
    if not user_data.get("active", True):
        return False, "Usuário desativado no sistema.", False
    if verify_password(str(user_data.get("password") or ""), str(password or "")):
        return True, "Login realizado com sucesso", bool(user_data.get("is_admin", False))
    return False, "Credenciais incorretas ou usuário não encontrado.", False


def add_user(username: str, password: str | None = None, is_admin: bool = False):
    """Cadastra um usuário comum. Sem senha, o acesso é por seleção."""
    if is_admin:
        # A criação de novos administradores não faz parte do cadastro aberto
        # ao ADM e não pode ser feita por parâmetro de formulário.
        return False, "Não é permitido conceder privilégios ADM neste cadastro."
    users = load_users()
    name = str(username or "").strip()
    if not name:
        return False, "Informe o nome do usuário."
    if len(name) > 80:
        return False, "O nome do usuário deve ter no máximo 80 caracteres."
    if _find_user_key(users, name) is not None:
        return False, "Já existe um usuário com esse nome."
    if any(
        str(record.get("user_id") or "") == f"usr_{_slugify(name)}"
        for record in users.values()
        if isinstance(record, dict)
    ):
        return False, "Já existe um identificador interno para esse usuário."

    provided_password = str(password or "").strip()
    users[name] = {
        "name": name,
        "user_id": _make_user_id(name, users),
        "password": (
            hash_password(provided_password)
            if provided_password
            else _random_unusable_password()
        ),
        "active": True,
        "is_admin": bool(is_admin),
        "created_at": _now(),
    }
    save_users(users)
    return True, "Usuário cadastrado com sucesso."


def update_password(username: str, current_password: str, new_password: str):
    users = load_users()
    key = _find_user_key(users, username)
    if key is None:
        return False, "Usuário não encontrado."

    user_data = users[key]
    if not verify_password(str(user_data.get("password") or ""), current_password):
        return False, "Senha atual incorreta."

    if len(new_password.strip()) < 6:
        return False, "A nova senha deve ter pelo menos 6 caracteres."

    users[key]["password"] = hash_password(new_password)
    save_users(users)
    return True, "Senha alterada com sucesso."


def admin_reset_password(username: str, new_password: str):
    users = load_users()
    key = _find_user_key(users, username)
    if key is None:
        return False, "Usuário não encontrado."
    users[key]["password"] = hash_password(new_password)
    save_users(users)
    return True, "Senha redefinida pelo administrador com sucesso."


def _active_admin_count(users: dict) -> int:
    return sum(
        1
        for record in users.values()
        if isinstance(record, dict)
        and record.get("is_admin", False)
        and record.get("active", True)
    )


def toggle_user_status(username: str):
    users = load_users()
    key = _find_user_key(users, username)
    if key is None:
        return False, "Usuário não encontrado."
    if key in DEFAULT_USER_NAMES:
        return False, "Os usuários iniciais do sistema são protegidos."
    current = users[key].get("active", True)
    if (
        current
        and users[key].get("is_admin", False)
        and _active_admin_count(users) <= 1
    ):
        return False, "Não é permitido desativar o último administrador ativo."
    users[key]["active"] = not current
    save_users(users)
    status_text = "ativado" if not current else "desativado"
    return True, f"Usuário {status_text} com sucesso."


def delete_user(username: str):
    users = load_users()
    key = _find_user_key(users, username)
    if key is None:
        return False, "Usuário não encontrado."
    if key in DEFAULT_USER_NAMES:
        return False, "Os usuários iniciais do sistema são protegidos."
    if (
        users[key].get("is_admin", False)
        and users[key].get("active", True)
        and _active_admin_count(users) <= 1
    ):
        return False, "Não é permitido excluir o último administrador ativo."
    del users[key]
    save_users(users)
    return True, "Usuário removido com sucesso."


def session_user_is_admin() -> bool:
    """Revalida no cadastro se o usuário identificado na sessão tem perfil ADM.

    O nome exibido não define o privilégio: a verificação usa o identificador
    interno da sessão e o campo ``is_admin`` do registro persistido. Este fluxo
    não autentica identidade e pressupõe uso em ambiente controlado.
    """
    try:
        import streamlit as st

        if not st.session_state.get("authenticated", False):
            return False
        record = get_active_user_by_id(str(st.session_state.get("user_id") or ""))
        if not isinstance(record, dict):
            return False
        return bool(record.get("is_admin", False))
    except Exception:
        return False
