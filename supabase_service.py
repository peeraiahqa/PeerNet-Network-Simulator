from __future__ import annotations

import os
from typing import Any

import streamlit as st
from supabase import Client, create_client


def _secret(name: str) -> str:
    """Read a secret from Streamlit Secrets first, then environment variables."""
    try:
        value = str(st.secrets.get(name, "") or "").strip()
    except Exception:
        value = ""

    return value or os.getenv(name, "").strip()


@st.cache_resource
def create_user_client() -> Client:
    url = _secret("SUPABASE_URL")
    anon_key = _secret("SUPABASE_ANON_KEY") or _secret("SUPABASE_KEY")

    if not url or not anon_key:
        raise RuntimeError(
            "Supabase is not configured. Add SUPABASE_URL and "
            "SUPABASE_ANON_KEY to .env locally or Streamlit Cloud Secrets."
        )

    return create_client(url, anon_key)


def get_client() -> Client:
    client = create_user_client()
    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")

    if access_token and refresh_token:
        try:
            client.auth.set_session(access_token, refresh_token)
        except Exception:
            clear_auth_state()

    return client


def save_session(auth_response: Any) -> None:
    session = getattr(auth_response, "session", None)
    user = getattr(auth_response, "user", None)

    if not session or not user:
        return

    metadata = getattr(user, "user_metadata", {}) or {}

    st.session_state.access_token = session.access_token
    st.session_state.refresh_token = session.refresh_token
    st.session_state.user_id = user.id
    st.session_state.user_email = user.email or ""
    st.session_state.user_name = (
        metadata.get("full_name")
        or metadata.get("username")
        or (user.email or "PeerNet User").split("@")[0]
    )
    st.session_state.authenticated = True


def clear_auth_state() -> None:
    for key in (
        "access_token",
        "refresh_token",
        "user_id",
        "user_email",
        "user_name",
        "authenticated",
        "current_project_id",
        "current_project_name",
    ):
        st.session_state.pop(key, None)

    st.session_state.authenticated = False


def sign_in(email: str, password: str) -> Any:
    cleaned_email = email.strip().lower()

    if not cleaned_email.endswith("@gmail.com"):
        raise ValueError("Please enter a valid Gmail address.")

    response = get_client().auth.sign_in_with_password(
        {"email": cleaned_email, "password": password}
    )

    if not getattr(response, "session", None):
        raise RuntimeError("Login failed. Verify your email and password.")

    save_session(response)
    return response


def sign_up(
    email: str,
    password: str,
    full_name: str,
    username: str = "",
) -> Any:
    cleaned_email = email.strip().lower()

    if not cleaned_email.endswith("@gmail.com"):
        raise ValueError("Registration currently requires a Gmail address.")

    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")

    return get_client().auth.sign_up(
        {
            "email": cleaned_email,
            "password": password,
            "options": {
                "data": {
                    "full_name": full_name.strip(),
                    "username": username.strip().lower(),
                }
            },
        }
    )


def send_password_reset(email: str) -> None:
    cleaned_email = email.strip().lower()

    if not cleaned_email.endswith("@gmail.com"):
        raise ValueError("Please enter a valid Gmail address.")

    get_client().auth.reset_password_for_email(cleaned_email)


def resend_verification(email: str) -> None:
    cleaned_email = email.strip().lower()

    if not cleaned_email.endswith("@gmail.com"):
        raise ValueError("Please enter a valid Gmail address.")

    get_client().auth.resend(
        {
            "type": "signup",
            "email": cleaned_email,
        }
    )


def sign_out() -> None:
    try:
        get_client().auth.sign_out()
    finally:
        clear_auth_state()


def list_simulator_projects() -> list[dict[str, Any]]:
    user_id = st.session_state.get("user_id")
    if not user_id:
        return []

    response = (
        get_client()
        .table("simulator_projects")
        .select("*")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )

    return response.data or []


def create_simulator_project(
    name: str,
    topology_json: dict[str, Any],
    description: str = "",
) -> dict[str, Any]:
    user_id = st.session_state["user_id"]

    response = (
        get_client()
        .table("simulator_projects")
        .insert(
            {
                "user_id": user_id,
                "name": name.strip() or "Untitled topology",
                "description": description.strip(),
                "topology_json": topology_json,
            }
        )
        .select("*")
        .execute()
    )

    if not response.data:
        raise RuntimeError("Supabase did not return the created project.")

    return response.data[0]


def update_simulator_project(
    project_id: str,
    name: str,
    topology_json: dict[str, Any],
    description: str = "",
) -> dict[str, Any]:
    user_id = st.session_state["user_id"]

    response = (
        get_client()
        .table("simulator_projects")
        .update(
            {
                "name": name.strip() or "Untitled topology",
                "description": description.strip(),
                "topology_json": topology_json,
                "updated_at": "now()",
            }
        )
        .eq("id", project_id)
        .eq("user_id", user_id)
        .select("*")
        .execute()
    )

    if not response.data:
        raise RuntimeError("Project could not be updated.")

    return response.data[0]


def load_simulator_project(project_id: str) -> dict[str, Any]:
    user_id = st.session_state["user_id"]

    response = (
        get_client()
        .table("simulator_projects")
        .select("*")
        .eq("id", project_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        raise ValueError("Simulator project not found.")

    return response.data[0]


def delete_simulator_project(project_id: str) -> None:
    user_id = st.session_state["user_id"]

    (
        get_client()
        .table("simulator_projects")
        .delete()
        .eq("id", project_id)
        .eq("user_id", user_id)
        .execute()
    )
