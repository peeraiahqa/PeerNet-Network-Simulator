from __future__ import annotations

import os
from typing import Any

import streamlit as st
from supabase import Client, create_client


def _secret(name: str) -> str:
    value = ""
    try:
        value = str(st.secrets.get(name, "") or "")
    except Exception:
        value = ""
    return value.strip() or os.getenv(name, "").strip()


@st.cache_resource
def get_supabase() -> Client:
    url = _secret("SUPABASE_URL")
    key = _secret("SUPABASE_KEY") or _secret("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError(
            "Supabase is not configured. Add SUPABASE_URL and SUPABASE_KEY "
            "to .env locally or Streamlit Community Cloud Secrets."
        )
    return create_client(url, key)


def sign_in(email: str, password: str) -> Any:
    if not email.strip().lower().endswith("@gmail.com"):
        raise ValueError("Please enter a valid Gmail address.")
    response = get_supabase().auth.sign_in_with_password(
        {"email": email.strip().lower(), "password": password}
    )
    if not getattr(response, "session", None):
        raise RuntimeError("Login failed. Verify your email and password.")
    return response


def sign_up(email: str, password: str, full_name: str) -> Any:
    if not email.strip().lower().endswith("@gmail.com"):
        raise ValueError("Registration currently requires a Gmail address.")
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")
    return get_supabase().auth.sign_up(
        {
            "email": email.strip().lower(),
            "password": password,
            "options": {"data": {"full_name": full_name.strip()}},
        }
    )


def send_password_reset(email: str) -> None:
    if not email.strip().lower().endswith("@gmail.com"):
        raise ValueError("Please enter a valid Gmail address.")
    get_supabase().auth.reset_password_email(email.strip().lower())


def sign_out() -> None:
    try:
        get_supabase().auth.sign_out()
    finally:
        st.session_state.authenticated = False
        st.session_state.user_email = ""
        st.session_state.user_name = ""
