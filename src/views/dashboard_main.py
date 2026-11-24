import html
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.export_manager import EXPORTS_DIR
from src.storage_bridge import storage_root
from src.storage_manager import load_clients, load_visits
from src.ui_components import (
    CLIENTS_TAB_CONSULT,
    CLIENTS_TAB_NEW,
    PAGE_CLIENTS,
    PAGE_HISTORY,
    PAGE_REPORTS,
    PAGE_VISITS,
    VISITS_TAB_NEW,
    navigate_to,
    render_acnnorte_logo,
    render_empty_state,
    render_section_title,
    status_badge,
)


def _parse_datetime(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def _build_recent_activities(clients: dict, visits: dict, limit: int = 6):
    activities = []
    for visit in visits.values():
        activities.append(
            {
                "kind": "visita",
                "icon": "📋",
                "title": f"Visita de {visit.get('client_name', 'cliente')}",
                "detail": f"Técnico: {visit.get('technician', '—')}",
                "status": visit.get("status", "Rascunho"),
                "when": visit.get("updated_at") or visit.get("created_at", ""),
            }
        )
    for client in clients.values():
        activities.append(
            {
                "kind": "cliente",
                "icon": "🏢",
                "title": f"Cliente cadastrado: {client.get('name', '—')}",
                "detail": f"CNPJ: {client.get('cnpj', '—')}",
                "status": None,
                "when": client.get("created_at", ""),
            }
        )

    def sort_key(item):
        parsed = _parse_datetime(item.get("when", ""))
        return parsed or datetime.min

    return sorted(activities, key=sort_key, reverse=True)[:limit]


def compute_dashboard_metrics(clients: dict, visits: dict, reports_generated: int = 0) -> dict:
    """Indicadores reais do dashboard, calculados somente a partir de dados salvos."""
    statuses = [str(v.get("status") or "Rascunho").strip() for v in visits.values()]
    return {
        "total_visits": len(visits),
        "completed": sum(1 for status in statuses if status == "Finalizada"),
        "pending": sum(1 for status in statuses if status == "Rascunho"),
        "in_progress": sum(1 for status in statuses if status == "Em Andamento"),
        "companies": len(clients),
        "reports": int(reports_generated or 0),
    }


def count_generated_reports() -> int:
    """Conta PDFs já gerados em data/exports e no espelho storage/reports."""
    names = set()
    directories = (Path(EXPORTS_DIR), storage_root() / "storage" / "reports")
    for directory in directories:
        try:
            for pdf in directory.glob("*.pdf"):
                names.add(pdf.name)
        except OSError:
            continue
    return len(names)


def _build_recent_visits(visits: dict, limit: int = 5):
    """Lista as visitas mais recentes para a tabela do dashboard."""
    items = []
    for visit_id, visit in visits.items():
        items.append(
            {
                "ID": visit_id,
                "Empresa": visit.get("client_name", "—"),
                "Data": str(visit.get("date_start") or visit.get("date") or "—"),
                "Técnico": visit.get("technician", "—"),
                "Tipo": visit.get("visit_type") or "—",
                "Status": visit.get("status", "Rascunho"),
            }
        )
    items.sort(key=lambda item: item["Data"], reverse=True)
    return items[:limit]


def render_main_dashboard():
    username = html.escape(st.session_state.get("username", "Usuário"))
    render_acnnorte_logo(size="medium", subtitle="Dashboard e Indicadores Operacionais")

    st.markdown(
        f"### Olá, **{username}**! Veja o resumo das suas visitas técnicas."
    )
    st.caption(f"Hoje é {datetime.now().strftime('%d/%m/%Y')} — dados salvos neste dispositivo.")

    clients = load_clients()
    visits = load_visits()

    metrics = compute_dashboard_metrics(clients, visits, count_generated_reports())

    if not visits and not clients:
        render_empty_state(
            "🗂️",
            "Ainda não existem registros",
            "Cadastre uma empresa e inicie a primeira visita para alimentar o dashboard.",
        )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de visitas registradas", metrics["total_visits"])
    with col2:
        st.metric("Visitas concluídas", metrics["completed"])
    with col3:
        st.metric("Visitas pendentes", metrics["pending"])

    col4, col5, col6 = st.columns(3)
    with col4:
        st.metric("Visitas em andamento", metrics["in_progress"])
    with col5:
        st.metric("Empresas atendidas", metrics["companies"])
    with col6:
        st.metric("Relatórios gerados", metrics["reports"])

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Atalhos rápidos (navegam de verdade para a funcionalidade)
    # ------------------------------------------------------------------
    render_section_title("Acesso rápido", "Nova visita, histórico e relatórios em um clique.", "⚡")
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        if st.button("➕ Nova visita", key="dash_new_visit", width="stretch"):
            navigate_to(PAGE_VISITS, visits_tab=VISITS_TAB_NEW)
    with sc2:
        if st.button("🗂️ Histórico de visitas", key="dash_history", width="stretch"):
            navigate_to(PAGE_HISTORY)
    with sc3:
        if st.button("📊 Relatórios", key="dash_reports", width="stretch"):
            navigate_to(PAGE_REPORTS)
    with sc4:
        if st.button("🏢 Cadastrar cliente", key="dash_new_client", width="stretch"):
            navigate_to(PAGE_CLIENTS, clients_tab=CLIENTS_TAB_NEW)

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Últimas atividades
    # ------------------------------------------------------------------
    render_section_title("Últimas atividades", "Clientes e visitas atualizados recentemente.", "🕒")
    activities = _build_recent_activities(clients, visits)
    if not activities:
        render_empty_state(
            "🗂️",
            "Nenhuma atividade registrada ainda",
            "Cadastre um cliente ou inicie uma visita para começar.",
        )
    else:
        for activity in activities:
            badge = status_badge(activity["status"]) if activity.get("status") else ""
            st.markdown(
                f"""
                <div class="acn-activity">
                    <b>{activity['icon']} {html.escape(activity['title'])}</b> {badge}
                    <div>{html.escape(activity['detail'])}</div>
                    <div class="acn-activity-meta">Atualizado em {html.escape(str(activity['when']) or '—')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------------------
    # Visitas recentes (somente dados persistidos)
    # ------------------------------------------------------------------
    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    render_section_title("Visitas recentes", "Últimos registros salvos no sistema.", "🕒")
    recent_visits = _build_recent_visits(visits)
    if recent_visits:
        st.dataframe(pd.DataFrame(recent_visits), hide_index=True, width="stretch")
    else:
        st.info("Ainda não existem visitas registradas.")

    # ------------------------------------------------------------------
    # Instruções rápidas
    # ------------------------------------------------------------------
    with st.expander("ℹ️ Instruções rápidas — fluxo de utilização", expanded=False):
        st.markdown(
            "1. Cadastrar uma nova visita.\n"
            "2. Preencher os dados da empresa e da visita.\n"
            "3. Realizar o checklist de Segurança do Trabalho.\n"
            "4. Registrar observações e fotografias.\n"
            "5. Salvar a visita.\n"
            "6. Consultar o histórico.\n"
            "7. Gerar relatórios."
        )
