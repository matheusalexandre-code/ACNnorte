"""Conta de serviço do Xano: sincronização com o login apenas por nome.

Como o aplicativo não pede senha, nenhum token do Xano é obtido por usuário.
Estes testes garantem que a sincronização é ativada pela conta de serviço
configurada no ambiente, que o token é reaproveitado e renovado, e que a
ausência de configuração mantém o modo local.
"""

import pytest

import src.xano_sync as xano_sync
from src.core.database.xano_client import XanoError

BASE_URL = "https://exemplo.xano.io/api:acnnorte"


class FakeXanoClient:
    """Substitui o XanoClient: registra logins e tokens usados."""

    logins = 0
    tokens_used: list = []
    login_response = {"authToken": "tok-servico-1", "user": {"id": 42}}
    login_error: Exception | None = None

    def __init__(self, base_url=None, token=None, timeout=15.0, session=None):
        self.token = token
        FakeXanoClient.tokens_used.append(token)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        pass

    def post(self, path, json=None, **kwargs):
        if path == "/auth/login":
            FakeXanoClient.logins += 1
            if FakeXanoClient.login_error is not None:
                raise FakeXanoClient.login_error
            assert json == {"email": "sistema@acnnorte.com.br", "password": "senha-servico"}
            return dict(FakeXanoClient.login_response)
        raise AssertionError(f"POST inesperado: {path}")


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch):
    for key in ("XANO_BASE_URL", "XANO_AUTH_TOKEN", "XANO_SERVICE_EMAIL", "XANO_SERVICE_PASSWORD"):
        monkeypatch.setenv(key, "")
    monkeypatch.setattr(xano_sync, "_session_token", lambda: "")
    monkeypatch.setattr(xano_sync, "XanoClient", FakeXanoClient)
    FakeXanoClient.logins = 0
    FakeXanoClient.tokens_used = []
    FakeXanoClient.login_response = {"authToken": "tok-servico-1", "user": {"id": 42}}
    FakeXanoClient.login_error = None
    xano_sync.invalidate_service_token()
    yield
    xano_sync.invalidate_service_token()


def _configura_conta(monkeypatch):
    monkeypatch.setenv("XANO_BASE_URL", BASE_URL)
    monkeypatch.setenv("XANO_SERVICE_EMAIL", "Sistema@ACNnorte.com.br ")
    monkeypatch.setenv("XANO_SERVICE_PASSWORD", "senha-servico")


def test_sem_configuracao_permanece_no_modo_local():
    assert xano_sync.sync_enabled() is False
    assert xano_sync.service_account_configured() is False


def test_url_sem_autenticacao_nao_ativa_sync(monkeypatch):
    monkeypatch.setenv("XANO_BASE_URL", BASE_URL)
    assert xano_sync.sync_enabled() is False


def test_conta_de_servico_ativa_sync_sem_login_por_usuario(monkeypatch):
    _configura_conta(monkeypatch)
    assert xano_sync.sync_enabled() is True
    # sync_enabled não deve fazer chamadas HTTP.
    assert FakeXanoClient.logins == 0


def test_token_fixo_continua_aceito(monkeypatch):
    monkeypatch.setenv("XANO_BASE_URL", BASE_URL)
    monkeypatch.setenv("XANO_AUTH_TOKEN", "tok-fixo")
    assert xano_sync.sync_enabled() is True
    assert xano_sync._resolve_token() == "tok-fixo"
    assert FakeXanoClient.logins == 0


def test_login_unico_e_token_reaproveitado(monkeypatch):
    _configura_conta(monkeypatch)
    xano_sync._client()
    xano_sync._client()
    assert FakeXanoClient.logins == 1
    assert FakeXanoClient.tokens_used[-1] == "tok-servico-1"
    assert FakeXanoClient.tokens_used[-2] == "tok-servico-1"


def test_token_renovado_apos_expirar(monkeypatch):
    _configura_conta(monkeypatch)
    relogio = [1000.0]
    monkeypatch.setattr(xano_sync.time, "time", lambda: relogio[0])

    assert xano_sync._resolve_token() == "tok-servico-1"
    FakeXanoClient.login_response = {"authToken": "tok-servico-2", "user": {"id": 42}}
    relogio[0] += xano_sync.SERVICE_TOKEN_TTL_SECONDS + 1

    assert xano_sync._resolve_token() == "tok-servico-2"
    assert FakeXanoClient.logins == 2


def test_erro_401_forca_novo_login(monkeypatch):
    _configura_conta(monkeypatch)
    assert xano_sync._resolve_token() == "tok-servico-1"

    xano_sync._handle_auth_error(XanoError("expirado", status_code=401))
    FakeXanoClient.login_response = {"authToken": "tok-servico-2", "user": {"id": 42}}

    assert xano_sync._resolve_token() == "tok-servico-2"
    assert FakeXanoClient.logins == 2


def test_outros_erros_nao_descartam_o_token(monkeypatch):
    _configura_conta(monkeypatch)
    xano_sync._resolve_token()
    xano_sync._handle_auth_error(XanoError("falha", status_code=500))
    xano_sync._resolve_token()
    assert FakeXanoClient.logins == 1


def test_token_da_sessao_tem_prioridade(monkeypatch):
    _configura_conta(monkeypatch)
    monkeypatch.setattr(xano_sync, "_session_token", lambda: "tok-sessao")
    assert xano_sync._resolve_token() == "tok-sessao"
    assert FakeXanoClient.logins == 0


def test_visita_registrada_pela_conta_de_servico(monkeypatch):
    _configura_conta(monkeypatch)
    xano_sync._resolve_token()
    assert xano_sync._session_user_id() == 42


def test_falha_no_login_usa_token_fixo_de_reserva(monkeypatch):
    _configura_conta(monkeypatch)
    monkeypatch.setenv("XANO_AUTH_TOKEN", "tok-reserva")
    FakeXanoClient.login_error = XanoError("credenciais inválidas", status_code=403)
    assert xano_sync._resolve_token() == "tok-reserva"


def test_falha_no_login_sem_reserva_nao_quebra(monkeypatch):
    _configura_conta(monkeypatch)
    FakeXanoClient.login_error = XanoError("fora do ar", status_code=503)
    assert xano_sync._resolve_token() == ""
