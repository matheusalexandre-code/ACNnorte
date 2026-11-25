"""Tela de login simplificada do ACNnorte.

O fluxo comum identifica o usuário pela seleção do nome, sem senha. O perfil
administrativo exige uma autorização separada, verificada exclusivamente no
servidor por meio da variável de ambiente ``ACN_ADMIN_ACCESS_CODE``.
"""

from datetime import datetime

import streamlit as st

from src.auth_manager import (
    admin_access_configured,
    find_user_record,
    list_login_users,
    verify_admin_access_code,
)
from src.ui_components import LOGIN_LOGO_PATH, render_acnnorte_logo


def _persist_session(
    user_key: str,
    record: dict,
    admin_authorized: bool = False,
) -> None:
    """Grava a sessão com identificação e autorização claramente separadas."""
    is_admin_record = bool(record.get("is_admin", False))
    st.session_state["authenticated"] = True
    st.session_state["username"] = str(record.get("name") or user_key)
    st.session_state["user_id"] = str(record.get("user_id") or "")
    st.session_state["user_role"] = "administrador" if is_admin_record else "usuario"
    st.session_state["is_admin"] = bool(is_admin_record and admin_authorized)
    st.session_state["admin_authorized"] = bool(is_admin_record and admin_authorized)
    st.session_state["admin_authorized_at"] = (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if is_admin_record and admin_authorized
        else None
    )
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

    search = st.text_input(
        "Pesquisar usuário",
        placeholder="Digite parte do nome para localizar seu cadastro",
        key="login_search",
    ).strip()
    filtered = [
        user
        for user in users
        if not search or search.casefold() in user["name"].casefold()
    ]

    selected_id = None
    selected_user = None
    if filtered:
        names_by_id = {user["id"]: user["name"] for user in filtered}
        selected_id = st.selectbox(
            "Selecione seu nome",
            options=list(names_by_id.keys()),
            index=None,
            format_func=lambda value: names_by_id.get(value, value),
            placeholder="Digite para pesquisar...",
            key="login_user",
        )
        if selected_id:
            selected_user = next(
                (user for user in filtered if user["id"] == selected_id), None
            )
    else:
        st.warning(
            "Nenhum usuário corresponde à pesquisa. Verifique o nome digitado."
        )

    admin_code = ""
    if selected_user and selected_user.get("is_admin"):
        st.info(
            "Este cadastro possui perfil administrativo. Informe a autorização "
            "administrativa configurada no servidor."
        )
        if not admin_access_configured():
            st.warning(
                "A autorização administrativa não está configurada no servidor. "
                "Defina a variável ACN_ADMIN_ACCESS_CODE para liberar o acesso ADM."
            )
        admin_code = st.text_input(
            "Autorização administrativa",
            type="password",
            key="login_admin_code",
            help="Código separado do login comum, validado somente no servidor.",
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

        is_admin_record = bool(record.get("is_admin", False))
        if is_admin_record:
            if not admin_access_configured():
                st.error(
                    "A autorização administrativa não está configurada no "
                    "servidor. O acesso ADM permanece bloqueado."
                )
                return
            if not verify_admin_access_code(admin_code):
                st.error("Código de autorização administrativa inválido.")
                return

        _persist_session(user_key, record, admin_authorized=is_admin_record)
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
        st.caption(
            "A identificação por nome não concede privilégios administrativos. "
            "Operações de administração exigem autorização própria do servidor."
        )
