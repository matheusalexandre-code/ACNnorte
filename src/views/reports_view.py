import html
import os

import streamlit as st

from src.checklist_sst import (
    SST_CATEGORIES,
    SST_OBSERVATION_LABEL,
    get_sst_observations,
    summarize_sst,
)
from src.export_manager import EXPORTS_DIR
from src.features.visit_enhancements.reports import (
    generate_clients_excel_download,
    generate_visit_pdf_download,
    generate_visits_excel_download,
)
from src.storage_bridge import storage_root
from src.storage_manager import load_clients, load_visits
from src.ui_components import (
    render_acnnorte_logo,
    render_empty_state,
    render_section_title,
    status_badge,
)


def _render_report_preview(visit: dict, clients: dict) -> None:
    """Prévia fiel aos dados persistidos da visita selecionada."""
    client = clients.get(visit.get("client_id"), {})
    details = visit.get("company_details")
    details = details if isinstance(details, dict) else {}
    summary = summarize_sst(visit.get("sst_checklist"))

    st.markdown("##### 🛡️ ACNnorte — Relatório Técnico de Visita")
    st.markdown(
        f"**Empresa:** {visit.get('client_name', client.get('name', '—'))}  \n"
        f"**CNPJ:** {client.get('cnpj', details.get('cnpj', '—'))}  \n"
        f"**Responsável:** {details.get('responsible') or client.get('responsible', '—')}  \n"
        f"**Técnico responsável:** {visit.get('technician', '—')}  \n"
        f"**Data da visita:** {visit.get('date_start') or visit.get('date', '—')}  \n"
        f"**Objetivo:** {visit.get('objective') or '—'}"
    )

    st.markdown("**Resumo do checklist:**", help="Checklist de apoio; não substitui avaliação profissional.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Conforme", summary["Conforme"])
    c2.metric("Não conforme", summary["Não conforme"])
    c3.metric("Não aplicável", summary["Não aplicável"])

    for issue in summary["non_conformities"]:
        st.warning(f"**{issue['categoria']}** — {issue['item']}")

    sst_observations = get_sst_observations(visit)
    for category_key, category in SST_CATEGORIES.items():
        observation = sst_observations.get(category_key, "")
        if observation:
            st.markdown(
                f"**{html.escape(category['title'])}** — {SST_OBSERVATION_LABEL}: "
                f"{html.escape(observation)}"
            )

    observations = visit.get("technical_observations")
    observations = observations if isinstance(observations, dict) else {}
    labels = (
        ("Riscos identificados", "risks"),
        ("Recomendações", "recommendations"),
        ("Observações", "general"),
        ("Conclusão técnica", "conclusions"),
    )
    for label, key in labels:
        value = observations.get(key) or visit.get(key, "")
        if value:
            st.markdown(f"**{label}:** {value}")

    photos = visit.get("photos")
    if isinstance(photos, list) and photos:
        st.markdown(f"**Fotografias relacionadas ({len(photos)})**")
        for photo in photos[:6]:
            path = str(photo.get("path", ""))
            if path and os.path.exists(path):
                st.image(path, caption=str(photo.get("description") or ""), width=180)


def render_reports_view():
    render_acnnorte_logo(size="medium", subtitle="Relatórios em PDF e Exportação Excel (XLSX)")

    visits = load_visits()
    clients = load_clients()

    tab_pdf, tab_excel = st.tabs(
        ["📄 Relatório PDF", "📊 Exportação Excel (XLSX)"]
    )

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------
    with tab_pdf:
        render_section_title(
            "Relatório profissional em PDF",
            "Gere o documento da visita com a identidade visual da ACNnorte.",
            "📄",
        )

        if not visits:
            render_empty_state("📄", "Nenhuma visita para relatar", "Registre uma visita técnica primeiro.")
        else:
            only_completed = st.checkbox(
                "Somente visitas concluídas (relatório final)",
                value=False,
                key="report_only_completed",
            )
            candidates = (
                {
                    v_id: v
                    for v_id, v in visits.items()
                    if v.get("status") == "Finalizada"
                }
                if only_completed
                else visits
            )
            if not candidates:
                render_empty_state(
                    "📄",
                    "Nenhuma visita concluída",
                    "Finalize uma visita no histórico para gerar o relatório final.",
                )
            else:
                visit_options = {
                    f"Visita #{v_id} — {v.get('client_name', '—')} ({v.get('date', '—')}) • {v.get('status', 'Rascunho')}": v_id
                    for v_id, v in candidates.items()
                }
                selected_label = st.selectbox(
                    "Selecione a visita",
                    list(visit_options.keys()),
                    key="report_visit_select",
                )
                selected_v_id = visit_options[selected_label]
                selected_visit = visits[selected_v_id]

                st.markdown(
                    f"**Empresa:** {selected_visit.get('client_name', '—')} &nbsp;|&nbsp; "
                    f"**Técnico:** {selected_visit.get('technician', '—')} &nbsp;|&nbsp; "
                    f"**Situação:** {status_badge(selected_visit.get('status', 'Rascunho'))}",
                    unsafe_allow_html=True,
                )

                with st.expander("👁️ Pré-visualização do relatório", expanded=True):
                    _render_report_preview(selected_visit, clients)

                st.caption(
                    f"Os PDFs também são arquivados em: "
                    f"{storage_root() / 'storage' / 'reports'} (origem: {EXPORTS_DIR})."
                )

                if st.button("🚀 Gerar relatório PDF", key="generate_pdf", type="primary", width="stretch"):
                    with st.spinner("Gerando relatório..."):
                        try:
                            pdf_download = generate_visit_pdf_download(selected_v_id)
                        except Exception:
                            pdf_download = None

                    if pdf_download:
                        st.session_state["pdf_download"] = pdf_download
                        st.toast("Relatório PDF gerado com sucesso!")
                    else:
                        st.session_state.pop("pdf_download", None)
                        st.error("Não foi possível gerar o relatório agora. Tente novamente.")

                pdf_download = st.session_state.get("pdf_download")
                if pdf_download:
                    st.success("Relatório pronto para download.")
                    st.download_button(
                        label="📥 Baixar arquivo PDF",
                        data=pdf_download["data"],
                        file_name=pdf_download["name"],
                        mime=pdf_download.get("mime", "application/pdf"),
                        width="stretch",
                    )

    # ------------------------------------------------------------------
    # Excel
    # ------------------------------------------------------------------
    with tab_excel:
        render_section_title(
            "Exportação para Microsoft Excel",
            "Baixe planilhas com os cadastros de clientes e o histórico de visitas.",
            "📊",
        )

        col_clients, col_visits = st.columns(2)

        with col_clients:
            st.markdown("#### 🏢 Clientes cadastrados")
            st.caption(f"Total de clientes no sistema: {len(clients)}")
            if st.button("📊 Gerar planilha de clientes", key="export_clients", width="stretch"):
                with st.spinner("Gerando planilha de clientes..."):
                    try:
                        clients_download = generate_clients_excel_download()
                    except Exception:
                        clients_download = None
                if clients_download:
                    st.session_state["excel_clients"] = clients_download
                    st.toast("Planilha de clientes gerada com sucesso!")
                else:
                    st.session_state.pop("excel_clients", None)
                    st.error("Não há clientes cadastrados para exportar.")

            excel_clients = st.session_state.get("excel_clients")
            if excel_clients:
                st.download_button(
                    label="📥 Baixar Excel de clientes",
                    data=excel_clients["data"],
                    file_name=excel_clients["name"],
                    mime=excel_clients.get("mime", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    width="stretch",
                )

        with col_visits:
            st.markdown("#### 🛡️ Visitas técnicas")
            st.caption(f"Total de visitas registradas: {len(visits)}")
            if st.button("📊 Gerar planilha de visitas", key="export_visits", width="stretch"):
                with st.spinner("Gerando planilha de visitas..."):
                    try:
                        visits_download = generate_visits_excel_download()
                    except Exception:
                        visits_download = None
                if visits_download:
                    st.session_state["excel_visits"] = visits_download
                    st.toast("Planilha de visitas gerada com sucesso!")
                else:
                    st.session_state.pop("excel_visits", None)
                    st.error("Não há visitas registradas para exportar.")

            excel_visits = st.session_state.get("excel_visits")
            if excel_visits:
                st.download_button(
                    label="📥 Baixar Excel de visitas",
                    data=excel_visits["data"],
                    file_name=excel_visits["name"],
                    mime=excel_visits.get("mime", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    width="stretch",
                )
