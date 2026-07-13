# dashboard/components/auth_wall.py
import streamlit as st
from dashboard.utils.api_client import login, get_me


def check_auth() -> bool:
    """Returns True if user is authenticated, False otherwise."""
    return bool(st.session_state.get("access_token"))


def show_login_page():
    """Renders the login form. Called when user is not authenticated."""
    st.markdown("""
    <style>
    .login-box {
        max-width: 420px;
        margin: 80px auto;
        padding: 2rem;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        background: white;
    }
    .login-title {
        text-align: center;
        font-size: 1.6rem;
        font-weight: 600;
        color: #003580;
        margin-bottom: 0.25rem;
    }
    .login-sub {
        text-align: center;
        color: #888;
        font-size: 0.9rem;
        margin-bottom: 1.5rem;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-title">🚂 Railways AI</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">India Railways Delay Intelligence Platform</div>', unsafe_allow_html=True)
        st.markdown("---")

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="admin")
            password = st.text_input("Password", type="password", placeholder="Admin@12345")
            submitted = st.form_submit_button("Log In", use_container_width=True, type="primary")

        if submitted:
            if not username or not password:
                st.error("Please enter both username and password")
                return

            with st.spinner("Logging in..."):
                result = login(username, password)

            if result:
                st.session_state["access_token"]  = result["access_token"]
                st.session_state["refresh_token"] = result.get("refresh_token", "")
                me = get_me()
                if me:
                    st.session_state["user"]     = me
                    st.session_state["username"] = me.get("username", username)
                    st.session_state["role"]     = me.get("role", "viewer")
                st.success("Logged in!")
                st.rerun()
            else:
                st.error("Invalid username or password")


def show_sidebar_user():
    """Shows user info and logout button in sidebar."""
    user = st.session_state.get("user", {})
    username = st.session_state.get("username", "User")
    role     = st.session_state.get("role", "viewer")

    with st.sidebar:
        st.markdown("---")
        st.markdown(f"**👤 {username}**")
        st.markdown(f"Role: `{role}`")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()