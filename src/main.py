import html
import sys
from pathlib import Path

# Os módulos usam imports absolutos ``src.*``. Quando a aplicação é iniciada por
# um caminho completo (por exemplo, ``streamlit run .../src/main.py``) a pasta
# raiz pode não entrar automaticamente no ``sys.path``. Este único ajuste no
# orquestrador mantém a execução consistente de qualquer diretório, sem
# duplicar mecanismos de importação nos módulos filhos.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from src.auth_manager import get_active_user_by_id, init_db, session_user_is_admin
from src.features import initialize_features
from src.storage_manager import StorageError, init_storage
from src.ui_components import (
    CLIENTS_TAB_NEW,
    NAV_ITEMS,
    PAGE_ADMIN,
    PAGE_CLIENTS,
    PAGE_DASHBOARD,
    PAGE_HISTORY,
    PAGE_PHOTOS,
    PAGE_PROFILE,
    PAGE_REPORTS,
    PAGE_VISITS,
    SIDEBAR_OPEN_KEY,
    VISITS_TAB_LIST,
    VISITS_TAB_NEW,
    apply_global_styles,
    apply_pending_state,
    navigate_to,
    render_acnnorte_logo,
    render_flash,
    render_sidebar_toggle,
    render_sync_indicator,
    request_sidebar_close,
)
from src.views.admin_view import render_admin_view
from src.views.clients_view import render_clients_view
from src.views.dashboard_main import render_main_dashboard
from src.views.login_view import render_login_view
from src.views.photos_view import render_photos_view
from src.views.profile_view import render_profile_view
from src.views.reports_view import render_reports_view
from src.views.visits_view import render_visits_view
from src.views.history_view import render_visit_history_view

def _render_new_visit_page():
    """Rota 'Nova Visita': abre diretamente o formulário de cadastro."""
    if st.session_state.get("visits_tab", VISITS_TAB_LIST) == VISITS_TAB_LIST:
        st.session_state["visits_tab"] = VISITS_TAB_NEW
    render_visits_view()


PAGE_RENDERERS = {
    PAGE_DASHBOARD: render_main_dashboard,
    PAGE_CLIENTS: render_clients_view,
    PAGE_VISITS: _render_new_visit_page,
    PAGE_HISTORY: render_visit_history_view,
    PAGE_PHOTOS: render_photos_view,
    PAGE_REPORTS: render_reports_view,
    PAGE_PROFILE: render_profile_view,
    PAGE_ADMIN: render_admin_view,
}

SESSION_KEYS = (
    "authenticated",
    "username",
    "user_id",
    "user_role",
    "is_admin",
    "auth_source",
    "xano_token",
    "xano_user",
    "user_email",
    "current_page",
    "active_visit_id",
    "visits_tab",
    "clients_tab",
    "xano_remote_visits",
    "xano_smoke_result",
    "login_user",
)

# Configuração única do Streamlit. O menu inicia expandido conforme a
# especificação do dashboard; o estado posterior é controlado pelos controles
# nativos e pelo botão "☰ Menu", preservando a navegação mobile-first.
PAGE_CONFIG = {
    "page_title": "ACNnorte",
    "page_icon": "🛡️",
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}


def _render_xano_smoke_test() -> None:
    """Teste opcional de conectividade com o backend Xano."""
    from src.core.database.xano_client import smoke_test

    if st.button(
        "🔌 Testar conexão com o Xano",
        key="xano_smoke_test",
        width="stretch",
        help="Verifica se o API group do Xano está acessível.",
    ):
        with st.spinner("Testando conexão com o Xano..."):
            st.session_state["xano_smoke_result"] = smoke_test()

    result = st.session_state.get("xano_smoke_result")
    if result is None:
        return
    if not result.ok:
        st.error(result.message)
    elif result.authenticated:
        st.success(result.message)
    else:
        st.info(result.message)


def _render_sidebar(is_admin: bool):
    """Menu lateral com perfil, navegação, atalhos e indicador de sincronização."""
    current_page = st.session_state.get("current_page", PAGE_DASHBOARD)

    with st.sidebar:
        # Botão de fechamento próprio, sempre no topo e com área de toque
        # confortável. Funciona em conjunto com o controle nativo do Streamlit.
        if st.button(
            "✕ Fechar menu",
            key="sidebar_close_menu",
            help="Recolher o menu lateral",
            width="stretch",
        ):
            request_sidebar_close()

        render_acnnorte_logo(width=200)

        username = html.escape(str(st.session_state.get("username", "Usuário")))
        role = "Administrador" if is_admin else "Usuário"
        st.markdown(
            f"""
            <div class="acn-user-card">
                <div class="acn-user-name">👤 <b>{username}</b></div>
                <div class="acn-user-role">{username} - {role}</div>
                <div class="acn-user-caption">Sessão ativa neste dispositivo</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for page, icon, description in NAV_ITEMS:
            # "Alterar Senha" permanece como rota interna, mas fora do menu.
            # "Gerenciar Usuários" é exibido somente quando o perfil ADM vem
            # do cadastro do usuário identificado na sessão.
            if page == PAGE_PROFILE:
                continue
            if page == PAGE_ADMIN and not is_admin:
                continue
            if st.button(
                f"{icon} {page}",
                key=f"nav_{page}",
                help=description,
                type="primary" if current_page == page else "secondary",
                width="stretch",
            ):
                navigate_to(page)

        st.markdown(
            '<div class="acn-nav-label">Acesso rápido</div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "➕ Cadastrar cliente",
            key="quick_new_client",
            width="stretch",
            help="Abrir o cadastro de um novo cliente.",
        ):
            navigate_to(PAGE_CLIENTS, clients_tab=CLIENTS_TAB_NEW)
        if st.button(
            "🚀 Nova visita",
            key="quick_new_visit",
            width="stretch",
            help="Iniciar uma nova visita técnica.",
        ):
            navigate_to(PAGE_VISITS, visits_tab=VISITS_TAB_NEW)
        if st.button(
            "🗂️ Histórico de visitas",
            key="quick_visit_history",
            width="stretch",
            help="Consultar, filtrar e gerenciar as visitas registradas.",
        ):
            navigate_to(PAGE_HISTORY)

        _render_xano_smoke_test()
        render_sync_indicator()

        if st.button("🚪 Sair", key="logout", width="stretch"):
            # Encerra a identificação, o perfil e os resíduos da sessão; o
            # próximo acesso volta à tela de login.
            for key in SESSION_KEYS:
                st.session_state.pop(key, None)
            st.session_state["current_page"] = PAGE_DASHBOARD
            st.rerun()


def main():
    st.set_page_config(**PAGE_CONFIG)

    # Inicialização única e idempotente do armazenamento local.
    try:
        init_db()
        init_storage()
        # Carrega o registro central de extensões (temperatura, assinaturas,
        # equipamentos, fotografias, relatórios e integração) antes das telas.
        initialize_features()
    except StorageError as exc:
        st.error(str(exc))
        return
    except Exception:
        st.error("Não foi possível preparar os dados do sistema. Tente novamente.")
        return
    apply_global_styles()

    # Intenção do usuário para o menu lateral; nunca é sobrescrita em reruns.
    st.session_state.setdefault(SIDEBAR_OPEN_KEY, True)

    st.session_state.setdefault("authenticated", False)

    apply_pending_state()

    if not st.session_state.get("authenticated", False):
        # A tela de login não tem sidebar; o botão de menu só faz sentido
        # depois da autenticação.
        render_login_view()
        return

    # Revalida a identificação no cadastro real a cada execução. Sessões de
    # usuários removidos ou desativados voltam imediatamente para o login.
    active_record = get_active_user_by_id(
        str(st.session_state.get("user_id") or "")
    )
    if not isinstance(active_record, dict):
        for key in SESSION_KEYS:
            st.session_state.pop(key, None)
        st.session_state["current_page"] = PAGE_DASHBOARD
        render_login_view()
        return

    st.session_state["username"] = str(
        active_record.get("name") or st.session_state.get("username") or "Usuário"
    )
    is_admin = session_user_is_admin()
    st.session_state["is_admin"] = is_admin
    current_page = st.session_state.get("current_page", PAGE_DASHBOARD)
    if current_page == PAGE_ADMIN and not is_admin:
        current_page = PAGE_DASHBOARD
    if current_page not in PAGE_RENDERERS:
        current_page = PAGE_DASHBOARD
    st.session_state["current_page"] = current_page

    _render_sidebar(is_admin)
    render_sidebar_toggle()
    render_flash()

    renderer = PAGE_RENDERERS.get(current_page, render_main_dashboard)
    try:
        renderer()
    except StorageError as exc:
        st.error(str(exc))
    except Exception:
        st.error("Não foi possível carregar esta tela. Tente novamente.")


if __name__ == "__main__":
    main()
