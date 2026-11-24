"""Testes das ampliações de dashboard, checklist, histórico e storage."""

import os
from datetime import date
from pathlib import Path

import pytest

import src.export_manager as export_manager
import src.storage_bridge as storage_bridge
import src.storage_manager as storage
import src.views.dashboard_main as dashboard_main
import src.views.history_view as history_view
from src.checklist_sst import (
    SST_CATEGORIES,
    SST_OPTIONS,
    build_sst_answers,
    iter_sst_items,
    summarize_sst,
    sst_widget_key,
)


@pytest.fixture()
def isolated_storage(tmp_path, monkeypatch):
    """Redireciona JSON, fotos e exports para um diretório temporário."""
    data_dir = tmp_path / "data"
    exports_dir = data_dir / "exports"
    monkeypatch.setattr(storage, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(storage, "CLIENTS_FILE", str(data_dir / "clients.json"))
    monkeypatch.setattr(storage, "VISITS_FILE", str(data_dir / "visits.json"))
    monkeypatch.setattr(storage, "PHOTOS_DIR", str(data_dir / "photos"))
    monkeypatch.setattr(export_manager, "EXPORTS_DIR", str(exports_dir))
    monkeypatch.setattr(dashboard_main, "EXPORTS_DIR", str(exports_dir))
    storage.init_storage()
    return tmp_path


def test_checklist_is_modular_and_summarizes_real_answers():
    assert len(SST_CATEGORIES) == 14
    assert SST_OPTIONS == ("Conforme", "Não conforme", "Não aplicável")

    answers = {}
    for category_key, item in iter_sst_items():
        key = sst_widget_key("new", category_key, item["id"])
        answers[key] = "Conforme"
    first_item = next(iter_sst_items())[1]
    answers[sst_widget_key("new", "epi", first_item["id"])] = "Não conforme"

    normalized = build_sst_answers("new", answers)
    summary = summarize_sst(normalized)
    assert summary["total"] == len(list(iter_sst_items()))
    assert summary["Não conforme"] == 1
    assert summary["Conforme"] == summary["total"] - 1
    assert summary["non_conformities"][0]["item"] == first_item["label"]


def test_add_visit_persists_extended_form_fields(isolated_storage):
    ok, client_id, _ = storage.add_client(
        "Empresa Teste", "00.000.000/0001-00", "Rua A", "Responsável", "999", "a@b.com"
    )
    assert ok

    ok, visit_id, _ = storage.add_visit(
        client_id,
        "Técnico Teste",
        "2026-11-20",
        status="Em Andamento",
        visit_type="Inspeção",
        objective="Verificar EPIs",
        company_details={"city": "Manaus", "state": "AM", "segment": "Logística"},
        sst_checklist={"epi_uso": "Conforme"},
        technical_observations={"risks": "Ruído", "recommendations": "Monitorar"},
    )
    assert ok

    visit = storage.load_visits()[visit_id]
    assert visit["visit_type"] == "Inspeção"
    assert visit["objective"] == "Verificar EPIs"
    assert visit["company_details"]["city"] == "Manaus"
    assert visit["sst_checklist"]["epi_uso"] == "Conforme"
    assert visit["technical_observations"]["risks"] == "Ruído"


def test_set_visit_status_preserves_the_rest_of_the_record(isolated_storage):
    ok, client_id, _ = storage.add_client(
        "Empresa B", "11.111.111/0001-11", "Rua B", "Resp", "888", "b@b.com"
    )
    assert ok
    ok, visit_id, _ = storage.add_visit(
        client_id, "Técnico", "2026-11-20", objective="Objetivo original"
    )
    assert ok

    ok, message = storage.set_visit_status(visit_id, "Finalizada")
    assert ok and "Finalizada" in message
    visit = storage.load_visits()[visit_id]
    assert visit["status"] == "Finalizada"
    assert visit["objective"] == "Objetivo original"

    ok, _ = storage.set_visit_status(visit_id, "Status inválido")
    assert not ok
    assert storage.load_visits()[visit_id]["status"] == "Finalizada"


def test_filter_visits_applies_all_filters_simultaneously():
    visits = {
        "v1": {
            "client_name": "ACN Norte",
            "technician": "Ana",
            "status": "Finalizada",
            "visit_type": "Inspeção",
            "date_start": "2026-11-10",
        },
        "v2": {
            "client_name": "Outra Empresa",
            "technician": "Ana",
            "status": "Finalizada",
            "visit_type": "Inspeção",
            "date_start": "2026-11-12",
        },
    }
    result = history_view.filter_visits(
        visits,
        company="acn",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 30),
        technician="ana",
        status="Finalizada",
        visit_type="Inspeção",
    )
    assert list(result) == ["v1"]

    assert history_view.filter_visits(visits, status="Rascunho") == {}


def test_storage_bridge_mirrors_without_overwriting(isolated_storage):
    source = isolated_storage / "source.pdf"
    source.write_bytes(b"%PDF-1.4 teste")

    first = storage_bridge.mirror_file(str(source), "reports")
    second = storage_bridge.mirror_file(str(source), "reports")

    assert first and second
    assert first != second
    assert Path(first).is_file() and Path(second).is_file()
    assert storage_bridge.mirror_file(str(source), "invalido") is None


def test_dashboard_metrics_use_only_persisted_data():
    clients = {"c1": {}, "c2": {}}
    visits = {
        "v1": {"status": "Finalizada"},
        "v2": {"status": "Rascunho"},
        "v3": {"status": "Em Andamento"},
    }
    metrics = dashboard_main.compute_dashboard_metrics(clients, visits, 2)
    assert metrics == {
        "total_visits": 3,
        "completed": 1,
        "pending": 1,
        "in_progress": 1,
        "companies": 2,
        "reports": 2,
    }
    assert dashboard_main.compute_dashboard_metrics({}, {}, 0)["total_visits"] == 0


def test_generated_pdf_and_excel_are_mirrored_to_storage(isolated_storage):
    ok, client_id, _ = storage.add_client(
        "Empresa Relatório", "22.222.222/0001-22", "Rua C", "Resp", "777", "c@c.com"
    )
    assert ok
    ok, visit_id, _ = storage.add_visit(
        client_id, "Técnico", "2026-11-20", status="Finalizada"
    )
    assert ok

    pdf_path = export_manager.generate_pdf_report(visit_id)
    assert pdf_path and os.path.isfile(pdf_path)
    assert list((isolated_storage / "storage" / "reports").glob("*.pdf"))

    xlsx_path = export_manager.export_visits_to_excel()
    assert xlsx_path and os.path.isfile(xlsx_path)
    assert list((isolated_storage / "storage" / "exports").glob("*.xlsx"))
