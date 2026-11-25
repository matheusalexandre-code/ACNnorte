"""Observações individuais por tópico do checklist de Segurança do Trabalho."""

import os
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import src.auth_manager as auth
import src.export_manager as export_manager
import src.storage_manager as storage
import src.views.visits_view as visits_view
import src.xano_sync as xano_sync
from src.checklist_sst import (
    SST_CATEGORIES,
    SST_OBSERVATION_LABEL,
    SST_OBSERVATION_PLACEHOLDER,
    SST_UNANSWERED,
    build_sst_answers,
    build_sst_observations,
    get_sst_observations,
    iter_sst_items,
    normalize_sst_observations,
    sst_observation_widget_key,
    summarize_sst,
)

MAIN_SCRIPT = str(Path(__file__).resolve().parents[1] / "src" / "main.py")

OBS_EPI = "Todos os funcionários possuem EPIs adequados."
OBS_EPC = "Necessário revisar a proteção coletiva da área."

SAMPLE_OBSERVATIONS = {
    "epi": OBS_EPI,
    "epc": OBS_EPC,
    "sinalizacao": "",
}


@pytest.fixture()
def isolated_storage(tmp_path, monkeypatch):
    """Redireciona JSON, fotos e exports para um diretório temporário."""
    data_dir = tmp_path / "data"
    exports_dir = data_dir / "exports"
    auth_dir = tmp_path / "auth"
    monkeypatch.setattr(auth, "DATA_DIR", str(auth_dir))
    monkeypatch.setattr(auth, "USERS_FILE", str(auth_dir / "users.json"))
    monkeypatch.setattr(storage, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(storage, "CLIENTS_FILE", str(data_dir / "clients.json"))
    monkeypatch.setattr(storage, "VISITS_FILE", str(data_dir / "visits.json"))
    monkeypatch.setattr(storage, "PHOTOS_DIR", str(data_dir / "photos"))
    monkeypatch.setattr(export_manager, "EXPORTS_DIR", str(exports_dir))
    monkeypatch.delenv("XANO_BASE_URL", raising=False)
    auth.init_db()
    storage.init_storage()
    return tmp_path


def _authenticated_app():
    at = AppTest.from_file(MAIN_SCRIPT, default_timeout=60)
    at.session_state["authenticated"] = True
    at.session_state["username"] = "Ana.norte"
    at.session_state["user_id"] = "usr_ana_norte"
    at.session_state["user_role"] = "usuario"
    at.session_state["is_admin"] = False
    at.session_state["admin_authorized"] = False
    return at


def _create_client():
    ok, client_id, _ = storage.add_client(
        "Empresa SST", "00.000.000/0001-00", "Rua A", "Responsável", "999", "a@b.com"
    )
    assert ok
    return client_id


def _create_visit(observations=None, answers=None):
    client_id = _create_client()
    ok, visit_id, _ = storage.add_visit(
        client_id,
        "Técnico SST",
        "2026-11-24",
        status="Em Andamento",
        sst_checklist=answers or {},
        sst_observations=observations or {},
    )
    assert ok
    return client_id, visit_id


def _sst_answers():
    answers = {}
    for category_key, item in iter_sst_items():
        answers[sst_widget_key_for(category_key, item)] = "Conforme"
    return answers


def sst_widget_key_for(category_key, item):
    from src.checklist_sst import sst_widget_key

    return sst_widget_key("new", category_key, item["id"])


# ---------------------------------------------------------------------------
# 1 e 2 — identificação e independência dos 14 campos
# ---------------------------------------------------------------------------
def test_observation_widget_keys_are_stable_unique_and_not_index_based():
    assert len(SST_CATEGORIES) == 14
    keys = [sst_observation_widget_key("new", key) for key in SST_CATEGORIES]
    assert len(set(keys)) == 14
    assert keys[0] == "sst_obs_new_epi"
    assert keys[1] == "sst_obs_new_epc"

    other_visit_keys = [sst_observation_widget_key("abc123", key) for key in SST_CATEGORIES]
    assert not set(keys) & set(other_visit_keys)
    assert all(f"_{key}" in widget for key, widget in zip(SST_CATEGORIES, other_visit_keys))
    assert SST_OBSERVATION_LABEL == "Comentários / Observações"
    assert "observações" in SST_OBSERVATION_PLACEHOLDER.lower()


def test_build_sst_observations_keeps_all_14_topics_independent():
    collected = {
        sst_observation_widget_key("new", category_key): f"Observação de {category_key}"
        for category_key in SST_CATEGORIES
    }
    collected[sst_observation_widget_key("new", "epc")] = OBS_EPC

    observations = build_sst_observations("new", collected)

    assert len(observations) == 14
    assert observations["epi"] == "Observação de epi"
    assert observations["epc"] == OBS_EPC
    assert observations["documentacao"] == "Observação de documentacao"
    assert all(observations[key] for key in SST_CATEGORIES)
    assert normalize_sst_observations(None) == {key: "" for key in SST_CATEGORIES}


# ---------------------------------------------------------------------------
# 3, 4, 5, 6 e 7 — persistência local, recuperação, edição e compatibilidade
# ---------------------------------------------------------------------------
def test_add_and_load_visit_preserve_all_observations(isolated_storage):
    _client_id, visit_id = _create_visit(observations=SAMPLE_OBSERVATIONS)

    visit = storage.load_visits()[visit_id]
    recovered = get_sst_observations(visit)

    assert visit["sst_observations"]["epi"] == OBS_EPI
    assert recovered["epc"] == OBS_EPC
    assert recovered["sinalizacao"] == ""
    assert len(recovered) == 14


def test_update_visit_preserves_other_topics_and_allows_clearing_one(isolated_storage):
    answers = build_sst_answers("new", _sst_answers())
    _client_id, visit_id = _create_visit(observations=SAMPLE_OBSERVATIONS, answers=answers)

    ok, _ = storage.update_visit(
        visit_id, {}, "obs", "conclusao", "Em Andamento",
        sst_observations={"epi": "EPI revisado após vistoria."},
    )
    assert ok
    visit = storage.load_visits()[visit_id]
    assert visit["sst_observations"]["epi"] == "EPI revisado após vistoria."
    assert visit["sst_observations"]["epc"] == OBS_EPC
    assert visit["sst_checklist"] == answers, "respostas não podem ser apagadas"

    ok, _ = storage.update_visit(
        visit_id, {}, "obs", "conclusao", "Em Andamento",
        sst_observations={"epc": ""},
    )
    assert ok
    visit = storage.load_visits()[visit_id]
    assert visit["sst_observations"]["epc"] == ""
    assert visit["sst_observations"]["epi"] == "EPI revisado após vistoria."


def test_old_visit_without_observations_continues_working(isolated_storage):
    client_id = _create_client()
    ok, visit_id, _ = storage.add_visit(
        client_id, "Técnico", "2026-01-01", sst_checklist={"epi_uso": "Conforme"}
    )
    assert ok
    # Simula um registro gravado antes da existência do campo.
    visits = storage.load_visits()
    visits[visit_id].pop("sst_observations", None)
    storage.save_visits(visits)
    visit = storage.load_visits()[visit_id]
    assert "sst_observations" not in visit

    observations = get_sst_observations(visit)
    assert set(observations) == set(SST_CATEGORIES)
    assert not any(observations.values())
    assert summarize_sst(visit["sst_checklist"])["Conforme"] == 1

    pdf_path = export_manager.generate_pdf_report(visit_id)
    assert pdf_path and os.path.isfile(pdf_path)
    assert export_manager.export_visits_to_excel()


def test_empty_observations_do_not_add_artificial_information(isolated_storage, monkeypatch):
    _client_id, visit_id = _create_visit(observations={"epi": OBS_EPI, "epc": ""})

    captured = []
    original_paragraph = export_manager.Paragraph

    def _spy(text, *args, **kwargs):
        captured.append(str(text))
        return original_paragraph(text, *args, **kwargs)

    monkeypatch.setattr(export_manager, "Paragraph", _spy)
    assert export_manager.generate_pdf_report(visit_id)

    observation_lines = [t for t in captured if SST_OBSERVATION_LABEL in t]
    assert len(observation_lines) == 1
    assert OBS_EPI in observation_lines[0]

    xlsx_path = export_manager.export_visits_to_excel()
    frame = pd.read_excel(xlsx_path)
    row = frame[frame["ID Visita"] == visit_id].iloc[0]
    assert SST_OBSERVATION_LABEL in row["Checklist SST - Equipamentos de Proteção Individual (EPIs)"]
    assert SST_OBSERVATION_LABEL not in row["Checklist SST - Equipamentos de Proteção Coletiva (EPCs)"]


# ---------------------------------------------------------------------------
# 10 e 11 — PDF e Excel
# ---------------------------------------------------------------------------
def test_pdf_includes_topic_name_result_and_observation(isolated_storage, monkeypatch):
    answers = build_sst_answers("new", _sst_answers())
    _client_id, visit_id = _create_visit(observations=SAMPLE_OBSERVATIONS, answers=answers)

    captured = []
    original_paragraph = export_manager.Paragraph

    def _spy(text, *args, **kwargs):
        captured.append(str(text))
        return original_paragraph(text, *args, **kwargs)

    monkeypatch.setattr(export_manager, "Paragraph", _spy)
    pdf_path = export_manager.generate_pdf_report(visit_id)

    assert pdf_path and os.path.isfile(pdf_path)
    assert any("Checklist de Segurança do Trabalho" in text for text in captured)
    assert any("Equipamentos de Proteção Individual (EPIs)" in text for text in captured)
    assert any("Uso correto e obrigatório dos EPIs: Conforme" in text for text in captured)
    assert any(OBS_EPI in text for text in captured)
    assert any(OBS_EPC in text for text in captured)


def test_excel_includes_topic_name_result_and_observation(isolated_storage):
    answers = build_sst_answers("new", _sst_answers())
    _client_id, visit_id = _create_visit(observations=SAMPLE_OBSERVATIONS, answers=answers)

    xlsx_path = export_manager.export_visits_to_excel()
    frame = pd.read_excel(xlsx_path)
    row = frame[frame["ID Visita"] == visit_id].iloc[0]

    epi_col = "Checklist SST - Equipamentos de Proteção Individual (EPIs)"
    epc_col = "Checklist SST - Equipamentos de Proteção Coletiva (EPCs)"
    assert epi_col in frame.columns
    assert epc_col in frame.columns
    assert "Uso correto e obrigatório dos EPIs: Conforme" in row[epi_col]
    assert OBS_EPI in row[epi_col]
    assert OBS_EPC in row[epc_col]
    assert OBS_EPI not in row[epc_col]
    assert len([c for c in frame.columns if str(c).startswith("Checklist SST - ")]) == 14


# ---------------------------------------------------------------------------
# 8 e 9 — Xano: payload, sincronização e recuperação
# ---------------------------------------------------------------------------
def test_xano_payloads_include_observations_without_schema_changes(isolated_storage):
    answers = build_sst_answers("new", _sst_answers())
    _client_id, visit_id = _create_visit(observations=SAMPLE_OBSERVATIONS, answers=answers)
    visit = storage.load_visits()[visit_id]

    ext = xano_sync._build_ext_payload(visit)
    assert ext["sst_observations"] == visit["sst_observations"]
    assert ext["sst_checklist"] == answers
    assert len(get_sst_observations(visit)) == 14

    patch = xano_sync._visit_patch_payload(visit)
    assert set(patch["general_observations"])
    recovered_text, recovered_ext = xano_sync._unpack_observations(
        patch["general_observations"]
    )
    assert recovered_text == visit.get("observations", "")
    assert recovered_ext["sst_observations"]["epi"] == OBS_EPI
    assert recovered_ext["sst_checklist"] == answers
    assert "checklist_epi" in patch and "general_observations" in patch


class _FakeXanoClient:
    def __init__(self, remote):
        self.remote = remote
        self.patches = []

    def get(self, path, **kwargs):
        return {"visit": dict(self.remote)}

    def patch(self, path, payload, **kwargs):
        self.patches.append((path, payload))
        return {"visit": dict(self.remote)}

    def post(self, path, payload=None, **kwargs):
        return {}

    def close(self):
        pass


def test_xano_sync_sends_and_recovers_observations(isolated_storage, monkeypatch):
    _client_id, visit_id = _create_visit(observations=SAMPLE_OBSERVATIONS)
    visit = storage.load_visits()[visit_id]
    visit["xano_id"] = 55
    visit["xano_client_id"] = 12

    fake = _FakeXanoClient({"id": 55, "status": "rascunho", "visit_date": "2026-11-24"})
    monkeypatch.setattr(xano_sync, "sync_enabled", lambda *args, **kwargs: True)
    monkeypatch.setattr(xano_sync, "_client", lambda *args, **kwargs: fake)
    monkeypatch.setattr(xano_sync, "sync_visit_photos", lambda *args, **kwargs: None)

    result = xano_sync.sync_visit(dict(visit))

    assert len(fake.patches) == 1
    assert fake.patches[0][0] == "/visits/55"
    _text, ext = xano_sync._unpack_observations(
        fake.patches[0][1]["general_observations"]
    )
    assert ext["sst_observations"]["epi"] == OBS_EPI
    assert result["xano_synced_at"]

    remote = {
        "id": 55,
        "status": "rascunho",
        "visit_date": "2026-11-24",
        "general_observations": xano_sync._visit_patch_payload(result)[
            "general_observations"
        ],
    }
    restored = xano_sync._remote_visit_to_local(remote)
    assert get_sst_observations(restored)["epc"] == OBS_EPC
    assert get_sst_observations(restored)["epi"] == OBS_EPI

    legacy = xano_sync._remote_visit_to_local({"id": 56, "status": "rascunho"})
    assert get_sst_observations(legacy) == {key: "" for key in SST_CATEGORIES}


# ---------------------------------------------------------------------------
# 12 — interface Streamlit (preenchimento, independência e persistência)
# ---------------------------------------------------------------------------
def test_new_visit_form_has_14_independent_observation_fields(isolated_storage):
    _create_client()
    at = _authenticated_app()
    at.session_state["current_page"] = "Nova Visita"
    at.session_state["visits_tab"] = "➕ Iniciar Visita"
    at.run()

    assert not at.exception
    keys = [sst_observation_widget_key("new", key) for key in SST_CATEGORIES]
    for key in keys:
        widget = at.get_by_key(key)
        assert widget.value == "", key

    at.get_by_key(keys[0]).set_value(OBS_EPI).run()
    at.get_by_key(keys[1]).set_value(OBS_EPC).run()
    assert not at.exception
    assert at.session_state[keys[0]] == OBS_EPI
    assert at.session_state[keys[1]] == OBS_EPC
    assert all(at.session_state[key] == "" for key in keys[2:])

    at.button(key="FormSubmitter:new_visit_form-Salvar visita").click().run()
    assert not at.exception

    visits = storage.load_visits()
    assert len(visits) == 1
    saved = next(iter(visits.values()))
    assert saved["sst_observations"]["epi"] == OBS_EPI
    assert saved["sst_observations"]["epc"] == OBS_EPC
    assert saved["sst_observations"]["sinalizacao"] == ""
    assert all(at.session_state[key] == "" for key in keys), "campos 'new' devem ser limpos"
    assert SST_UNANSWERED == "Não avaliado"


def test_edit_flow_recovers_changes_and_preserves_other_topics(isolated_storage, monkeypatch):
    # Componentes customizados (foto/assinatura) mantêm o registry do primeiro
    # AppTest da suíte; não são necessários para validar as observações.
    monkeypatch.setattr(visits_view, "photo_input", lambda *args, **kwargs: None)
    monkeypatch.setattr(visits_view, "signature_pad", lambda *args, **kwargs: None)

    answers = build_sst_answers("new", _sst_answers())
    _client_id, visit_id = _create_visit(observations=SAMPLE_OBSERVATIONS, answers=answers)

    at = _authenticated_app()
    at.session_state["current_page"] = "Nova Visita"
    at.session_state["visits_tab"] = "✍️ Preencher Visita"
    at.session_state["active_visit_id"] = visit_id
    at.run()

    assert not at.exception
    epi_key = sst_observation_widget_key(visit_id, "epi")
    epc_key = sst_observation_widget_key(visit_id, "epc")
    assert at.get_by_key(epi_key).value == OBS_EPI
    assert at.get_by_key(epc_key).value == OBS_EPC

    at.get_by_key(epi_key).set_value("EPI substituído após nova análise.").run()
    assert not at.exception
    assert at.session_state[epi_key] == "EPI substituído após nova análise."

    at.button(key=f"next_{visit_id}").click().run()
    assert not at.exception
    assert at.session_state[epi_key] == "EPI substituído após nova análise."
    assert at.session_state[epc_key] == OBS_EPC

    at.button(key=f"save_{visit_id}").click().run()
    assert not at.exception
    visit = storage.load_visits()[visit_id]
    assert visit["sst_observations"]["epi"] == "EPI substituído após nova análise."
    assert visit["sst_observations"]["epc"] == OBS_EPC
    assert visit["sst_checklist"] == answers
