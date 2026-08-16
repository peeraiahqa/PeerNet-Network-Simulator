from __future__ import annotations

"""
PeerNet Network Simulator authentication facade.

Authentication is backed by the same Supabase Auth service configured by
SUPABASE_URL + SUPABASE_ANON_KEY. This makes it possible for an existing
PeerNet AI account to sign in to the Simulator when both applications use
the same Supabase project.

Simulator application data is NOT stored here. Saved labs are handled by
supabase_service.py in the simulator-specific `simulator_projects` table.
"""

from typing import Any

from supabase_service import (
    clear_auth_state,
    get_client,
    resend_verification,
    save_session,
    send_password_reset,
    sign_in,
    sign_out,
    sign_up,
)

__all__ = [
    "clear_auth_state",
    "get_client",
    "resend_verification",
    "save_session",
    "send_password_reset",
    "sign_in",
    "sign_out",
    "sign_up",
]
