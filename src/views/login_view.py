"""Tela de login simplificada do ACNnorte.

A identificação é feita apenas pela seleção do nome cadastrado. Não há senha,
pesquisa de usuários nem código administrativo: o perfil ADM é lido do próprio
cadastro, por meio do identificador interno do usuário selecionado.

Este modelo não verifica identidade e é adequado somente para uso em ambiente
controlado, sem exposição pública.
"""

import streamlit as st

from src.auth_manager import find_user_record, list_login_users
from src.ui_components import LOGIN_LOGO_PATH, render_acnnorte_logo


def _persist_session(user_key: str, record: dict) -> None:
    """Registra na sessão a identificação e o perfil vindos do cadastro."""
    is_admin_record = bool(record.get("is_admin", False))
    st.session_state["authenticated"] = True
    st.session_state["username"] = str(record.get("name") or user_key)
    st.session_state["user_id"] = str(record.get("user_id") or "")
    st.session_state["user_role"] = "administrador" if is_admin_record else "usuario"
    st.session_state["is_admin"] = is_admin_record
    st.session_state["auth_source"] = "local"

    # O login por seleção não produz token Xano; evita reaproveitar uma sessão
    # remota de outro usuário no mesmo navegador.
    for key in ("xano_token", "xano_user", "user_email"):
        st.session_state.pop(key, None)


def _render_login_form() -> None:
    users = list_login_users()
    if not users:
        st.error(
            "Nenhum usuário ativo foi encontrado. Contate o administrador do "
            "sistema para verificar o cadastro."
        )
        return

    names_by_id = {user["id"]: user["name"] for user in users}
    selected_id = st.selectbox(
        "Selecione seu nome",
        options=list(names_by_id.keys()),
        index=None,
        format_func=lambda value: names_by_id.get(value, value),
        key="login_user",
    )

    if st.button(
        "ENTRAR",
        key="login_submit",
        type="primary",
        width="stretch",
    ):
        if not selected_id:
            st.error("Selecione seu nome na lista para entrar.")
            return

        user_key, record = find_user_record(selected_id)
        if not isinstance(record, dict) or not record.get("active", True):
            st.error(
                "Este usuário não está disponível. Atualize a página e tente "
                "novamente."
            )
            return

        _persist_session(user_key, record)
        st.success("Acesso autorizado. Abrindo o ACNnorte...")
        st.rerun()


def render_login_view():
    """Renderiza a tela de identificação com a logo oficial da ACNnorte."""
    left, center, right = st.columns([1, 1.7, 1])
    with center:
        render_acnnorte_logo(
            width=520,
            subtitle="Segurança do Trabalho",
            logo_path=str(LOGIN_LOGO_PATH),
        )
        st.markdown(
            "<h2 style='text-align:center;margin:0.35rem 0 0;'>"
            "Bem-vindo(a) ao ACNnorte</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center;color:#5b6573;margin:0 0 1.2rem;'>"
            "Selecione seu nome para acessar o sistema.</p>",
            unsafe_allow_html=True,
        )
        _render_login_form()
