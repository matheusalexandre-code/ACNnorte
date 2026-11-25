"""Histórico de visitas técnicas com filtros, detalhes e ações reais."""

import html
from datetime import date, datetime

import pandas as pd
import streamlit as st

from src.checklist_sst import (
    SST_CATEGORIES,
    SST_OBSERVATION_LABEL,
    get_sst_observations,
    summarize_sst,
)
from src.export_manager import export_visits_to_excel, generate_pdf_report
from src.storage_manager import (
    VISIT_STATUSES,
    load_clients,
    load_visits,
    set_visit_status,
)
from src.ui_components import (
    PAGE_REPORTS,
    PAGE_VISITS,
    VISITS_TAB_FILL,
    navigate_to,
    render_acnnorte_logo,
    render_empty_state,
    render_section_title,
    status_badge,
)


def _parse_visit_date(visit: dict):
    """Converte a data da visita para ``date``, tolerando registros antigos."""
    raw = str(visit.get("date_start") or visit.get("date") or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw[:19], fmt).date()
        except ValueError:
            continue
    return None


def filter_visits(
    visits: dict,
    *,
    company: str = "",
    start_date: date = None,
    end_date: date = None,
    technician: str = "",
    status: str = "",
    visit_type: str = "",
) -> dict:
    """Aplica todos os filtros simultaneamente (somente leitura)."""
    company = str(company or "").strip().casefold()
    technician = str(technician or "").strip().casefold()
    status = str(status or "").strip().casefold()
    visit_type = str(visit_type or "").strip().casefold()

    result = {}
    for visit_id, visit in visits.items():
        if company and company not in str(visit.get("client_name", "")).casefold():
            continue
        if technician and technician not in str(visit.get("technician", "")).casefold():
            continue
        if status and status != str(visit.get("status", "")).casefold():
            continue
        if visit_type and visit_type != str(visit.get("visit_type", "")).casefold():
            continue
        visit_date = _parse_visit_date(visit)
        if start_date and (visit_date is None or visit_date < start_date):
            continue
        if end_date and (visit_date is None or visit_date > end_date):
            continue
        result[visit_id] = visit
    return result


def build_history_dataframe(visits: dict, clients: dict) -> pd.DataFrame:
    """Monta a tabela do histórico usando somente dados persistidos."""
    rows = []
    for visit_id, visit in visits.items():
        client = clients.get(visit.get("client_id"), {})
        summary = summarize_sst(visit.get("sst_checklist"))
        rows.append(
            {
                "ID": visit_id,
                "Empresa": visit.get("client_name") or client.get("name", "—"),
                "CNPJ": client.get("cnpj", "—"),
                "Data da visita": str(visit.get("date_start") or visit.get("date") or "—"),
                "Técnico responsável": visit.get("technician", "—"),
                "Tipo de visita": visit.get("visit_type") or "Não informado",
                "Status": visit.get("status", "Rascunho"),
                "Não conformidades": summary["Não conforme"],
            }
        )
    return pd.DataFrame(rows)


def _render_detail(visit_id: str, visit: dict, clients: dict) -> None:
    """Exibe todos os blocos relevantes de uma visita selecionada."""
    client = clients.get(visit.get("client_id"), {})
    details = visit.get("company_details")
    details = details if isinstance(details, dict) else {}

    st.markdown("#### 🏢 Dados da empresa")
    st.markdown(
        f"**{html.escape(str(visit.get('client_name', client.get('name', '—'))))}**  \n"
        f"**CNPJ:** {html.escape(str(client.get('cnpj', details.get('cnpj', '—'))))}  \n"
        f"**Responsável:** {html.escape(str(details.get('responsible') or client.get('responsible', '—')))}  \n"
        f"**Endereço:** {html.escape(str(details.get('address') or client.get('address', '—')))}  \n"
        f"**Cidade/UF:** {html.escape(str(details.get('city', '—')))} / "
        f"{html.escape(str(details.get('state', '—')))}  \n"
        f"**Segmento:** {html.escape(str(details.get('segment', '—')))}"
    )

    st.markdown("#### 📋 Dados da visita")
    st.markdown(
        f"**ID:** `{visit_id}`  \n"
        f"**Data:** {html.escape(str(visit.get('date_start') or visit.get('date', '—')))} "
        f"até {html.escape(str(visit.get('date_end') or '—'))}  \n"
        f"**Horário:** {html.escape(str(visit.get('horario') or '—'))}  \n"
        f"**Técnico:** {html.escape(str(visit.get('technician', '—')))}  \n"
        f"**Tipo:** {html.escape(str(visit.get('visit_type') or '—'))}  \n"
        f"**Status:** {status_badge(visit.get('status', 'Rascunho'))}  \n"
        f"**Objetivo:** {html.escape(str(visit.get('objective') or '—'))}",
        unsafe_allow_html=True,
    )

    st.markdown("#### ✅ Checklist de Segurança do Trabalho")
    answers = visit.get("sst_checklist")
    answers = answers if isinstance(answers, dict) else {}
    sst_observations = get_sst_observations(visit)
    summary = summarize_sst(answers)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Conforme", summary["Conforme"])
    c2.metric("Não conforme", summary["Não conforme"])
    c3.metric("Não aplicável", summary["Não aplicável"])
    c4.metric("Não avaliado", summary["Não avaliado"])

    for category_key, category in SST_CATEGORIES.items():
        with st.expander(f"{category['icon']} {category['title']}"):
            for item in category["items"]:
                st.markdown(
                    f"- **{item['label']}:** {html.escape(str(answers.get(item['id'], 'Não avaliado')))}"
                )
            observation = sst_observations.get(category_key, "")
            if observation:
                st.markdown(
                    f"**{SST_OBSERVATION_LABEL}:** {html.escape(observation)}"
                )

    st.markdown("#### 📝 Observações técnicas")
    observations = visit.get("technical_observations")
    observations = observations if isinstance(observations, dict) else {}
    for label, key in (
        ("Observações gerais", "general"),
        ("Riscos identificados", "risks"),
        ("Não conformidades", "non_conformities"),
        ("Recomendações", "recommendations"),
        ("Ações necessárias", "actions"),
        ("Prazo recomendado", "deadline"),
    ):
        value = observations.get(key) or visit.get("observations", "")
        if value:
            st.markdown(f"**{label}:** {html.escape(str(value))}")

    photos = visit.get("photos")
    if isinstance(photos, list) and photos:
        st.markdown(f"#### 📷 Fotografias ({len(photos)})")
        for photo in photos:
            path = str(photo.get("path", ""))
            caption = str(photo.get("description") or photo.get("filename", "Fotografia"))
            if path:
                try:
                    st.image(path, caption=caption, width=220)
                except Exception:
                    st.caption(f"Fotografia indisponível: {caption}")

    st.markdown(
        f"**Criada em:** {html.escape(str(visit.get('created_at', '—')))}  \n"
        f"**Atualizada em:** {html.escape(str(visit.get('updated_at', '—')))}"
    )


def render_visit_history_view():
    """Página 'Histórico de Visitas' integrada ao roteador principal."""
    render_acnnorte_logo(size="medium", subtitle="Histórico, Consulta e Gestão de Visitas")
    render_section_title(
        "Histórico de visitas técnicas",
        "Filtre, inspecione e gerencie todos os registros persistidos.",
        "🗂️",
    )

    visits = load_visits()
    clients = load_clients()
    if not visits:
        render_empty_state(
            "🗂️",
            "Nenhuma visita cadastrada ainda",
            "Cadastre uma nova visita para começar a montar o histórico.",
        )
        if st.button("➕ Nova visita", key="history_new_visit_empty", type="primary"):
            navigate_to(PAGE_VISITS)
        return

    with st.expander("🔎 Filtros", expanded=True):
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        c5, c6 = st.columns(2)
        with c1:
            company = st.text_input("Empresa", key="hist_filter_company")
        with c2:
            technician = st.text_input("Técnico responsável", key="hist_filter_technician")
        with c3:
            status = st.selectbox(
                "Status", [""] + list(VISIT_STATUSES), key="hist_filter_status"
            )
        with c4:
            types = sorted({str(v.get("visit_type", "")).strip() for v in visits.values()})
            types = [value for value in types if value]
            visit_type = st.selectbox(
                "Tipo de visita", [""] + types, key="hist_filter_type"
            )
        with c5:
            start_date = st.date_input("De", value=None, key="hist_filter_start")
        with c6:
            end_date = st.date_input("Até", value=None, key="hist_filter_end")
        if st.button("🧹 Limpar filtros", key="hist_clear_filters"):
            for key in (
                "hist_filter_company",
                "hist_filter_technician",
                "hist_filter_status",
                "hist_filter_type",
                "hist_filter_start",
                "hist_filter_end",
            ):
                st.session_state.pop(key, None)
            st.rerun()

    filtered = filter_visits(
        visits,
        company=company,
        start_date=start_date,
        end_date=end_date,
        technician=technician,
        status=status,
        visit_type=visit_type,
    )

    st.caption(f"{len(filtered)} de {len(visits)} visitas encontradas.")
    if not filtered:
        render_empty_state(
            "🔍",
            "Nenhuma visita corresponde aos filtros",
            "Ajuste os filtros acima ou limpe a consulta.",
        )
        return

    st.dataframe(
        build_history_dataframe(filtered, clients),
        hide_index=True,
        width="stretch",
    )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    render_section_title("Detalhes da visita", "Selecione um registro para inspecionar.", "🔍")
    options = {
        f"#{vid} — {v.get('client_name', '—')} ({v.get('date', '—')})": vid
        for vid, v in filtered.items()
    }
    selected_label = st.selectbox("Visita", list(options.keys()), key="history_detail_select")
    selected_id = options[selected_label]
    selected_visit = visits[selected_id]

    with st.expander("Ver registro completo", expanded=False):
        _render_detail(selected_id, selected_visit, clients)

    a1, a2, a3 = st.columns(3)
    with a1:
        if st.button("✍️ Editar visita", key="history_edit", width="stretch"):
            st.session_state["active_visit_id"] = selected_id
            navigate_to(PAGE_VISITS, visits_tab=VISITS_TAB_FILL)
    with a2:
        new_status = st.selectbox(
            "Atualizar status",
            list(VISIT_STATUSES),
            index=list(VISIT_STATUSES).index(selected_visit.get("status", "Rascunho"))
            if selected_visit.get("status", "Rascunho") in VISIT_STATUSES
            else 0,
            key="history_new_status",
        )
        if st.button("💾 Salvar status", key="history_save_status", width="stretch"):
            ok, message = set_visit_status(selected_id, new_status)
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)
    with a3:
        if st.button("📊 Abrir relatórios", key="history_reports", width="stretch"):
            navigate_to(PAGE_REPORTS)

    r1, r2 = st.columns(2)
    with r1:
        if st.button("🚀 Gerar PDF desta visita", key="history_generate_pdf", width="stretch"):
            try:
                pdf_path = generate_pdf_report(selected_id)
            except Exception:
                pdf_path = None
            if pdf_path:
                try:
                    with open(pdf_path, "rb") as pdf_file:
                        st.download_button(
                            "📥 Baixar PDF",
                            data=pdf_file.read(),
                            file_name=f"Relatorio_Visita_{selected_id}.pdf",
                            mime="application/pdf",
                            key="history_download_pdf",
                            width="stretch",
                        )
                except OSError:
                    st.error("Não foi possível ler o PDF gerado.")
            else:
                st.error("Não foi possível gerar o PDF. Tente novamente.")
    with r2:
        if st.button("📊 Exportar histórico XLSX", key="history_export_xlsx", width="stretch"):
            try:
                xlsx_path = export_visits_to_excel()
            except Exception:
                xlsx_path = None
            if xlsx_path:
                try:
                    with open(xlsx_path, "rb") as xlsx_file:
                        st.download_button(
                            "📥 Baixar planilha",
                            data=xlsx_file.read(),
                            file_name="Visitas_Tecnicas_ACNnorte.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="history_download_xlsx",
                            width="stretch",
                        )
                except OSError:
                    st.error("Não foi possível ler a planilha gerada.")
            else:
                st.error("Não há visitas para exportar.")
