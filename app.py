from __future__ import annotations

import base64
import copy
import html
import ipaddress
import shutil
import struct
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

from auth import (
    send_password_reset,
    sign_in,
    sign_out,
    sign_up,
)
from supabase_service import (
    create_simulator_project,
    delete_simulator_project,
    list_simulator_projects,
    load_simulator_project,
    update_simulator_project,
)
from topology_component import topology_canvas
from terminal_component import inline_terminal
from switch_cli import (
    DEFAULT_VLANS,
    configure_switchports,
    ensure_switch_defaults,
    is_switch,
    resolve_interface_range,
    show_interface_switchport,
    show_interfaces_status as show_switch_interfaces_status,
    show_interfaces_trunk,
    show_vlan_brief as show_switch_vlan_brief,
    validate_vlan_id,
)
from routing_cli import (
    configure_interface_routing,
    configure_policy,
    configure_route_map_mode,
    configure_router_mode,
    configure_static_route,
    ensure_routing_defaults,
    enter_router_mode,
    is_routing_device,
    routing_running_config,
    show_routing_summary,
)
from routing_engine import evaluate_bidirectional_route, evaluate_route
from network_validation import (
    audit_device,
    audit_topology,
    validate_gateway,
    validate_interface_address,
)
from dhcp_engine import (
    allocate_lease,
    configure_dhcp_global,
    configure_dhcp_pool,
    dhcp_running_config,
    release_lease,
    show_dhcp_bindings,
    show_dhcp_pools,
)
from acl_engine import (
    acl_running_config,
    configure_access_group,
    configure_access_list,
    show_access_lists,
)
from nat_engine import (
    clear_translations,
    configure_nat_global,
    configure_nat_interface,
    nat_running_config,
    show_statistics as show_nat_statistics,
    show_translations as show_nat_translations,
)
from dns_engine import (
    configure_ip_host,
    configure_server_record,
    dns_running_config,
    resolve_name,
    show_records as show_dns_records,
)
from simulator_ai import extract_commands, generate_command_guidance


APP_DIR = Path(__file__).resolve().parent
LOGO = APP_DIR / "assets" / "peernet-solutions-logo.png"
FAVICON = APP_DIR / "assets" / "favicon.png"
LOGIN_ART = APP_DIR / "assets" / "network-lab-illustration.jpg"

st.set_page_config(
    page_title="PeerNet Network Simulator",
    page_icon=str(FAVICON),
    layout="wide",
    initial_sidebar_state="expanded",
)


@dataclass
class Interface:
    name: str
    ip_address: str = ""
    status: str = "up"
    connected_to: Optional[str] = None
    switchport_mode: str = "access"
    access_vlan: int = 1
    native_vlan: int = 1
    trunk_allowed_vlans: list[int] = field(default_factory=list)
    description: str = ""
    ipv6_address: str = ""
    encapsulation_dot1q: Optional[int] = None
    encapsulation_native: bool = False
    ospfv3_process: str = ""
    ospfv3_area: str = ""
    tunnel_source: str = ""
    tunnel_destination: str = ""
    tunnel_mode: str = "gre ip"
    ipsec_profile: str = ""
    access_group_in: str = ""
    access_group_out: str = ""
    nat_inside: bool = False
    nat_outside: bool = False


@dataclass
class Device:
    name: str
    device_type: str
    interfaces: Dict[str, Interface] = field(default_factory=dict)
    routing_table: Dict[str, str] = field(default_factory=dict)
    default_gateway: str = ""
    dns_server: str = ""
    vlans: Dict[int, str] = field(default_factory=dict)
    route_distances: Dict[str, int] = field(default_factory=dict)
    routing_config: dict = field(default_factory=dict)
    startup_config: dict = field(default_factory=dict)


DEVICE_GROUPS = {
    "Network Devices": [
        "Router",
        "Switch",
        "Multilayer Switch",
        "Cisco IOS Firewall",
        "Router/Switch Processor",
        "Access Server",
        "PIX Firewall",
        "Network Cloud",
    ],
    "End Users": [
        "PC",
        "Laptop",
        "Server",
        "Authentication Server",
        "Camera / PC Video",
        "IP Phone",
        "Analog Phone",
    ],
}

DEFAULT_INTERFACES = {
    "Router": [
        "Gi0/0", "Gi0/1", "Gi0/2", "Gi0/3",
        "S0/0/0", "S0/0/1"
    ],
    "Switch": [
        "Gi0/1", "Gi0/2", "Gi0/3", "Gi0/4",
        *[f"Fa0/{port}" for port in range(1, 25)],
    ],
    "Multilayer Switch": [
        "Gi0/1", "Gi0/2", "Gi0/3", "Gi0/4",
        "Gi0/5", "Gi0/6", "Vlan1"
    ],
    "Cisco IOS Firewall": [
        "Gi0/0", "Gi0/1", "Gi0/2", "Gi0/3",
        "Mgmt0/0"
    ],
    "Router/Switch Processor": [
        "Gi0/0", "Gi0/1", "Gi0/2", "Gi0/3"
    ],
    "Access Server": [
        "Gi0/0", "Gi0/1", "Async0", "Async1",
        "Async2", "Async3"
    ],
    "PIX Firewall": [
        "Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"
    ],
    "Network Cloud": [
        "wan0", "wan1", "eth0", "eth1",
        "serial0", "fiber0", "wireless0"
    ],
    "PC": ["eth0", "wlan0"],
    "Laptop": ["eth0", "wlan0"],
    "Server": ["eth0", "eth1"],
    "Authentication Server": ["eth0", "eth1"],
    "Camera / PC Video": ["eth0", "wlan0"],
    "IP Phone": ["switch0", "pc0"],
    "Analog Phone": ["phone0"],
}

PREFIX = {
    "Router": "R",
    "Switch": "SW",
    "Multilayer Switch": "MLS",
    "Cisco IOS Firewall": "FW",
    "Router/Switch Processor": "RSP",
    "Access Server": "AS",
    "PIX Firewall": "PIX",
    "Network Cloud": "ISP",
    "PC": "PC",
    "Laptop": "LAP",
    "Server": "SRV",
    "Authentication Server": "AUTH",
    "Camera / PC Video": "CAM",
    "IP Phone": "PHONE",
    "Analog Phone": "AP",
}


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        #MainMenu, footer, header { visibility:hidden; }
        

        .block-container {
            max-width:100% !important;
            padding:.25rem .35rem .45rem !important;
        }

        .stApp { background:#f8fbff; }

        .pn-left-card {
            padding:.65rem .75rem .8rem;
            border:1px solid #d7e2f1;
            border-radius:18px;
            background:linear-gradient(180deg,#ffffff 0%,#f8fbff 100%);
            box-shadow:0 10px 28px rgba(35,75,140,.08);
        }

        .pn-logo {
            display:flex;
            justify-content:center;
            align-items:center;
            padding:0 0 .25rem;
            margin:0;
        }

        .pn-logo img {
            width:165px;
            max-width:88%;
            display:block;
            margin:0;
        }

        .pn-user-card {
            display:flex;
            align-items:center;
            gap:.7rem;
            padding:.42rem .2rem .6rem;
        }

        .pn-avatar {
            position:relative;
            width:50px;
            height:50px;
            display:grid;
            place-items:center;
            border-radius:50%;
            color:#fff;
            background:linear-gradient(145deg,#6d28d9,#8b5cf6);
            box-shadow:0 8px 18px rgba(109,40,217,.18);
            font-size:1.05rem;
            font-weight:950;
        }

        .pn-dot {
            position:absolute;
            right:0;
            bottom:2px;
            width:13px;
            height:13px;
            border:2px solid #fff;
            border-radius:50%;
            background:#22c55e;
        }

        .pn-user-copy strong {
            display:block;
            color:#111827;
            font-size:.82rem;
        }

        .pn-user-copy small {
            color:#16a34a;
            font-size:.67rem;
            font-weight:850;
        }

        .pn-section-title {
            margin:.7rem 0 .4rem;
            padding:.55rem .65rem;
            border-radius:11px;
            color:#fff;
            font-size:.74rem;
            font-weight:950;
            background:linear-gradient(90deg,#2563eb,#1d4ed8);
        }

        .pn-section-title.devices {
            background:linear-gradient(90deg,#6d28d9,#7c3aed);
        }

        .pn-footer {
            margin-top:.8rem;
            padding-top:.65rem;
            border-top:1px solid #e2e8f0;
            text-align:center;
            color:#64748b;
            font-size:.64rem;
            line-height:1.5;
        }

        .pn-license {
            display:inline-block;
            margin:.35rem 0;
            padding:.26rem .55rem;
            border:1px solid #b7e5c2;
            border-radius:999px;
            color:#177a39;
            background:#f0fff4;
            font-weight:850;
        }

        .pn-topbar {
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:.7rem;
            padding:.25rem .1rem .5rem;
        }

        .pn-topbar h2 {
            margin:0;
            color:#111827;
            font-size:1.35rem;
        }

        .pn-subtitle {
            color:#64748b;
            font-size:.82rem;
            font-weight:650;
        }

        .pn-canvas-card {
            overflow:hidden;
            border:1px solid #d8e2ef;
            border-radius:13px;
            background:#fff;
        }

        .pn-right-card {
            padding:.6rem;
            border:1px solid #d8e3f2;
            border-radius:12px;
            background:#fff;
        }

        .pn-console-card {
            margin-top:.55rem;
            overflow:hidden;
            border-radius:12px;
            background:#08111f;
            box-shadow:0 10px 24px rgba(15,23,42,.15);
        }

        .pn-console-head {
            display:flex;
            align-items:center;
            justify-content:space-between;
            padding:.55rem .7rem;
            border-bottom:1px solid #223049;
            background:#0d1727;
            color:#fff;
            font-size:.7rem;
            font-weight:800;
        }

        .pn-console {
            min-height:180px;
            max-height:260px;
            overflow:auto;
            padding:.9rem;
            color:#36f062;
            white-space:pre-wrap;
            font:.78rem/1.55 Consolas,"Courier New",monospace;
        }

        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button {
            border-radius:10px !important;
            font-weight:800 !important;
        }

        [class*="st-key-project_save"] button {
            border:0 !important;
            color:#fff !important;
            background:#16a34a !important;
        }

        [class*="st-key-project_delete"] button {
            border:0 !important;
            color:#fff !important;
            background:#ef4444 !important;
        }

        [class*="st-key-device_add"] button {
            border:0 !important;
            color:#fff !important;
            background:linear-gradient(90deg,#2563eb,#7c3aed) !important;
        }

        [class*="st-key-logout_btn"] button {
            color:#dc2626 !important;
            border:1px solid #fecaca !important;
            background:#fff !important;
        }

        /* Colorful glass controls — scoped strictly to sidebar actions. */
        [data-testid="stSidebar"] [class*="st-key-project_create"] button,
        [data-testid="stSidebar"] [class*="st-key-project_open"] button,
        [data-testid="stSidebar"] [class*="st-key-project_delete"] button,
        [data-testid="stSidebar"] [class*="st-key-project_save"] button,
        [data-testid="stSidebar"] [class*="st-key-device_add"] button,
        [data-testid="stSidebar"] [class*="st-key-load_demo"] button,
        [data-testid="stSidebar"] [class*="st-key-reset_topology"] button,
        [data-testid="stSidebar"] [class*="st-key-logout_btn"] button {
            position:relative !important;
            overflow:hidden !important;
            min-height:42px !important;
            border-radius:13px !important;
            border:1px solid rgba(255,255,255,.64) !important;
            color:#ffffff !important;
            font-weight:850 !important;
            letter-spacing:.01em !important;
            backdrop-filter:blur(12px) saturate(145%) !important;
            -webkit-backdrop-filter:blur(12px) saturate(145%) !important;
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,.48),
                inset 0 -1px 0 rgba(255,255,255,.10),
                0 7px 16px rgba(30,41,59,.14) !important;
            transition:transform .18s ease, box-shadow .18s ease,
                       filter .18s ease !important;
        }

        [data-testid="stSidebar"] [class*="st-key-project_create"] button {
            background:linear-gradient(135deg,rgba(14,165,233,.90),rgba(37,99,235,.92)) !important;
        }

        [data-testid="stSidebar"] [class*="st-key-project_open"] button {
            background:linear-gradient(135deg,rgba(59,130,246,.88),rgba(6,182,212,.90)) !important;
        }

        [data-testid="stSidebar"] [class*="st-key-project_delete"] button {
            background:linear-gradient(135deg,rgba(244,63,94,.90),rgba(239,68,68,.94)) !important;
        }

        [data-testid="stSidebar"] [class*="st-key-project_save"] button {
            background:linear-gradient(135deg,rgba(16,185,129,.92),rgba(22,163,74,.94)) !important;
        }

        [data-testid="stSidebar"] [class*="st-key-device_add"] button {
            background:linear-gradient(135deg,rgba(37,99,235,.92),rgba(124,58,237,.94),rgba(217,70,239,.88)) !important;
        }

        [data-testid="stSidebar"] [class*="st-key-load_demo"] button {
            background:linear-gradient(135deg,rgba(6,182,212,.88),rgba(14,165,233,.92)) !important;
        }

        [data-testid="stSidebar"] [class*="st-key-reset_topology"] button {
            background:linear-gradient(135deg,rgba(245,158,11,.90),rgba(249,115,22,.92)) !important;
        }

        [data-testid="stSidebar"] [class*="st-key-logout_btn"] button {
            background:linear-gradient(135deg,rgba(236,72,153,.88),rgba(139,92,246,.92)) !important;
        }

        [data-testid="stSidebar"] [class*="st-key-project_create"] button:hover,
        [data-testid="stSidebar"] [class*="st-key-project_open"] button:hover,
        [data-testid="stSidebar"] [class*="st-key-project_delete"] button:hover,
        [data-testid="stSidebar"] [class*="st-key-project_save"] button:hover,
        [data-testid="stSidebar"] [class*="st-key-device_add"] button:hover,
        [data-testid="stSidebar"] [class*="st-key-load_demo"] button:hover,
        [data-testid="stSidebar"] [class*="st-key-reset_topology"] button:hover,
        [data-testid="stSidebar"] [class*="st-key-logout_btn"] button:hover {
            transform:translateY(-2px) scale(1.012) !important;
            filter:brightness(1.08) saturate(1.08) !important;
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,.60),
                0 11px 22px rgba(30,41,59,.22) !important;
        }

        [data-testid="stSidebar"] button:disabled {
            transform:none !important;
            filter:saturate(.55) !important;
            opacity:.48 !important;
            box-shadow:inset 0 1px 0 rgba(255,255,255,.35) !important;
        }

        @media(max-width:1000px) {
            .pn-logo img { width:145px; }
        }
        





/* =========================================================
   PEERNET SIDEBAR + NORMAL PAGE SCROLL
   ========================================================= */

html,
body {
    height: auto !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    overscroll-behavior-y: auto !important;
    scroll-behavior: auto !important;
}

[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
.block-container {
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
}

/* Keep native Streamlit sidebar available and slightly wider. */
[data-testid="stSidebar"] {
    display: block !important;
    width: 340px !important;
    min-width: 340px !important;
    max-width: 340px !important;
    height: 100vh !important;
    overflow: hidden !important;
}

[data-testid="stSidebarContent"] {
    width: 340px !important;
    min-width: 340px !important;
}

/* Sidebar content gets its own smooth vertical scroll. */
[data-testid="stSidebarContent"] {
    height: 100vh !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    overscroll-behavior: contain !important;
    scrollbar-gutter: stable;
    padding-bottom: 1rem;
}

/* Main application scrolls naturally as one page. */
[data-testid="stMain"] {
    overflow-y: auto !important;
    overflow-x: hidden !important;
}

/* Keep topology iframe from creating a second page-level scrollbar. */
.pn-canvas-card {
    overflow: hidden !important;
}

/* Console output scrolls inside the console only when it becomes long. */
.pn-console {
    max-height: 300px !important;
    overflow-y: auto !important;
    overflow-x: auto !important;
    overscroll-behavior: contain !important;
}

/* Sidebar scrollbar */
[data-testid="stSidebarContent"]::-webkit-scrollbar {
    width: 7px;
}
[data-testid="stSidebarContent"]::-webkit-scrollbar-thumb {
    background: rgba(100,116,139,.38);
    border-radius: 999px;
}

/* Console scrollbar */
.pn-console::-webkit-scrollbar {
    width: 7px;
    height: 7px;
}
.pn-console::-webkit-scrollbar-thumb {
    background: rgba(100,116,139,.38);
    border-radius: 999px;
}

/* IST greeting replacing the inactive topology toolbar controls. */
.pn-ist-greeting {
    display:flex;
    align-items:center;
    justify-content:flex-end;
    min-height:42px;
    padding:.35rem .35rem .35rem 0;
    border:0;
    border-radius:0;
    color:#172554;
    background:transparent;
    box-shadow:none;
    backdrop-filter:none;
    -webkit-backdrop-filter:none;
    font-size:1.18rem;
    font-weight:850;
}

.pn-ist-greeting small {
    margin-left:auto;
    color:#64748b;
    font-size:.68rem;
    font-weight:750;
}

/* Compact live topology summary shown only inside Validation. */
.pn-validation-stats {
    display:grid;
    grid-template-columns:repeat(4,minmax(0,1fr));
    gap:.65rem;
    margin:.5rem 0 .9rem;
}

.pn-validation-stat {
    padding:.68rem .8rem;
    border:1px solid rgba(255,255,255,.78);
    border-radius:13px;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.92),0 6px 15px rgba(15,23,42,.08);
    backdrop-filter:blur(10px);
    -webkit-backdrop-filter:blur(10px);
}

.pn-validation-stat span {
    display:block;
    color:#64748b;
    font-size:.7rem;
    font-weight:800;
    text-transform:uppercase;
    letter-spacing:.04em;
}

.pn-validation-stat strong {
    display:block;
    margin-top:.1rem;
    color:#0f172a;
    font-size:1.2rem;
    font-weight:900;
}

.pn-validation-stat.devices { background:linear-gradient(135deg,rgba(219,234,254,.92),rgba(191,219,254,.72)); }
.pn-validation-stat.links { background:linear-gradient(135deg,rgba(237,233,254,.92),rgba(221,214,254,.74)); }
.pn-validation-stat.up { background:linear-gradient(135deg,rgba(220,252,231,.94),rgba(187,247,208,.74)); }
.pn-validation-stat.down { background:linear-gradient(135deg,rgba(254,226,226,.94),rgba(254,202,202,.72)); }

@media(max-width:700px) {
    .pn-validation-stats { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .pn-ist-greeting small { display:none; }
}

/* Laptop/mobile safety */
@media (max-width: 900px) {
    [data-testid="stSidebar"] {
        height: 100vh !important;
    }

    [data-testid="stMain"] {
        overflow-y: auto !important;
    }
}



/* =========================================================
   PEERNET MAIN DASHBOARD SCROLL
   Sidebar is intentionally NOT modified here.
   ========================================================= */

/* Main Streamlit viewport gets its own smooth vertical scroll. */
[data-testid="stMain"] {
    height: 100vh !important;
    max-height: 100vh !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    overscroll-behavior-y: contain !important;
    scroll-behavior: auto !important;
    scrollbar-gutter: stable;
}

/* Main block remains content-sized inside the scrolling viewport. */
[data-testid="stMainBlockContainer"],
[data-testid="stMain"] .block-container {
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
    padding-bottom: 2rem !important;
}

/* Do not let the topology iframe create another page scrollbar. */
.pn-canvas-card {
    overflow: hidden !important;
    margin-bottom: .65rem !important;
}

/* Console/results can scroll internally only when their content is long. */
.pn-console {
    max-height: 320px !important;
    overflow-y: auto !important;
    overflow-x: auto !important;
    overscroll-behavior: contain !important;
}

/* Visible but unobtrusive main-dashboard scrollbar. */
[data-testid="stMain"]::-webkit-scrollbar {
    width: 10px;
}

[data-testid="stMain"]::-webkit-scrollbar-track {
    background: transparent;
}

[data-testid="stMain"]::-webkit-scrollbar-thumb {
    background: rgba(100,116,139,.42);
    border-radius: 999px;
    border: 2px solid transparent;
    background-clip: padding-box;
}

[data-testid="stMain"]::-webkit-scrollbar-thumb:hover {
    background: rgba(71,85,105,.62);
    border: 2px solid transparent;
    background-clip: padding-box;
}

/* Firefox */
[data-testid="stMain"] {
    scrollbar-width: thin;
    scrollbar-color: rgba(100,116,139,.50) transparent;
}


/* =========================================================
   COLORFUL TOPOLOGY TOOLBAR BUTTONS
   ========================================================= */
[class*="st-key-tool_select"] button,
[class*="st-key-tool_connect"] button,
[class*="st-key-tool_move"] button,
[class*="st-key-tool_delete"] button,
[class*="st-key-tool_fullscreen"] button {
    color: #ffffff !important;
    border: 0 !important;
    border-radius: 10px !important;
    font-weight: 800 !important;
    box-shadow: 0 4px 10px rgba(15,23,42,.15) !important;
    transition: transform .15s ease, filter .15s ease, box-shadow .15s ease !important;
}

[class*="st-key-tool_select"] button {
    background: linear-gradient(135deg,#2563eb,#3b82f6) !important;
}

[class*="st-key-tool_connect"] button {
    background: linear-gradient(135deg,#16a34a,#22c55e) !important;
}

[class*="st-key-tool_move"] button {
    background: linear-gradient(135deg,#7c3aed,#9333ea) !important;
}

[class*="st-key-tool_delete"] button {
    background: linear-gradient(135deg,#dc2626,#ef4444) !important;
}

[class*="st-key-tool_fullscreen"] button {
    background: linear-gradient(135deg,#ea580c,#f59e0b) !important;
}

[class*="st-key-tool_select"] button:hover,
[class*="st-key-tool_connect"] button:hover,
[class*="st-key-tool_move"] button:hover,
[class*="st-key-tool_delete"] button:hover,
[class*="st-key-tool_fullscreen"] button:hover {
    filter: brightness(1.05);
    transform: translateY(-1px);
    box-shadow: 0 7px 14px rgba(15,23,42,.20) !important;
}

/* Compact Ping / Traceroute action buttons */
[class*="st-key-run_ping"] button,
[class*="st-key-run_trace"] button {
    width: auto !important;
    min-width: 150px !important;
    max-width: 190px !important;
    padding-left: 1.1rem !important;
    padding-right: 1.1rem !important;
    border-radius: 9px !important;
    font-weight: 800 !important;
}

/* Far-right AI tab: this is the only tab row containing seven buttons. */
div[role="tablist"]:has(button:nth-of-type(7)),
[data-baseweb="tab-list"]:has(button:nth-of-type(7)) {
    display:flex !important;
    width:100% !important;
}

div[role="tablist"]:has(button:nth-of-type(7)) button:nth-of-type(7),
[data-baseweb="tab-list"]:has(button:nth-of-type(7)) button:nth-of-type(7) {
    margin-left:auto !important;
    padding:.45rem .9rem !important;
    border:1px solid rgba(124,58,237,.38) !important;
    border-radius:999px !important;
    background:linear-gradient(135deg,#7c3aed 0%,#2563eb 55%,#06b6d4 100%) !important;
    color:#ffffff !important;
    font-weight:850 !important;
    box-shadow:0 6px 16px rgba(79,70,229,.28) !important;
}

div[role="tablist"]:has(button:nth-of-type(7)) button:nth-of-type(7) p,
[data-baseweb="tab-list"]:has(button:nth-of-type(7)) button:nth-of-type(7) p {
    color:#ffffff !important;
    font-weight:850 !important;
}

div[role="tablist"]:has(button:nth-of-type(7)) button:nth-of-type(7):hover,
[data-baseweb="tab-list"]:has(button:nth-of-type(7)) button:nth-of-type(7):hover {
    filter:brightness(1.08);
    transform:translateY(-1px);
}

/* Compact, colorful AI Assistant actions. */
[class*="st-key-generate_ai_commands"] button {
    width:auto !important;
    min-width:170px !important;
    padding:.42rem .9rem !important;
    border:0 !important;
    border-radius:9px !important;
    background:linear-gradient(135deg,#2563eb,#7c3aed) !important;
    color:#ffffff !important;
    box-shadow:0 4px 12px rgba(79,70,229,.22) !important;
}

[class*="st-key-clear_ai_answer"] button {
    width:auto !important;
    min-width:82px !important;
    padding:.42rem .8rem !important;
    border:1px solid #f59e0b !important;
    border-radius:9px !important;
    background:linear-gradient(135deg,#fff7ed,#fef3c7) !important;
    color:#9a3412 !important;
    font-weight:800 !important;
}

[class*="st-key-run_ping"] button {
    background: linear-gradient(135deg,#2563eb,#3b82f6) !important;
    color:#ffffff !important;
    border:0 !important;
}

[class*="st-key-stop_ping_animation"] button,
[class*="st-key-stop_trace_animation"] button {
    width:auto !important;
    min-width:150px !important;
    max-width:210px !important;
    color:#ffffff !important;
    border:0 !important;
    border-radius:9px !important;
    font-weight:850 !important;
}

[class*="st-key-stop_ping_animation"] button {
    background:linear-gradient(135deg,#dc2626,#ef4444) !important;
}

[class*="st-key-stop_trace_animation"] button {
    background:linear-gradient(135deg,#ea580c,#f97316) !important;
}

[class*="st-key-run_trace"] button {
    background: linear-gradient(135deg,#7c3aed,#9333ea) !important;
    color:#ffffff !important;
    border:0 !important;
}


/* =========================================================
   LOGIN PAGE ONLY
   ========================================================= */

.stApp:has([class*="st-key-peernet_auth_box"]) {
    background:
        radial-gradient(circle at 8% 12%,rgba(37,99,235,.16),transparent 28%),
        radial-gradient(circle at 92% 16%,rgba(124,58,237,.13),transparent 25%),
        radial-gradient(circle at 80% 88%,rgba(6,182,212,.12),transparent 28%),
        linear-gradient(135deg,#f8fbff 0%,#f3f7ff 48%,#fbf9ff 100%) !important;
}

.stApp:has([class*="st-key-peernet_auth_box"])::before {
    content:"";
    position:fixed;
    inset:0;
    pointer-events:none;
    opacity:.32;
    background-image:
        radial-gradient(circle,#60a5fa 1.5px,transparent 1.7px),
        linear-gradient(32deg,transparent 49.5%,rgba(96,165,250,.14) 50%,transparent 50.5%),
        linear-gradient(148deg,transparent 49.5%,rgba(124,58,237,.10) 50%,transparent 50.5%);
    background-size:54px 54px,216px 162px,270px 216px;
    background-position:10px 8px,24px 18px,70px 42px;
}

.stApp:has([class*="st-key-peernet_auth_box"])::after {
    content:"";
    position:fixed;
    inset:0;
    pointer-events:none;
    z-index:0;
    background:
        radial-gradient(ellipse 330px 250px at -30px -35px,
            transparent 55%,rgba(37,99,235,.22) 56%,rgba(124,58,237,.15) 65%,transparent 66%),
        radial-gradient(ellipse 360px 270px at calc(100% + 35px) calc(100% + 35px),
            transparent 54%,rgba(6,182,212,.20) 55%,rgba(245,158,11,.14) 64%,transparent 65%);
}

.stApp:has([class*="st-key-peernet_auth_box"]) [data-testid="stAppViewContainer"] > * {
    position:relative;
    z-index:1;
}

.stApp:has([class*="st-key-peernet_auth_box"]) [data-testid="stMainBlockContainer"] {
    max-width:1500px !important;
    padding-top:2rem !important;
    padding-bottom:1.25rem !important;
}

.stApp:has([class*="st-key-peernet_auth_box"]) [data-testid="stHorizontalBlock"]:has([class*="st-key-peernet_auth_box"]) {
    align-items:stretch !important;
}

.stApp:has([class*="st-key-peernet_auth_box"]) [data-testid="stHorizontalBlock"]:has([class*="st-key-peernet_auth_box"]) > [data-testid="stColumn"] {
    display:flex !important;
    flex-direction:column !important;
}

.stApp:has([class*="st-key-peernet_auth_box"]) [data-testid="stHorizontalBlock"]:has([class*="st-key-peernet_auth_box"]) > [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {
    flex:1 1 auto !important;
}

.pn-auth-eyebrow {
    width:max-content;
    margin:.1rem auto .65rem;
    padding:.38rem .78rem;
    border:1px solid rgba(37,99,235,.16);
    border-radius:999px;
    background:linear-gradient(135deg,rgba(219,234,254,.92),rgba(237,233,254,.92));
    color:#2457c5;
    font-size:.72rem;
    font-weight:850;
    letter-spacing:.08em;
    text-transform:uppercase;
    box-shadow:0 5px 16px rgba(37,99,235,.10);
}

.pn-auth-logo {
    display:flex;
    justify-content:center;
    align-items:center;
    width:100%;
    margin:.15rem auto .45rem;
}

.pn-auth-logo img {
    width:205px;
    max-width:75%;
    display:block;
    margin:0 auto;
}

.pn-auth-title {
    text-align:center;
    margin:.05rem auto .18rem;
    font-size:clamp(2rem,3.4vw,3rem);
    font-weight:950;
    line-height:1.08;
    letter-spacing:-.035em;
}

.pn-auth-title .pn-auth-peer {
    color:#0b2f68;
}

.pn-auth-title .pn-auth-network {
    background:linear-gradient(90deg,#155eef 0%,#1689ff 48%,#06b6d4 100%);
    -webkit-background-clip:text;
    background-clip:text;
    color:transparent;
    -webkit-text-fill-color:transparent;
}

.pn-auth-tagline {
    margin:0 auto .45rem;
    text-align:center;
    color:#64748b;
    font-size:.98rem;
    font-weight:700;
    letter-spacing:.025em;
}

.pn-auth-benefits {
    display:flex;
    justify-content:center;
    flex-wrap:wrap;
    gap:.42rem;
    margin:0 auto 1rem;
}

.pn-auth-benefits span {
    padding:.32rem .62rem;
    border:1px solid #dbeafe;
    border-radius:999px;
    background:rgba(255,255,255,.78);
    color:#475569;
    font-size:.7rem;
    font-weight:750;
    box-shadow:0 3px 10px rgba(15,23,42,.05);
}

.pn-auth-side-caption {
    margin:.4rem 0 0;
    text-align:center;
    color:#64748b;
    font-size:.72rem;
}

/* Boxed auth container generated by st.container(border=True). */
[class*="st-key-peernet_auth_box"] {
    padding:.7rem 1rem 1rem !important;
    border:1px solid rgba(255,255,255,.9) !important;
    border-radius:24px !important;
    background:rgba(255,255,255,.78) !important;
    backdrop-filter:blur(18px) saturate(145%) !important;
    -webkit-backdrop-filter:blur(18px) saturate(145%) !important;
    box-shadow:0 22px 55px rgba(30,64,175,.14),inset 0 1px 0 #fff !important;
}

[class*="st-key-peernet_auth_box"] [data-baseweb="tab-list"] {
    gap:.35rem !important;
    padding:.28rem !important;
    border:1px solid #e3eaf5 !important;
    border-radius:13px !important;
    background:#f5f8fd !important;
}

[class*="st-key-peernet_auth_box"] [data-baseweb="tab"] {
    min-height:38px !important;
    border-radius:9px !important;
    color:#64748b !important;
    font-weight:800 !important;
}

[class*="st-key-peernet_auth_box"] [aria-selected="true"] {
    background:#ffffff !important;
    color:#155eef !important;
    box-shadow:0 4px 12px rgba(37,99,235,.12) !important;
}

/* Keep inputs soft and modern only inside login box. */
[class*="st-key-peernet_auth_box"] input {
    min-height:46px !important;
    border-radius:12px !important;
    background:rgba(245,248,253,.95) !important;
}

[class*="st-key-peernet_auth_box"] [data-testid="stForm"] {
    border:0 !important;
    padding:.25rem 0 !important;
}

[class*="st-key-peernet_auth_box"] button[kind="primaryFormSubmit"],
[class*="st-key-peernet_auth_box"] button[kind="secondaryFormSubmit"],
[class*="st-key-peernet_auth_box"] [data-testid="stButton"] button {
    min-height:45px !important;
    border:0 !important;
    border-radius:12px !important;
    background:linear-gradient(135deg,#155eef 0%,#2563eb 48%,#7c3aed 100%) !important;
    color:#ffffff !important;
    font-weight:850 !important;
    box-shadow:0 9px 20px rgba(79,70,229,.22) !important;
    transition:transform .16s ease,box-shadow .16s ease,filter .16s ease !important;
}

[class*="st-key-peernet_auth_box"] button:hover {
    transform:translateY(-1px) !important;
    filter:brightness(1.04) !important;
    box-shadow:0 12px 25px rgba(79,70,229,.28) !important;
}

.stApp:has([class*="st-key-peernet_auth_box"]) [data-testid="stImage"] {
    width:100% !important;
    height:100% !important;
    min-height:clamp(655px,73vh,775px) !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    padding:.55rem !important;
    border:1px solid rgba(255,255,255,.9) !important;
    border-radius:26px !important;
    background:rgba(255,255,255,.62) !important;
    box-shadow:0 24px 60px rgba(30,64,175,.15) !important;
    overflow:hidden !important;
}

.stApp:has([class*="st-key-peernet_auth_box"]) [data-testid="stImage"] img {
    border-radius:20px !important;
    width:100% !important;
    height:100% !important;
    max-height:760px !important;
    object-fit:contain !important;
    object-position:center !important;
    display:block !important;
}

[class*="st-key-peernet_auth_art"] {
    flex:1 1 auto !important;
    width:100% !important;
    height:100% !important;
    min-height:clamp(655px,73vh,775px) !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
}

/* Login-only spacing on smaller screens. */
@media(max-width:900px) {
    .pn-auth-logo img {
        width:175px;
    }

    .pn-auth-title {
        font-size:2rem;
    }

    .stApp:has([class*="st-key-peernet_auth_box"]) [data-testid="stMainBlockContainer"] {
        padding-top:1rem !important;
    }

    .stApp:has([class*="st-key-peernet_auth_box"]) [data-testid="stImage"] img {
        height:auto !important;
        max-height:none !important;
        object-fit:contain !important;
    }

    .stApp:has([class*="st-key-peernet_auth_box"]) [data-testid="stImage"],
    [class*="st-key-peernet_auth_art"] {
        min-height:0 !important;
        height:auto !important;
    }
}

</style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    defaults = {
        "authenticated": False,
        "devices": {},
        "links": [],
        "positions": {},
        "cli_modes": {},
        "cli_interfaces": {},
        "cli_interface_ranges": {},
        "cli_vlans": {},
        "cli_routing_contexts": {},
        "cli_route_map_contexts": {},
        "cli_dhcp_contexts": {},
        "cli_history": {},
        "cli_command_history": {},
        "deleted_device_undo": [],
        "booted": set(),
        "selected_device": None,
        "topology_selected_device": None,
        "dialog_mode": None,
        "dialog_device": None,
        "last_event": None,
        "current_project_id": None,
        "current_project_name": "Untitled topology",
        "last_terminal_event": None,
        "terminal_prefill": "",
        "ping_output": "",
        "traceroute_output": "",
        "packet_records": [],
        "packet_analysis_output": [],
        "packet_sequence": 0,
        "packet_animation": {},
        "events_log": [],
        "last_capture_path": "",
        "connect_source": None,
        "connect_target": None,
        "connector_type": "Ethernet / Copper",
        "ai_answer": "",
        "ai_commands": [],
        "ai_request": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def next_name(device_type: str) -> str:
    prefix = PREFIX.get(device_type, "DEV")
    number = 1
    while f"{prefix}{number}" in st.session_state.devices:
        number += 1
    return f"{prefix}{number}"


def add_device(device_type: str, position: Optional[dict] = None) -> str:
    name = next_name(device_type)
    st.session_state.devices[name] = Device(
        name=name,
        device_type=device_type,
        interfaces={
            item: Interface(item)
            for item in DEFAULT_INTERFACES.get(device_type, ["eth0"])
        },
    )
    ensure_switch_defaults(st.session_state.devices[name])
    ensure_routing_defaults(st.session_state.devices[name])

    count = len(st.session_state.devices)
    # Use three visible rows, then extend the topology horizontally. This keeps
    # large layouts reachable through the canvas scrollbar without introducing
    # a vertical topology scrollbar. Existing saved positions are unchanged.
    st.session_state.positions[name] = position or {
        "x": 150 + ((count - 1) // 3) * 190,
        "y": 105 + ((count - 1) % 3) * 145,
    }

    st.session_state.cli_modes[name] = "user"
    st.session_state.cli_history[name] = []
    st.session_state.cli_command_history[name] = []
    # Keep the current selection while the user is building a topology.
    # Selecting every newly added device made the console steal the viewport.
    if st.session_state.selected_device not in st.session_state.devices:
        st.session_state.selected_device = name
    return name


CONNECTOR_TYPES = {
    "Ethernet / Copper": "wired",
    "Fiber / Optical": "optical",
    "Serial": "serial",
    "Wireless": "wireless",
}


def connector_preview_html(selected: str) -> str:
    connector_styles = {
        "Ethernet / Copper": {
            "color": "#111827",
            "border": "2px solid #111827",
            "description": "Solid copper Ethernet cable",
        },
        "Fiber / Optical": {
            "color": "#7c3aed",
            "border": "3px solid #7c3aed",
            "description": "Thick purple optical fiber",
        },
        "Serial": {
            "color": "#f59e0b",
            "border": "3px dashed #f59e0b",
            "description": "Dashed amber serial cable",
        },
        "Wireless": {
            "color": "#0ea5e9",
            "border": "3px dotted #0ea5e9",
            "description": "Dotted blue wireless connection",
        },
    }
    style = connector_styles.get(selected, connector_styles["Ethernet / Copper"])
    return f"""
    <div style="
        display:flex;align-items:center;gap:10px;
        margin:0 0 4px;padding:4px 8px;
        border:1px solid #dbe4f0;border-radius:9px;
        background:#f8fafc;
    ">
        <span style="
            display:inline-block;width:70px;height:0;
            border-top:{style['border']};
        "></span>
        <span style="font-size:11px;font-weight:800;color:{style['color']};">
            {html.escape(selected)}
        </span>
        <span style="font-size:10px;color:#64748b;">
            {style['description']}
        </span>
    </div>
    """


def free_interfaces(device_name: str) -> list[str]:
    if device_name not in st.session_state.devices:
        return []

    return [
        name
        for name, interface in st.session_state.devices[
            device_name
        ].interfaces.items()
        if not interface.connected_to
    ]


def interface_connector_hint(interface_name: str) -> str:
    lowered = interface_name.lower()

    if "serial" in lowered or lowered.startswith("s"):
        return "Serial"
    if "fiber" in lowered or "opt" in lowered:
        return "Fiber / Optical"
    if "wlan" in lowered or "wireless" in lowered:
        return "Wireless"
    return "Ethernet / Copper"


def connect_interfaces(
    source: str,
    source_if: str,
    target: str,
    target_if: str,
    connector_type: str,
) -> tuple[bool, str]:
    if source == target:
        return False, "Choose two different devices."

    if (
        source not in st.session_state.devices
        or target not in st.session_state.devices
    ):
        return False, "Source or destination device is missing."

    source_device = st.session_state.devices[source]
    target_device = st.session_state.devices[target]

    if source_if not in source_device.interfaces:
        return False, f"{source}:{source_if} does not exist."

    if target_if not in target_device.interfaces:
        return False, f"{target}:{target_if} does not exist."

    if source_device.interfaces[source_if].connected_to:
        return False, f"{source}:{source_if} is already in use."

    if target_device.interfaces[target_if].connected_to:
        return False, f"{target}:{target_if} is already in use."

    source_device.interfaces[source_if].connected_to = (
        f"{target}:{target_if}"
    )
    target_device.interfaces[target_if].connected_to = (
        f"{source}:{source_if}"
    )

    link_id = (
        f"{source}-{source_if}-{target}-{target_if}-"
        f"{len(st.session_state.links)+1}"
    )

    st.session_state.links.append(
        {
            "id": link_id,
            "source": source,
            "target": target,
            "source_if": source_if,
            "target_if": target_if,
            "connector_type": connector_type,
        }
    )

    add_event(
        f"Connected {source}:{source_if} ↔ "
        f"{target}:{target_if} using {connector_type}."
    )

    return (
        True,
        f"Connected {source}:{source_if} ↔ "
        f"{target}:{target_if} using {connector_type}.",
    )


def link_label(link: dict) -> str:
    return (
        f"{link.get('source', 'unknown')}:"
        f"{link.get('source_if') or 'unassigned'} ↔ "
        f"{link.get('target', 'unknown')}:"
        f"{link.get('target_if') or 'unassigned'}"
    )


def link_operational_status(link: dict) -> tuple[str, str]:
    """Return topology status class and a user-facing reason."""
    if link.get("forced_down"):
        return "down", "Cable failure simulated"

    endpoints = (
        (link.get("source"), link.get("source_if")),
        (link.get("target"), link.get("target_if")),
    )
    for device_name, interface_name in endpoints:
        device = st.session_state.devices.get(device_name)
        interface = (
            device.interfaces.get(interface_name)
            if device and interface_name
            else None
        )
        if interface is None:
            return "down", f"{device_name}:{interface_name or 'unassigned'} is missing"
        status = str(interface.status).lower()
        if status == "administratively down":
            return "admin-down", f"{device_name}:{interface_name} is administratively down"
        if status == "down":
            return "down", f"{device_name}:{interface_name} is down"

    return "up", "Both interfaces are operational"


def topology_interface_details(
    device_name: str,
    interface_name: str,
) -> dict[str, str]:
    device = st.session_state.devices.get(device_name)
    interface = (
        device.interfaces.get(interface_name)
        if device and interface_name
        else None
    )
    if interface is None:
        return {
            "device": device_name or "unknown",
            "interface": interface_name or "unassigned",
            "ip": "unassigned",
            "mode": "unknown",
            "vlan": "unassigned",
            "status": "down",
        }

    if device.device_type in {"Switch", "Multilayer Switch"}:
        mode = getattr(interface, "switchport_mode", "") or "access"
    else:
        mode = "routed"
    if mode == "access":
        vlan = f"access VLAN {getattr(interface, 'access_vlan', 1)}"
    elif mode == "trunk":
        allowed = getattr(interface, "trunk_allowed_vlans", [])
        allowed_text = ",".join(str(item) for item in allowed) or "all"
        vlan = (
            f"native VLAN {getattr(interface, 'native_vlan', 1)}; "
            f"allowed {allowed_text}"
        )
    else:
        vlan = "not applicable"

    return {
        "device": device_name,
        "interface": interface_name,
        "ip": interface.ip_address or "unassigned",
        "mode": mode,
        "vlan": vlan,
        "status": interface.status,
    }


def start_packet_animation(path: list[str], protocol: str = "ICMP") -> None:
    if len(path) < 2:
        st.session_state.packet_animation = {}
        return
    st.session_state.packet_animation = {
        "id": f"{time.time_ns()}",
        "path": list(path),
        "protocol": protocol,
        "expires_at": time.time() + max(3.2, (len(path) - 2) * 0.55 + 3.2),
    }


def links_for_device(device_name: str) -> list[dict]:
    return [
        link
        for link in st.session_state.links
        if device_name in {link.get("source"), link.get("target")}
    ]


def disconnect_link(link_id: str) -> tuple[bool, str]:
    link = next(
        (
            item
            for item in st.session_state.links
            if item.get("id") == link_id
        ),
        None,
    )
    if link is None:
        return False, "The selected connection no longer exists."

    source = link.get("source")
    target = link.get("target")
    source_if = link.get("source_if")
    target_if = link.get("target_if")
    label = link_label(link)

    endpoints = (
        (source, source_if, target, target_if),
        (target, target_if, source, source_if),
    )
    for device_name, interface_name, peer_name, peer_interface in endpoints:
        device = st.session_state.devices.get(device_name)
        if device is None or interface_name not in device.interfaces:
            continue
        interface = device.interfaces[interface_name]
        expected_peer = f"{peer_name}:{peer_interface}"
        if interface.connected_to == expected_peer:
            interface.connected_to = None

    # Remove only this cable. Other parallel connections between the same
    # device pair remain intact.
    st.session_state.links = [
        item
        for item in st.session_state.links
        if item.get("id") != link_id
    ]
    add_event(f"Disconnected {label}.")
    return True, f"Disconnected {label}. Both interfaces are now unassigned."


def connect_devices(source: str, target: str) -> None:
    """Convenience connection used by demo topology only."""
    source_free = free_interfaces(source)
    target_free = free_interfaces(target)

    if not source_free or not target_free:
        return

    connector = interface_connector_hint(source_free[0])

    connect_interfaces(
        source,
        source_free[0],
        target,
        target_free[0],
        connector,
    )


def next_added_port_name(
    device: Device,
    port_family: str,
) -> str:
    if port_family == "GigabitEthernet":
        prefix = "Gi0/"
    elif port_family == "FastEthernet":
        prefix = "Fa0/"
    elif port_family == "Serial":
        prefix = "S0/0/"
    elif port_family == "Fiber":
        prefix = "Fiber"
    elif port_family == "Wireless":
        prefix = "wlan"
    else:
        prefix = "Eth"

    index = 0 if prefix in {"Fiber", "wlan", "Eth"} else 1

    while True:
        candidate = f"{prefix}{index}"
        if candidate not in device.interfaces:
            return candidate
        index += 1


def add_device_port(
    device_name: str,
    port_family: str,
) -> tuple[bool, str]:
    if device_name not in st.session_state.devices:
        return False, "Select a valid device."

    device = st.session_state.devices[device_name]
    port_name = next_added_port_name(device, port_family)
    device.interfaces[port_name] = Interface(port_name)

    return True, f"Added {port_name} to {device_name}."


def prompt(name: str) -> str:
    mode = st.session_state.cli_modes.get(name, "user")

    if mode == "privileged":
        return f"{name}#"
    if mode == "config":
        return f"{name}(config)#"
    if mode == "interface":
        return f"{name}(config-if-{st.session_state.cli_interfaces.get(name,'')})#"
    if mode == "interface_range":
        return f"{name}(config-if-range)#"
    if mode == "vlan":
        return f"{name}(config-vlan)#"
    if mode == "router":
        return f"{name}(config-router)#"
    if mode == "route_map":
        return f"{name}(config-route-map)#"
    if mode == "dhcp":
        return f"{name}(dhcp-config)#"

    return f"{name}>"


def selected_cli_interfaces(name: str) -> list[str]:
    mode = st.session_state.cli_modes.get(name, "user")
    if mode == "interface_range":
        return st.session_state.cli_interface_ranges.get(name, [])
    interface_name = st.session_state.cli_interfaces.get(name)
    return [interface_name] if interface_name else []


def boot(name: str) -> None:
    if name in st.session_state.booted:
        return

    st.session_state.cli_history[name] = [
        "Welcome to PeerNet Network Simulator",
        "Type 'help' to see available commands.",
        "Connected to the simulator.",
        "",
        prompt(name),
    ]
    st.session_state.booted.add(name)


def append_cli(name: str, text: str) -> None:
    st.session_state.cli_history.setdefault(name, []).append(text)
    st.session_state.cli_history[name] = st.session_state.cli_history[name][-150:]


def show_ip_interface_brief(device: Device) -> str:
    rows = ["Interface              IP-Address        Status   Protocol"]

    for interface in device.interfaces.values():
        ip_value = (
            interface.ip_address.split("/")[0]
            if interface.ip_address
            else "unassigned"
        )
        protocol = (
            "up"
            if interface.status == "up" and interface.connected_to
            else "down"
        )

        rows.append(
            f"{interface.name:<22} {ip_value:<17} "
            f"{interface.status:<8} {protocol}"
        )

    return "\n".join(rows)


def show_ip_route(device: Device) -> str:
    rows = [
        "Codes: C - connected, S - static, R - RIP, O - OSPF, D - EIGRP, B - BGP",
        "",
    ]

    for interface in device.interfaces.values():
        if interface.ip_address and interface.status == "up":
            try:
                network = ipaddress.ip_interface(interface.ip_address).network
                rows.append(
                    f"C    {network} is directly connected, {interface.name}"
                )
            except ValueError:
                pass

    for network, next_hop in device.routing_table.items():
        distance = device.route_distances.get(network, 1)
        rows.append(f"S    {network} [{distance}/0] via {next_hop}")

    return "\n".join(rows)


def running_config(device: Device) -> str:
    rows = [f"hostname {device.name}", "!"]

    if is_switch(device):
        ensure_switch_defaults(device)
        for vlan_id, vlan_name in sorted(device.vlans.items()):
            if vlan_id in DEFAULT_VLANS:
                continue
            rows.extend([f"vlan {vlan_id}", f" name {vlan_name}", "!"])

    for interface in device.interfaces.values():
        rows.append(f"interface {interface.name}")
        if interface.description:
            rows.append(f" description {interface.description}")
        if interface.encapsulation_dot1q is not None:
            rows.append(
                f" encapsulation dot1Q {interface.encapsulation_dot1q}"
                + (" native" if interface.encapsulation_native else "")
            )
        if is_switch(device) and not interface.name.lower().startswith("vlan"):
            rows.append(f" switchport mode {interface.switchport_mode}")
            if interface.switchport_mode == "access":
                rows.append(f" switchport access vlan {interface.access_vlan}")
            else:
                rows.append(f" switchport trunk native vlan {interface.native_vlan}")
                allowed = interface.trunk_allowed_vlans
                if allowed:
                    rows.append(
                        " switchport trunk allowed vlan "
                        + ",".join(map(str, allowed))
                    )
        elif interface.ip_address:
            rows.append(f" ip address {interface.ip_address}")
        if interface.ipv6_address:
            rows.append(f" ipv6 address {interface.ipv6_address}")
        if interface.ospfv3_process:
            rows.append(
                f" ipv6 ospf {interface.ospfv3_process} area {interface.ospfv3_area}"
            )
        if interface.name.lower().startswith("tunnel"):
            if interface.tunnel_source:
                rows.append(f" tunnel source {interface.tunnel_source}")
            if interface.tunnel_destination:
                rows.append(f" tunnel destination {interface.tunnel_destination}")
            rows.append(f" tunnel mode {interface.tunnel_mode}")
        if interface.ipsec_profile:
                rows.append(
                    f" tunnel protection ipsec profile {interface.ipsec_profile}"
                )
        if interface.access_group_in:
            rows.append(f" ip access-group {interface.access_group_in} in")
        if interface.access_group_out:
            rows.append(f" ip access-group {interface.access_group_out} out")
        if interface.nat_inside:
            rows.append(" ip nat inside")
        if interface.nat_outside:
            rows.append(" ip nat outside")
        rows.extend(
            [
                f" {'no shutdown' if interface.status == 'up' else 'shutdown'}",
                "!",
            ]
        )

    rows.extend(routing_running_config(device))
    rows.extend(dhcp_running_config(device))
    rows.extend(acl_running_config(device))
    rows.extend(nat_running_config(device))
    rows.extend(dns_running_config(device))

    for network, next_hop in device.routing_table.items():
        distance = device.route_distances.get(network, 1)
        rows.append(
            f"ip route {network} {next_hop}"
            + (f" {distance}" if distance != 1 else "")
        )

    return "\n".join(rows)


def configuration_snapshot(device: Device) -> dict:
    interface_configs = {}
    for name, interface in device.interfaces.items():
        values = asdict(interface)
        values.pop("connected_to", None)
        interface_configs[name] = values
    return {
        "name": device.name,
        "interfaces": interface_configs,
        "routing_table": copy.deepcopy(device.routing_table),
        "default_gateway": device.default_gateway,
        "dns_server": device.dns_server,
        "vlans": copy.deepcopy(device.vlans),
        "route_distances": copy.deepcopy(device.route_distances),
        "routing_config": copy.deepcopy(device.routing_config),
        "text": running_config(device),
    }


def save_startup_config(device: Device) -> None:
    device.startup_config = configuration_snapshot(device)


def restore_startup_config(device: Device) -> tuple[bool, str]:
    snapshot = device.startup_config
    if not snapshot:
        return False, "% No startup configuration is present."

    connections = {
        name: interface.connected_to
        for name, interface in device.interfaces.items()
    }
    saved_interfaces = snapshot.get("interfaces", {})
    restored_interfaces = {}
    for interface_name in set(device.interfaces) | set(saved_interfaces):
        values = copy.deepcopy(saved_interfaces.get(interface_name, {}))
        values["name"] = interface_name
        values["connected_to"] = connections.get(interface_name)
        restored_interfaces[interface_name] = Interface(**values)

    device.interfaces = restored_interfaces
    device.routing_table = copy.deepcopy(snapshot.get("routing_table", {}))
    device.default_gateway = snapshot.get("default_gateway", "")
    device.dns_server = snapshot.get("dns_server", "")
    device.vlans = {
        int(vlan): vlan_name
        for vlan, vlan_name in copy.deepcopy(snapshot.get("vlans", {})).items()
    }
    device.route_distances = {
        prefix: int(distance)
        for prefix, distance in copy.deepcopy(
            snapshot.get("route_distances", {})
        ).items()
    }
    device.routing_config = copy.deepcopy(snapshot.get("routing_config", {}))
    ensure_switch_defaults(device)
    ensure_routing_defaults(device)
    return True, "Startup configuration restored."



def show_version(device: Device) -> str:
    return (
        "PeerNet Virtual OS Software\n"
        f"Device: {device.name}\n"
        f"Platform: {device.device_type}\n"
        f"Interfaces: {len(device.interfaces)}\n"
        "System image file is \"peernet-universal.bin\"\n"
        "Configuration register is 0x2102"
    )


def show_interfaces(device: Device) -> str:
    lines = []
    for interface in device.interfaces.values():
        protocol = (
            "up"
            if interface.status == "up" and interface.connected_to
            else "down"
        )
        lines.extend(
            [
                f"{interface.name} is {interface.status}, line protocol is {protocol}",
                f"  Internet address is {interface.ip_address or 'unassigned'}",
                f"  Connected to: {interface.connected_to or 'none'}",
                "  MTU 1500 bytes, BW 1000000 Kbit/sec",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def show_interfaces_status(device: Device) -> str:
    if is_switch(device):
        return show_switch_interfaces_status(device)
    lines = ["Port          Name        Status       Vlan       Duplex  Speed  Type"]
    for interface in device.interfaces.values():
        connected = "connected" if interface.connected_to else "notconnect"
        vlan = "1" if device.device_type in {"Switch", "Multilayer Switch"} else "--"
        lines.append(
            f"{interface.name:<13} --          {connected:<12} "
            f"{vlan:<10} auto    auto   virtual"
        )
    return "\n".join(lines)


def show_vlan_brief(device: Device) -> str:
    if device.device_type not in {"Switch", "Multilayer Switch"}:
        return "% VLAN database is not available on this device type."

    return show_switch_vlan_brief(device)


def show_mac_address_table(device: Device) -> str:
    if device.device_type not in {"Switch", "Multilayer Switch"}:
        return "% MAC address-table is not available on this device type."

    lines = [
        "          Mac Address Table",
        "-------------------------------------------",
        "Vlan    Mac Address       Type        Ports",
        "----    -----------       --------    -----",
    ]

    index = 1
    for interface in device.interfaces.values():
        if interface.connected_to:
            mac = f"00aa.00bb.{index:04x}"
            vlan_id = (
                interface.native_vlan
                if interface.switchport_mode == "trunk"
                else interface.access_vlan
            )
            lines.append(
                f"{vlan_id:<7} {mac}    DYNAMIC     {interface.name}"
            )
            index += 1

    if index == 1:
        lines.append("No dynamic MAC addresses learned.")

    return "\n".join(lines)


def show_spanning_tree(device: Device) -> str:
    if device.device_type not in {"Switch", "Multilayer Switch"}:
        return "% Spanning-tree is not available on this device type."

    return (
        "VLAN0001\n"
        "  Spanning tree enabled protocol ieee\n"
        f"  Root ID    Priority    32769\n"
        f"             Address     0011.2233.4455\n"
        f"  Bridge ID  Priority    32769\n"
        f"             Address     00aa.bbcc.ddee\n"
        "  Interface        Role Sts Cost      Prio.Nbr Type\n"
        "  ---------------- ---- --- --------- -------- ----------------"
    )


def show_arp(device: Device) -> str:
    lines = [
        "Protocol  Address          Age (min)  Hardware Addr   Type   Interface"
    ]
    found = False

    for interface in device.interfaces.values():
        if interface.connected_to and interface.ip_address:
            found = True
            ip_value = interface.ip_address.split("/")[0]
            lines.append(
                f"Internet  {ip_value:<16} -          00aa.bbcc.ddee  ARPA   {interface.name}"
            )

    if not found:
        lines.append("No ARP entries.")

    return "\n".join(lines)


def show_cdp_neighbors(device: Device) -> str:
    lines = [
        "Device ID        Local Intrfce     Holdtme    Capability  Platform  Port ID"
    ]
    found = False

    for interface in device.interfaces.values():
        if interface.connected_to:
            found = True
            peer, peer_if = interface.connected_to.split(":", 1)
            lines.append(
                f"{peer:<16} {interface.name:<16} 131         R S I       PeerNet   {peer_if}"
            )

    if not found:
        lines.append("No CDP neighbors found.")

    return "\n".join(lines)


def show_help(device: Device) -> str:
    common = [
        "arp                 ARP table",
        "cdp neighbors       CDP neighbor information",
        "copy run start      Save running configuration",
        "erase startup-config  Remove saved configuration",
        "interfaces          Interface information",
        "ip                  IP information",
        "ping <ip>           Test IP connectivity",
        "traceroute <ip>     Trace the routed path",
        "write memory        Save running configuration",
        "reload              Restore saved configuration",
        "running-config      Current operating configuration",
        "startup-config      Saved configuration",
        "version             System hardware and software status",
    ]

    if device.device_type in {"Switch", "Multilayer Switch"}:
        common.extend(
            [
                "interfaces status   Interface switchport status",
                "interfaces trunk    Operational trunk ports",
                "interfaces <port> switchport  Detailed port VLAN mode",
                "mac address-table   MAC forwarding table",
                "spanning-tree       Spanning-tree information",
                "vlan brief          VLAN status",
            ]
        )

    return "\n".join(f"  {item}" for item in common)


def show_ip_help() -> str:
    return (
        "  interface           IP interface information\n"
        "  route               IP routing table"
    )


def command_catalog(device: Device, mode: str) -> list[str]:
    commands = [
        "enable",
        "exit",
        "help",
        "ping ",
        "ping -c 5 ",
        "traceroute ",
        "traceroute -m 30 ",
        "tracert ",
        "copy running-config startup-config",
        "write memory",
        "erase startup-config",
        "reload",
        "show ?",
        "show arp",
        "show access-lists",
        "show cdp neighbors",
        "show interfaces",
        "show ip ?",
        "show ip interface brief",
        "show ip route",
        "show ip route static",
        "show ip dhcp binding",
        "show ip dhcp pool",
        "show ip nat translations",
        "show ip nat statistics",
        "show hosts",
        "clear ip nat translation *",
        "show ip protocols",
        "show ip ospf neighbor",
        "show ipv6 ospf neighbor",
        "show ip eigrp neighbors",
        "show ip bgp summary",
        "show route-map",
        "show running-config",
        "show startup-config",
        "show version",
    ]

    if device.device_type in {"Switch", "Multilayer Switch"}:
        commands.extend(
            [
                "show interfaces status",
                "show interfaces trunk",
                "show mac address-table",
                "show spanning-tree",
                "show vlan brief",
            ]
        )

    if mode == "privileged":
        commands.extend(
            [
                "configure terminal",
                "conf t",
            ]
        )

    if mode == "config":
        commands.extend(
            [
                "hostname ",
                "access-list ",
                "no access-list ",
                "ip nat inside source static ",
                "ip nat inside source list ",
                "ip host ",
                "no ip host ",
                "interface ",
                "interface range ",
                "ip route ",
                "ip dhcp excluded-address ",
                "ip dhcp pool ",
                "no ip dhcp pool ",
                "ip routing",
                "ipv6 unicast-routing",
                "ip prefix-list ",
                "route-map ",
                "router rip",
                "router ospf ",
                "router ospf v3 ",
                "router eigrp ",
                "router bgp ",
                "no vlan ",
                "vlan ",
                "end",
            ]
        )

    if mode == "interface":
        commands.extend(
            [
                "ip address ",
                "ip access-group ",
                "no ip access-group ",
                "ip nat inside",
                "ip nat outside",
                "no ip nat inside",
                "no ip nat outside",
                "ipv6 address ",
                "encapsulation dot1Q ",
                "ipv6 ospf ",
                "tunnel source ",
                "tunnel destination ",
                "tunnel mode gre ip",
                "tunnel mode ipsec ipv4",
                "description ",
                "switchport mode access",
                "switchport mode trunk",
                "switchport access vlan ",
                "switchport trunk native vlan ",
                "switchport trunk allowed vlan ",
                "shutdown",
                "no shutdown",
                "exit",
                "end",
            ]
        )

    if mode == "interface_range":
        commands.extend(
            [
                "description ",
                "switchport mode access",
                "switchport mode trunk",
                "switchport access vlan ",
                "switchport trunk native vlan ",
                "switchport trunk allowed vlan ",
                "shutdown",
                "no shutdown",
                "exit",
                "end",
            ]
        )

    if mode == "dhcp":
        commands.extend(
            ["network ", "default-router ", "dns-server ", "lease ", "exit", "end"]
        )

    if mode == "vlan":
        commands.extend(["name ", "no name", "exit", "end"])

    return sorted(set(commands))


def tab_matches(name: str, partial: str) -> list[str]:
    device = st.session_state.devices[name]
    mode = st.session_state.cli_modes.get(name, "user")

    raw = partial.rstrip()
    normalized = raw.lower()

    # Interface-name completion is case-sensitive after the command keyword.
    # Examples:
    #   interface G<Tab>   -> Gi0/0, Gi0/1
    #   interface Gi0/<Tab> -> Gi0/0, Gi0/1
    if normalized.startswith("interface "):
        typed_interface = raw.split(maxsplit=1)[1] if " " in raw else ""
        completion_aliases = {
            "g": "Gi",
            "gi": "Gi",
            "gigabit": "Gi",
            "f": "Fa",
            "fa": "Fa",
            "fast": "Fa",
            "s": "S",
            "se": "S",
            "serial": "S",
            "t": "Tunnel",
            "tu": "Tunnel",
            "tunnel": "Tunnel",
            "v": "Vlan",
            "vl": "Vlan",
            "vlan": "Vlan",
        }
        normalized_interface = normalize_interface_name(typed_interface)
        normalized_interface = completion_aliases.get(
            typed_interface.lower(),
            normalized_interface,
        )

        return [
            f"interface {interface_name}"
            for interface_name in device.interfaces
            if interface_name.lower().startswith(normalized_interface.lower())
        ]

    # General Cisco command keywords remain case-insensitive.
    return [
        command
        for command in command_catalog(device, mode)
        if command.lower().startswith(normalized)
    ]


def rename_device(old_name: str, new_name: str) -> str:
    new_name = new_name.strip()

    if not new_name:
        return old_name

    if new_name == old_name:
        return old_name

    if new_name in st.session_state.devices:
        append_cli(old_name, f"% Hostname {new_name} already exists.")
        return old_name

    device = st.session_state.devices.pop(old_name)
    device.name = new_name
    st.session_state.devices[new_name] = device

    if old_name in st.session_state.positions:
        st.session_state.positions[new_name] = st.session_state.positions.pop(old_name)

    if old_name in st.session_state.cli_modes:
        st.session_state.cli_modes[new_name] = st.session_state.cli_modes.pop(old_name)

    if old_name in st.session_state.cli_interfaces:
        st.session_state.cli_interfaces[new_name] = st.session_state.cli_interfaces.pop(old_name)
    if old_name in st.session_state.cli_interface_ranges:
        st.session_state.cli_interface_ranges[new_name] = st.session_state.cli_interface_ranges.pop(old_name)
    if old_name in st.session_state.cli_vlans:
        st.session_state.cli_vlans[new_name] = st.session_state.cli_vlans.pop(old_name)
    if old_name in st.session_state.cli_routing_contexts:
        st.session_state.cli_routing_contexts[new_name] = st.session_state.cli_routing_contexts.pop(old_name)
    if old_name in st.session_state.cli_route_map_contexts:
        st.session_state.cli_route_map_contexts[new_name] = st.session_state.cli_route_map_contexts.pop(old_name)

    if old_name in st.session_state.cli_history:
        st.session_state.cli_history[new_name] = st.session_state.cli_history.pop(old_name)
    if old_name in st.session_state.cli_command_history:
        st.session_state.cli_command_history[new_name] = st.session_state.cli_command_history.pop(old_name)

    if old_name in st.session_state.booted:
        st.session_state.booted.remove(old_name)
        st.session_state.booted.add(new_name)

    for link in st.session_state.links:
        if link["source"] == old_name:
            link["source"] = new_name
        if link["target"] == old_name:
            link["target"] = new_name
        link["id"] = f"{link['source']}-{link['target']}"

    for peer_device in st.session_state.devices.values():
        for interface in peer_device.interfaces.values():
            if interface.connected_to and interface.connected_to.startswith(old_name + ":"):
                interface.connected_to = new_name + interface.connected_to[len(old_name):]

    st.session_state.selected_device = new_name
    if st.session_state.dialog_device == old_name:
        st.session_state.dialog_device = new_name

    return new_name


def normalize_interface_name(requested: str) -> str:
    """Expand common Cisco interface abbreviations without changing numbers."""
    requested = requested.strip()
    lowered = requested.lower()
    aliases = (
        ("gigabitethernet", "Gi"),
        ("gigabit", "Gi"),
        ("gi", "Gi"),
        ("g", "Gi"),
        ("fastethernet", "Fa"),
        ("fast", "Fa"),
        ("fa", "Fa"),
        ("f", "Fa"),
        ("serial", "S"),
        ("se", "S"),
        ("s", "S"),
        ("tunnel", "Tunnel"),
        ("tu", "Tunnel"),
        ("vlan", "Vlan"),
    )
    for prefix, canonical in aliases:
        if lowered.startswith(prefix):
            suffix = requested[len(prefix):]
            if suffix and (suffix[0].isdigit() or suffix[0] in {"/", "."}):
                return canonical + suffix
    return requested


def resolve_interface_name(device: Device, requested: str) -> Optional[str]:
    normalized = normalize_interface_name(requested)
    return next(
        (
            existing
            for existing in device.interfaces
            if existing.lower() == normalized.lower()
        ),
        None,
    )

PC_DEVICE_TYPES = {
    "PC",
    "Laptop",
    "Server",
    "Authentication Server",
    "Camera / PC Video",
}


def primary_pc_interface(device: Device) -> Optional[Interface]:
    preferred = ("eth0", "Ethernet0", "Gi0/0", "wlan0")

    # A laptop can expose both eth0 and wlan0.  Prefer the adapter that is
    # physically connected so DHCP and host traffic are bound to the cable
    # (or wireless link) the user actually placed in the topology.
    for name in preferred:
        interface = device.interfaces.get(name)
        if interface and interface.connected_to and interface.status not in {
            "down", "administratively down", "disabled"
        }:
            return interface

    for interface in device.interfaces.values():
        if interface.connected_to and interface.status not in {
            "down", "administratively down", "disabled"
        }:
            return interface

    for name in preferred:
        if name in device.interfaces:
            return device.interfaces[name]

    return next(iter(device.interfaces.values()), None)


def mask_from_cidr(cidr: str) -> str:
    try:
        return str(ipaddress.ip_interface(cidr).network.netmask)
    except ValueError:
        return "unassigned"


def pc_ipconfig(device: Device, show_all: bool = False) -> str:
    interface = primary_pc_interface(device)

    if interface is None:
        return "No network adapter found."

    ip_value = (
        interface.ip_address.split("/")[0]
        if interface.ip_address
        else "unassigned"
    )
    mask = (
        mask_from_cidr(interface.ip_address)
        if interface.ip_address
        else "unassigned"
    )
    gateway = device.default_gateway or "unassigned"

    lines = [
        "PeerNet IP Configuration",
        "",
        f"Adapter {interface.name}",
        f"   IP Address       : {ip_value}",
        f"   Subnet Mask      : {mask}",
        f"   Default Gateway  : {gateway}",
    ]

    if show_all:
        lines.extend(
            [
                f"   DNS Server       : {device.dns_server or 'unassigned'}",
                f"   Status           : {interface.status}",
                f"   Connected To     : {interface.connected_to or 'not connected'}",
            ]
        )

    return "\n".join(lines)


def pc_apply_static_ip(
    device: Device,
    ip_value: str,
    subnet_mask: str,
    gateway: str = "",
) -> tuple[bool, str]:
    interface = primary_pc_interface(device)

    if interface is None:
        return False, "No network adapter found."

    try:
        prefix = ipaddress.IPv4Network(
            f"0.0.0.0/{subnet_mask}"
        ).prefixlen

        ip_iface = ipaddress.ip_interface(
            f"{ip_value}/{prefix}"
        )

        if gateway:
            ipaddress.ip_address(gateway)

    except ValueError:
        return (
            False,
            "Invalid IP configuration. "
            "Use: ip <address> <mask> [gateway]",
        )

    ok, message = validate_interface_address(
        st.session_state.devices,
        device.name,
        interface.name,
        str(ip_iface),
    )
    if not ok:
        return False, message
    if gateway:
        existing_ip = interface.ip_address
        interface.ip_address = str(ip_iface)
        gateway_ok, gateway_message = validate_gateway(device, gateway)
        interface.ip_address = existing_ip
        if not gateway_ok:
            return False, gateway_message

    interface.ip_address = str(ip_iface)
    interface.status = "up"
    device.default_gateway = gateway

    return True, "IP configuration applied successfully."


def pc_ping_result(
    source_name: str,
    destination_ip: str,
    source_ip: str = "",
) -> str:
    try:
        destination_ip = str(ipaddress.ip_address(destination_ip))
    except ValueError:
        return f"Ping request could not find host {destination_ip}."

    source_device = st.session_state.devices[source_name]
    source_if = primary_pc_interface(source_device)
    if source_ip:
        for interface in source_device.interfaces.values():
            if not interface.ip_address:
                continue
            try:
                configured_ip = str(
                    ipaddress.ip_interface(interface.ip_address).ip
                )
            except ValueError:
                continue
            if configured_ip == source_ip:
                source_if = interface
                break

    if not source_if or not source_if.ip_address:
        return "PING failed: source PC has no IP address."

    configured_source_ip = str(ipaddress.ip_interface(source_if.ip_address).ip)
    route_result = evaluate_bidirectional_route(
        source_name,
        configured_source_ip,
        destination_ip,
        st.session_state.devices,
        st.session_state.links,
    )
    if route_result.reachable:
        start_packet_animation(route_result.path, "ICMP")
        return (
            f"Pinging {destination_ip} with 32 bytes of data:\n"
            f"Reply from {destination_ip}: bytes=32 time<1ms TTL=128\n"
            f"Reply from {destination_ip}: bytes=32 time<1ms TTL=128\n\n"
            "Packets: Sent = 2, Received = 2, Lost = 0 (0% loss)"
        )

    st.session_state.packet_animation = {}
    details = "\n".join(route_result.decisions)
    return (
        f"Pinging {destination_ip} with 32 bytes of data:\n"
        "Destination host unreachable.\n"
        "Destination host unreachable.\n\n"
        "Packets: Sent = 2, Received = 0, Lost = 2 (100% loss)\n"
        f"Reason: {route_result.reason}"
        + (f"\n{details}" if details else "")
    )


def pc_help() -> str:
    return (
        "ip <address> <mask> [gateway]    Configure static IPv4\n"
        "ipconfig                         Show IP configuration\n"
        "ipconfig /all                    Show detailed IP configuration\n"
        "ipconfig /renew                  Obtain or renew a DHCP lease\n"
        "ipconfig /release                Release the DHCP lease\n"
        "gateway <ip>                     Set default gateway\n"
        "dns <ip>                         Set DNS server\n"
        "dns add <name> <ip>              Add record on a Server\n"
        "dns remove <name>                Remove record on a Server\n"
        "dns show                         Show records on a Server\n"
        "nslookup <name>                  Resolve a DNS hostname\n"
        "ping <ip|name>                   Test logical connectivity\n"
        "tracert <ip|name>                Trace logical path\n"
        "arp -a                           Show ARP entries\n"
        "route print                      Show PC routing table\n"
        "hostname                         Show PC hostname\n"
        "help                             Show available PC commands\n"
        "clear                            Clear console"
    )


def execute_pc_cli(name: str, command: str) -> bool:
    device = st.session_state.devices[name]
    stripped = command.strip()
    lowered = stripped.lower()

    if lowered.startswith("dns add ") or lowered.startswith("dns remove ") or lowered == "dns show":
        if device.device_type not in {"Server", "Authentication Server"}:
            append_cli(name, "DNS records can be hosted only on a server device.")
            return True
        handled, output = configure_server_record(device, stripped)
        if handled:
            append_cli(name, output)
            return True

    if lowered.startswith("nslookup "):
        query = stripped.split(maxsplit=1)[1].strip()
        ok, address, detail = resolve_name(
            st.session_state.devices, st.session_state.links, name, query
        )
        if ok:
            append_cli(name, f"Server: {device.dns_server or 'local'}\nName: {query}\nAddress: {address}")
        else:
            append_cli(name, f"*** DNS lookup failed: {detail}")
        return True

    if lowered == "ipconfig /renew":
        interface = primary_pc_interface(device)
        if interface is None:
            append_cli(name, "DHCP failed: this device has no usable interface.")
            return True

        # Migrate a DHCP lease that an older version may have placed on a
        # disconnected adapter (for example LAP1:eth0 while wlan0 is linked).
        # Static addresses are preserved because only recorded DHCP leases are
        # removed here.
        for other_name, other_interface in device.interfaces.items():
            if other_name == interface.name:
                continue
            if release_lease(st.session_state.devices, name, other_name):
                other_interface.ip_address = ""

        ok, message, lease = allocate_lease(
            st.session_state.devices, st.session_state.links, name, interface.name
        )
        if not ok:
            append_cli(name, message)
            return True
        interface.ip_address = f"{lease['address']}/{lease['prefixlen']}"
        interface.status = "up"
        device.default_gateway = lease["gateway"]
        device.dns_server = lease["dns"]
        append_cli(
            name,
            "Windows IP Configuration\n\n"
            f"DHCP lease obtained from {lease['server']} ({lease['pool']}).\n"
            f"IPv4 Address. . . . . . . . . . : {lease['address']}\n"
            f"Default Gateway . . . . . . . . : {lease['gateway'] or 'None'}",
        )
        add_event(f"{name}: obtained DHCP address {lease['address']} from {lease['server']}.")
        return True

    if lowered == "ipconfig /release":
        interface = primary_pc_interface(device)
        if interface is None:
            append_cli(name, "No interface is available to release.")
            return True
        previous = interface.ip_address.split("/")[0] if interface.ip_address else "unassigned"
        release_lease(st.session_state.devices, name, interface.name)
        interface.ip_address = ""
        device.default_gateway = ""
        device.dns_server = ""
        append_cli(name, f"DHCP address {previous} released.")
        add_event(f"{name}: released DHCP address {previous}.")
        return True

    if lowered == "ipconfig":
        append_cli(name, pc_ipconfig(device, False))
        return True

    if lowered == "ipconfig /all":
        append_cli(name, pc_ipconfig(device, True))
        return True

    if lowered.startswith("ip "):
        values = stripped.split()[1:]

        if len(values) not in {2, 3}:
            append_cli(
                name,
                "% Usage: ip <address> <mask> [gateway]",
            )
            return True

        gateway = values[2] if len(values) == 3 else ""

        ok, message = pc_apply_static_ip(
            device,
            values[0],
            values[1],
            gateway,
        )
        append_cli(name, message)
        return True

    if lowered.startswith("gateway "):
        value = stripped.split(maxsplit=1)[1].strip()

        try:
            ipaddress.ip_address(value)
            ok, message = validate_gateway(device, value)
            if ok:
                device.default_gateway = value
                append_cli(name, f"Default gateway set to {value}.")
            else:
                append_cli(name, message)
        except ValueError:
            append_cli(name, "% Invalid gateway address.")

        return True

    if lowered.startswith("dns "):
        value = stripped.split(maxsplit=1)[1].strip()

        try:
            ipaddress.ip_address(value)
            device.dns_server = value
            append_cli(name, f"DNS server set to {value}.")
        except ValueError:
            append_cli(name, "% Invalid DNS address.")

        return True

    if lowered.startswith("ping "):
        query = stripped.split(maxsplit=1)[1].strip()
        ok, destination, detail = resolve_name(
            st.session_state.devices, st.session_state.links, name, query
        )
        if not ok:
            append_cli(name, f"Ping request could not find host {query}: {detail}")
            return True
        append_cli(
            name,
            pc_ping_result(name, destination),
        )
        return True

    if lowered.startswith("tracert "):
        query = stripped.split(maxsplit=1)[1].strip()
        ok, destination, detail = resolve_name(
            st.session_state.devices, st.session_state.links, name, query
        )
        if not ok:
            append_cli(name, f"Unable to resolve {query}: {detail}")
            return True
        source_interface = primary_pc_interface(device)
        if not source_interface or not source_interface.ip_address:
            append_cli(name, "Trace failed: source PC has no IP address.")
            return True
        source_ip = str(ipaddress.ip_interface(source_interface.ip_address).ip)
        route_result = evaluate_bidirectional_route(
            name,
            source_ip,
            destination,
            st.session_state.devices,
            st.session_state.links,
        )
        lines = [f"Tracing route to {destination}"]
        for hop_number, hop in enumerate(route_result.path[1:], start=1):
            lines.append(f"  {hop_number:<2}   <1 ms    {hop}")
        if route_result.reachable:
            start_packet_animation(route_result.path, "ICMP Traceroute")
            lines.append("Trace complete.")
        else:
            st.session_state.packet_animation = {}
            lines.extend(["  *     Request timed out.", f"Trace failed: {route_result.reason}"])
        append_cli(name, "\n".join(lines))
        return True

    if lowered == "arp -a":
        append_cli(
            name,
            "Interface: "
            + (
                primary_pc_interface(device).ip_address.split("/")[0]
                if primary_pc_interface(device)
                and primary_pc_interface(device).ip_address
                else "unassigned"
            )
            + "\n  Internet Address      Physical Address      Type\n"
            "  No dynamic ARP entries.",
        )
        return True

    if lowered == "route print":
        append_cli(
            name,
            "IPv4 Route Table\n"
            "Destination        Gateway\n"
            f"0.0.0.0/0          {device.default_gateway or 'On-link'}",
        )
        return True

    if lowered == "hostname":
        append_cli(name, device.name)
        return True

    if lowered in {"help", "?"}:
        append_cli(name, pc_help())
        return True

    if lowered == "clear":
        st.session_state.cli_history[name] = []
        return True

    return False


def parse_console_ping(command: str) -> tuple[str, int, str]:
    """Parse Cisco ping and the commonly used Linux-style -c option."""
    values = command.split()
    if not values or values[0].lower() != "ping":
        return "", 0, "% Invalid ping command."

    destination = ""
    count = 5
    index = 1

    while index < len(values):
        token = values[index]
        lowered_token = token.lower()

        if lowered_token in {"-c", "repeat"}:
            if index + 1 >= len(values):
                return "", 0, "% Ping count is required."
            try:
                count = int(values[index + 1])
            except ValueError:
                return "", 0, "% Ping count must be a number."
            index += 2
            continue

        if destination:
            return "", 0, "% Use: ping [-c <1-100>] <destination-ip>"
        destination = token
        index += 1

    if not destination:
        return "", 0, "% Use: ping [-c <1-100>] <destination-ip>"
    if count < 1 or count > 100:
        return "", 0, "% Ping count must be between 1 and 100."

    try:
        destination = str(ipaddress.ip_address(destination))
    except ValueError:
        return "", 0, f"% Invalid destination IP: {destination}"

    return destination, count, ""


def console_ping_result(
    source_name: str,
    destination_ip: str,
    count: int,
) -> str:
    source_ip = _first_device_ip(source_name)
    if source_ip == "0.0.0.0":
        return (
            f"% Unable to source ping: {source_name} has no configured IP address."
        )
    route_result = evaluate_bidirectional_route(
        source_name,
        source_ip,
        destination_ip,
        st.session_state.devices,
        st.session_state.links,
    )
    reachable = route_result.reachable
    if reachable:
        start_packet_animation(route_result.path, "ICMP")
    else:
        st.session_state.packet_animation = {}
    symbols = "!" * count if reachable else "." * count
    received = count if reachable else 0
    success_rate = int((received / count) * 100)

    record_packet_analysis(
        source_name,
        destination_ip,
        "Console Ping",
        source_ip,
    )
    add_event(
        f"Console ping: {source_name} ({source_ip}) → "
        f"{destination_ip}, {count} probes"
    )

    output = [
        f"Type escape sequence to abort.",
        f"Sending {count}, 100-byte ICMP Echos to {destination_ip}, "
        "timeout is 2 seconds:",
        symbols,
        f"Success rate is {success_rate} percent ({received}/{count})",
    ]
    if reachable:
        output[-1] += ", round-trip min/avg/max = 1/1/2 ms"
    else:
        output.extend(["", f"% {route_result.reason}"])
    return "\n".join(output)


def parse_console_traceroute(command: str) -> tuple[str, int, str]:
    """Parse Cisco traceroute plus familiar -m maximum-hop syntax."""
    values = command.split()
    if not values or values[0].lower() not in {"traceroute", "tracert"}:
        return "", 0, "% Invalid traceroute command."

    destination = ""
    max_hops = 30
    index = 1
    while index < len(values):
        token = values[index]
        if token.lower() in {"-m", "ttl"}:
            if index + 1 >= len(values):
                return "", 0, "% Maximum hop count is required."
            try:
                max_hops = int(values[index + 1])
            except ValueError:
                return "", 0, "% Maximum hop count must be a number."
            index += 2
            continue
        if destination:
            return "", 0, "% Use: traceroute [-m <1-64>] <destination-ip>"
        destination = token
        index += 1

    if not destination:
        return "", 0, "% Use: traceroute [-m <1-64>] <destination-ip>"
    if not 1 <= max_hops <= 64:
        return "", 0, "% Maximum hop count must be between 1 and 64."
    try:
        destination = str(ipaddress.ip_address(destination))
    except ValueError:
        return "", 0, f"% Invalid destination IP: {destination}"
    return destination, max_hops, ""


def console_traceroute_result(
    source_name: str,
    destination_ip: str,
    max_hops: int,
) -> str:
    source_ip = _first_device_ip(source_name)
    if source_ip == "0.0.0.0":
        return (
            f"% Unable to source traceroute: {source_name} has no configured IP address."
        )

    route_result = evaluate_bidirectional_route(
        source_name,
        source_ip,
        destination_ip,
        st.session_state.devices,
        st.session_state.links,
    )
    visible_path = route_result.path[1:max_hops + 1]
    lines = [
        f"Type escape sequence to abort.",
        f"Tracing the route to {destination_ip}",
        "",
    ]
    for hop_number, hop_name in enumerate(visible_path, start=1):
        hop_ip = _first_device_ip(hop_name)
        lines.append(
            f"{hop_number:<3} {hop_ip:<15} 1 msec  1 msec  2 msec  ({hop_name})"
        )

    if route_result.reachable and len(route_result.path) - 1 <= max_hops:
        start_packet_animation(route_result.path, "ICMP Traceroute")
        lines.extend(["", "Trace complete."])
    elif route_result.reachable:
        st.session_state.packet_animation = {}
        lines.extend(["", f"Maximum hop count {max_hops} reached."])
    else:
        st.session_state.packet_animation = {}
        lines.extend(["", f"% Trace failed: {route_result.reason}"])
        lines.extend(f"  {decision}" for decision in route_result.decisions)

    record_packet_analysis(
        source_name,
        destination_ip,
        "Console Traceroute",
        source_ip,
    )
    add_event(
        f"Console traceroute: {source_name} ({source_ip}) → "
        f"{destination_ip}, maximum {max_hops} hops"
    )
    return "\n".join(lines)

def execute_cli(name: str, command: str) -> None:
    # A terminal paste can contain a complete configuration block. Execute
    # each non-empty line in order so CLI mode changes apply to the next line.
    pasted_commands = [
        line.strip()
        for line in command.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ]
    if len(pasted_commands) > 1:
        for pasted_command in pasted_commands:
            execute_cli(name, pasted_command)
        return

    command = pasted_commands[0] if pasted_commands else ""
    device = st.session_state.devices[name]
    mode = st.session_state.cli_modes.get(name, "user")

    # End devices use a PC-style console instead of Cisco IOS syntax.
    if device.device_type in PC_DEVICE_TYPES:
        append_cli(
            name,
            f"{prompt(name)} {command}" if command else prompt(name),
        )

        if not command:
            return

        if execute_pc_cli(name, command):
            return

        append_cli(
            name,
            f"% Invalid input detected: {command}",
        )
        return

    append_cli(
        name,
        f"{prompt(name)} {command}" if command else prompt(name),
    )

    if not command:
        return

    lowered = command.lower()
    words = command.split()

    routing_context = st.session_state.cli_routing_contexts.setdefault(name, {})
    route_map_context = st.session_state.cli_route_map_contexts.setdefault(name, {})
    dhcp_context = st.session_state.cli_dhcp_contexts.setdefault(name, {})

    show_result = show_routing_summary(device, command)
    if show_result.handled:
        if show_result.output:
            append_cli(name, show_result.output)
        return

    if lowered.startswith("ping"):
        if mode not in {"user", "privileged"}:
            append_cli(name, "% Ping is available in EXEC mode. Use 'end' first.")
            return
        query = command.split()[-1]
        ok, resolved, detail = resolve_name(st.session_state.devices, st.session_state.links, name, query)
        if not ok:
            append_cli(name, f"% Unknown host {query}: {detail}")
            return
        resolved_command = " ".join(command.split()[:-1] + [resolved])
        destination_ip, count, error = parse_console_ping(resolved_command)
        if error:
            append_cli(name, error)
            return
        append_cli(
            name,
            console_ping_result(name, destination_ip, count),
        )
        return

    if lowered.startswith("traceroute") or lowered.startswith("tracert"):
        if mode not in {"user", "privileged"}:
            append_cli(
                name,
                "% Traceroute is available in EXEC mode. Use 'end' first.",
            )
            return
        query = command.split()[-1]
        ok, resolved, detail = resolve_name(st.session_state.devices, st.session_state.links, name, query)
        if not ok:
            append_cli(name, f"% Unknown host {query}: {detail}")
            return
        resolved_command = " ".join(command.split()[:-1] + [resolved])
        destination_ip, max_hops, error = parse_console_traceroute(resolved_command)
        if error:
            append_cli(name, error)
            return
        append_cli(
            name,
            console_traceroute_result(name, destination_ip, max_hops),
        )
        return

    if lowered in {
        "copy running-config startup-config",
        "copy run start",
        "write memory",
        "wr mem",
        "wr",
    }:
        if mode != "privileged":
            append_cli(name, "% Privileged EXEC mode required.")
            return
        save_startup_config(device)
        if lowered.startswith("copy"):
            append_cli(
                name,
                "Destination filename [startup-config]?\n"
                "Building configuration...\n[OK]",
            )
        else:
            append_cli(name, "Building configuration...\n[OK]")
        add_event(f"{name}: running configuration saved to startup-config.")
        return

    if lowered in {"erase startup-config", "write erase"}:
        if mode != "privileged":
            append_cli(name, "% Privileged EXEC mode required.")
            return
        device.startup_config = {}
        append_cli(
            name,
            "Erasing the nvram filesystem will remove all configuration files!\n[OK]",
        )
        add_event(f"{name}: startup configuration erased.")
        return

    if lowered in {"reload", "reload now"}:
        if mode != "privileged":
            append_cli(name, "% Privileged EXEC mode required.")
            return
        ok, message = restore_startup_config(device)
        if not ok:
            append_cli(name, message)
            return
        st.session_state.cli_modes[name] = "user"
        st.session_state.cli_interfaces.pop(name, None)
        st.session_state.cli_interface_ranges.pop(name, None)
        st.session_state.cli_vlans.pop(name, None)
        st.session_state.cli_routing_contexts[name] = {}
        st.session_state.cli_route_map_contexts[name] = {}
        st.session_state.cli_dhcp_contexts[name] = {}
        append_cli(
            name,
            "Proceed with reload? [confirm]\nReloading...\n"
            "System Bootstrap, PeerNet Virtual IOS\n" + message,
        )
        add_event(f"{name}: reloaded from startup configuration.")
        return

    if mode == "router":
        result = configure_router_mode(device, command, routing_context)
        if result.handled:
            if result.mode:
                st.session_state.cli_modes[name] = result.mode
            if result.output:
                append_cli(name, result.output)
            return

    if mode == "route_map":
        result = configure_route_map_mode(device, command, route_map_context)
        if result.handled:
            if result.mode:
                st.session_state.cli_modes[name] = result.mode
            if result.output:
                append_cli(name, result.output)
            return

    if mode == "dhcp":
        handled, output, next_mode = configure_dhcp_pool(device, command, dhcp_context)
        if handled:
            if next_mode:
                st.session_state.cli_modes[name] = next_mode
            if output:
                append_cli(name, output)
            return

    if mode == "config":
        handled, output = configure_ip_host(device, command)
        if handled:
            if output:
                append_cli(name, output)
            return
        handled, output = configure_nat_global(device, command)
        if handled:
            if output:
                append_cli(name, output)
            return
        handled, output = configure_access_list(device, command)
        if handled:
            if output:
                append_cli(name, output)
            return
        handled, output, next_mode = configure_dhcp_global(device, command, dhcp_context)
        if handled:
            if not is_routing_device(device):
                append_cli(name, "% DHCP service is supported on routers and multilayer switches.")
                return
            if next_mode:
                st.session_state.cli_modes[name] = next_mode
            if output:
                append_cli(name, output)
            return
        if lowered == "ip routing":
            if device.device_type != "Multilayer Switch":
                append_cli(name, "% 'ip routing' is intended for a multilayer switch.")
            else:
                ensure_routing_defaults(device)["ip_routing"] = True
            return
        if lowered == "no ip routing":
            ensure_routing_defaults(device)["ip_routing"] = False
            return
        if lowered == "ipv6 unicast-routing":
            ensure_routing_defaults(device)["ipv6_unicast_routing"] = True
            return
        if lowered == "no ipv6 unicast-routing":
            ensure_routing_defaults(device)["ipv6_unicast_routing"] = False
            return

        for routing_result in (
            configure_static_route(device, command),
            enter_router_mode(device, command, routing_context),
            configure_policy(device, command, route_map_context),
        ):
            if routing_result.handled:
                if routing_result.mode:
                    st.session_state.cli_modes[name] = routing_result.mode
                if routing_result.output:
                    append_cli(name, routing_result.output)
                return

    if lowered in {"enable", "en"}:
        st.session_state.cli_modes[name] = "privileged"
        return

    if lowered in {"configure terminal", "conf t", "config t"}:
        if mode != "privileged":
            append_cli(name, "% Privileged EXEC mode required.")
        else:
            st.session_state.cli_modes[name] = "config"
        return

    if lowered.startswith("hostname "):
        if mode != "config":
            append_cli(name, "% Enter global configuration mode first.")
            return

        requested_hostname = command.split(maxsplit=1)[1].strip()

        if not requested_hostname or " " in requested_hostname:
            append_cli(name, "% Invalid hostname.")
            return

        new_name = rename_device(name, requested_hostname)

        if new_name != name:
            st.session_state.cli_modes[new_name] = "config"
            st.session_state.terminal_prefill = ""
            st.rerun()
        return

    if lowered.startswith("vlan "):
        if mode != "config":
            append_cli(name, "% Enter global configuration mode first.")
            return
        if not is_switch(device):
            append_cli(name, "% VLAN configuration is available only on switches.")
            return
        values = command.split()
        if len(values) != 2:
            append_cli(name, "% Use: vlan <1-4094>")
            return
        vlan_id, error = validate_vlan_id(values[1])
        if error or vlan_id is None:
            append_cli(name, error or "% Invalid VLAN ID.")
            return
        ensure_switch_defaults(device)
        device.vlans.setdefault(vlan_id, f"VLAN{vlan_id:04d}")
        st.session_state.cli_modes[name] = "vlan"
        st.session_state.cli_vlans[name] = vlan_id
        return

    if lowered.startswith("no vlan "):
        if mode != "config":
            append_cli(name, "% Enter global configuration mode first.")
            return
        if not is_switch(device):
            append_cli(name, "% VLAN configuration is available only on switches.")
            return
        values = command.split()
        if len(values) != 3:
            append_cli(name, "% Use: no vlan <1-4094>")
            return
        vlan_id, error = validate_vlan_id(values[2])
        if error or vlan_id is None:
            append_cli(name, error or "% Invalid VLAN ID.")
            return
        ensure_switch_defaults(device)
        if vlan_id in DEFAULT_VLANS:
            append_cli(name, f"% Default VLAN {vlan_id} cannot be removed.")
            return
        if vlan_id not in device.vlans:
            append_cli(name, f"% VLAN {vlan_id} does not exist.")
            return
        del device.vlans[vlan_id]
        for interface in device.interfaces.values():
            if interface.access_vlan == vlan_id:
                interface.access_vlan = 1
            interface.trunk_allowed_vlans = [
                allowed
                for allowed in interface.trunk_allowed_vlans
                if allowed != vlan_id
            ]
            if interface.native_vlan == vlan_id:
                interface.native_vlan = 1
        return

    if mode == "vlan" and lowered.startswith("name "):
        vlan_name = command.split(maxsplit=1)[1].strip()
        if not vlan_name or len(vlan_name) > 32 or " " in vlan_name:
            append_cli(name, "% VLAN name must be 1-32 characters without spaces.")
            return
        vlan_id = st.session_state.cli_vlans[name]
        device.vlans[vlan_id] = vlan_name
        return

    if mode == "vlan" and lowered == "no name":
        vlan_id = st.session_state.cli_vlans[name]
        device.vlans[vlan_id] = f"VLAN{vlan_id:04d}"
        return

    if lowered.startswith("interface range "):
        if mode not in {"config", "interface", "interface_range"}:
            append_cli(name, "% Enter global configuration mode first.")
            return
        if not is_switch(device):
            append_cli(name, "% Interface range is currently supported on switches.")
            return
        expression = command[len("interface range "):].strip()
        interface_names, error = resolve_interface_range(device, expression)
        if error or not interface_names:
            append_cli(name, error or "% Invalid interface range.")
            return
        st.session_state.cli_modes[name] = "interface_range"
        st.session_state.cli_interfaces.pop(name, None)
        st.session_state.cli_interface_ranges[name] = interface_names
        return

    if lowered.startswith("interface "):
        if mode not in {"config", "interface"}:
            append_cli(name, "% Enter global configuration mode first.")
            return

        # Interface names accept canonical spelling, lowercase spelling, and
        # common Cisco abbreviations such as g0/1, fa0/1, and s0/0/0.
        interface_name = command.split(maxsplit=1)[1].strip()
        exact_interface = resolve_interface_name(
            device,
            interface_name,
        )

        # Create logical routing interfaces on demand while keeping physical
        # interface validation unchanged.
        if exact_interface is None and is_routing_device(device):
            logical_name = normalize_interface_name(interface_name)
            if "." in logical_name:
                parent_name = logical_name.rsplit(".", 1)[0]
                if parent_name in device.interfaces and logical_name.rsplit(".", 1)[1].isdigit():
                    device.interfaces[logical_name] = Interface(logical_name)
                    exact_interface = logical_name
            elif logical_name.lower().startswith("tunnel") and logical_name[6:].isdigit():
                device.interfaces[logical_name] = Interface(logical_name)
                exact_interface = logical_name
            elif (
                device.device_type == "Multilayer Switch"
                and logical_name.lower().startswith("vlan")
                and logical_name[4:].isdigit()
            ):
                vlan_id = int(logical_name[4:])
                ensure_switch_defaults(device)
                if vlan_id in device.vlans:
                    device.interfaces[logical_name] = Interface(logical_name)
                    exact_interface = logical_name

        if exact_interface is None:
            append_cli(
                name,
                f"% Invalid interface '{interface_name}'.\n"
                f"Available interfaces: "
                f"{', '.join(device.interfaces.keys())}",
            )
            return

        st.session_state.cli_modes[name] = "interface"
        st.session_state.cli_interfaces[name] = exact_interface
        st.session_state.cli_interface_ranges.pop(name, None)
        return

    if lowered.startswith("ip address "):
        if mode != "interface":
            append_cli(name, "% Enter interface configuration mode first.")
            return

        values = words[2:]

        try:
            if len(values) == 1 and "/" in values[0]:
                cidr = str(ipaddress.ip_interface(values[0]))
            elif len(values) == 2:
                prefix = ipaddress.IPv4Network(
                    f"0.0.0.0/{values[1]}"
                ).prefixlen
                cidr = str(
                    ipaddress.ip_interface(f"{values[0]}/{prefix}")
                )
            else:
                raise ValueError
        except ValueError:
            append_cli(name, "% Invalid IP address format.")
            return

        interface_name = st.session_state.cli_interfaces[name]
        ok, message = validate_interface_address(
            st.session_state.devices,
            name,
            interface_name,
            cidr,
        )
        if not ok:
            append_cli(name, message)
            return
        device.interfaces[interface_name].ip_address = cidr
        return

    if mode in {"interface", "interface_range"}:
        handled, error = configure_nat_interface(
            [device.interfaces[item] for item in selected_cli_interfaces(name)], command
        )
        if handled:
            if error:
                append_cli(name, error)
            return

    if mode in {"interface", "interface_range"}:
        handled, error = configure_access_group(
            [device.interfaces[item] for item in selected_cli_interfaces(name)], command
        )
        if handled:
            if error:
                append_cli(name, error)
            return

    if mode in {"interface", "interface_range"}:
        routing_interfaces = [
            device.interfaces[interface_name]
            for interface_name in selected_cli_interfaces(name)
        ]
        routing_result = configure_interface_routing(
            device,
            routing_interfaces,
            command,
        )
        if routing_result.handled:
            if routing_result.output:
                append_cli(name, routing_result.output)
            return

    if mode in {"interface", "interface_range"}:
        handled, error = configure_switchports(
            device,
            selected_cli_interfaces(name),
            command,
        )
        if handled:
            if error:
                append_cli(name, error)
            return

    if lowered in {"shutdown", "shut"}:
        if mode in {"interface", "interface_range"}:
            for interface_name in selected_cli_interfaces(name):
                device.interfaces[interface_name].status = "administratively down"
        return

    if lowered in {"no shutdown", "no shut"}:
        if mode in {"interface", "interface_range"}:
            for interface_name in selected_cli_interfaces(name):
                device.interfaces[interface_name].status = "up"
        return

    if lowered == "exit":
        if mode in {"interface", "interface_range", "vlan"}:
            st.session_state.cli_modes[name] = "config"
            st.session_state.cli_interfaces.pop(name, None)
            st.session_state.cli_interface_ranges.pop(name, None)
            st.session_state.cli_vlans.pop(name, None)
        elif mode == "config":
            st.session_state.cli_modes[name] = "privileged"
        elif mode == "privileged":
            st.session_state.cli_modes[name] = "user"
        return

    if lowered == "end":
        st.session_state.cli_modes[name] = "privileged"
        st.session_state.cli_interfaces.pop(name, None)
        st.session_state.cli_interface_ranges.pop(name, None)
        st.session_state.cli_vlans.pop(name, None)
        return

    if lowered.startswith("ip route "):
        if mode != "config":
            append_cli(name, "% Enter global configuration mode first.")
            return

        values = words[2:]

        try:
            if len(values) == 2 and "/" in values[0]:
                network = str(
                    ipaddress.ip_network(values[0], strict=False)
                )
                next_hop = str(ipaddress.ip_address(values[1]))
            else:
                raise ValueError
        except ValueError:
            append_cli(
                name,
                "% Use: ip route 10.0.2.0/24 172.16.0.2",
            )
            return

        device.routing_table[network] = next_hop
        return

    if lowered in {"show ?", "show"}:
        append_cli(name, show_help(device))
        return

    if lowered == "show ip ?":
        append_cli(name, show_ip_help())
        return

    if lowered in {"show ip interface brief", "show ip int brief"}:
        append_cli(name, show_ip_interface_brief(device))
        return

    if lowered == "show interfaces":
        append_cli(name, show_interfaces(device))
        return

    if lowered in {"show access-lists", "show ip access-lists"}:
        append_cli(name, show_access_lists(device))
        return

    if lowered == "show ip nat translations":
        append_cli(name, show_nat_translations(device))
        return

    if lowered == "show ip nat statistics":
        append_cli(name, show_nat_statistics(device))
        return

    if lowered == "show hosts":
        append_cli(name, show_dns_records(device))
        return

    if lowered == "clear ip nat translation *":
        clear_translations(device)
        return

    if lowered == "show interfaces status":
        append_cli(name, show_interfaces_status(device))
        return

    if lowered == "show interfaces trunk":
        if not is_switch(device):
            append_cli(name, "% Trunk information is available only on switches.")
        else:
            append_cli(name, show_interfaces_trunk(device))
        return

    if lowered.startswith("show interfaces ") and lowered.endswith(" switchport"):
        if not is_switch(device):
            append_cli(name, "% Switchport information is available only on switches.")
            return
        interface_name = command.split()[2]
        exact_interface = resolve_interface_name(device, interface_name)
        append_cli(
            name,
            show_interface_switchport(device, exact_interface or interface_name),
        )
        return

    if lowered == "show ip route":
        append_cli(name, show_ip_route(device))
        return

    if lowered == "show ip dhcp binding":
        append_cli(name, show_dhcp_bindings(device))
        return

    if lowered == "show ip dhcp pool":
        append_cli(name, show_dhcp_pools(device))
        return

    if lowered in {"show running-config", "show run"}:
        append_cli(name, running_config(device))
        return

    if lowered == "show startup-config":
        if device.startup_config:
            append_cli(
                name,
                device.startup_config.get("text", "")
                or "Startup configuration is empty.",
            )
        else:
            append_cli(name, "% Startup configuration is not present.")
        return

    if lowered == "show version":
        append_cli(name, show_version(device))
        return

    if lowered == "show arp":
        append_cli(name, show_arp(device))
        return

    if lowered == "show cdp neighbors":
        append_cli(name, show_cdp_neighbors(device))
        return

    if lowered == "show vlan brief":
        append_cli(name, show_vlan_brief(device))
        return

    if lowered == "show mac address-table":
        append_cli(name, show_mac_address_table(device))
        return

    if lowered == "show spanning-tree":
        append_cli(name, show_spanning_tree(device))
        return

    if lowered == "interface ?":
        append_cli(
            name,
            "\n".join(
                f"  {interface_name}"
                for interface_name in device.interfaces
            ),
        )
        return

    if lowered in {"help", "?"}:
        append_cli(
            name,
            "\n".join(command_catalog(device, mode)),
        )
        return

    if lowered == "interface":
        append_cli(
            name,
            "% Incomplete command. Use 'interface ?' "
            "or type 'interface G' and press Tab.",
        )
        return

    if lowered.startswith("show "):
        matches = tab_matches(name, lowered)
        if matches:
            append_cli(
                name,
                "% Incomplete or unknown show command. Matching commands:\n"
                + "\n".join(f"  {item}" for item in matches),
            )
        else:
            append_cli(
                name,
                f"% Unknown show command: {command}\n"
                "Type 'show ?' for available show commands.",
            )
        return

    append_cli(name, f"% Invalid input detected: {command}")


def add_event(message: str) -> None:
    st.session_state.events_log.append(
        {
            "time": time.strftime("%H:%M:%S"),
            "message": message,
        }
    )
    st.session_state.events_log = st.session_state.events_log[-200:]


def _first_device_ip(device_name: str) -> str:
    device = st.session_state.devices.get(device_name)
    if not device:
        return "0.0.0.0"
    for interface in device.interfaces.values():
        if interface.ip_address:
            return interface.ip_address.split("/")[0]
    return "0.0.0.0"


def _device_for_ip(ip_value: str) -> Optional[str]:
    try:
        target = ipaddress.ip_address(ip_value)
    except ValueError:
        return None

    for device_name, device in st.session_state.devices.items():
        for interface in device.interfaces.values():
            if not interface.ip_address:
                continue
            try:
                if ipaddress.ip_interface(interface.ip_address).ip == target:
                    return device_name
            except ValueError:
                continue
    return None


def _topology_path(source: str, destination: str) -> list[str]:
    if source not in st.session_state.devices:
        return []
    if destination not in st.session_state.devices:
        return []

    adjacency = {name: [] for name in st.session_state.devices}

    for link in st.session_state.links:
        a = link.get("source")
        b = link.get("target")
        if a in adjacency and b in adjacency:
            adjacency[a].append(b)
            adjacency[b].append(a)

    queue = [(source, [source])]
    visited = {source}

    while queue:
        node, path = queue.pop(0)
        if node == destination:
            return path

        for neighbor in adjacency.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return []


def _sim_mac(name: str) -> str:
    value = abs(hash(name)) & 0xFFFFFF
    return (
        f"02:00:00:"
        f"{(value >> 16) & 0xff:02x}:"
        f"{(value >> 8) & 0xff:02x}:"
        f"{value & 0xff:02x}"
    )


def record_packet_analysis(
    source: str,
    destination_ip: str,
    operation: str,
    source_ip: str = "",
) -> None:
    source_ip = source_ip or _first_device_ip(source)
    destination_device = _device_for_ip(destination_ip)
    route_result = evaluate_route(
        source,
        source_ip,
        destination_ip,
        st.session_state.devices,
        st.session_state.links,
    )
    path = route_result.path or [source]
    timestamp = time.time()
    analyses = []

    for index, hop in enumerate(path):
        st.session_state.packet_sequence += 1
        packet_no = st.session_state.packet_sequence
        next_hop = (
            path[index + 1]
            if index + 1 < len(path)
            else destination_device
        )

        src_mac = _sim_mac(hop)
        dst_mac = (
            _sim_mac(next_hop)
            if next_hop
            else "ff:ff:ff:ff:ff:ff"
        )
        ttl = max(64 - index, 1)

        record = {
            "no": packet_no,
            "time": timestamp + index * 0.001,
            "source_device": source,
            "hop_device": hop,
            "destination_device": destination_device or "Unknown",
            "source_ip": source_ip,
            "destination_ip": destination_ip,
            "source_mac": src_mac,
            "destination_mac": dst_mac,
            "protocol": "ICMP",
            "length": 98,
            "ttl": ttl,
            "info": (
                f"{operation}: {hop} → "
                f"{next_hop or destination_ip}"
            ),
        }
        st.session_state.packet_records.append(record)

        analyses.append(
            {
                "packet_no": packet_no,
                "hop": index + 1,
                "device": hop,
                "layer_2": f"Ethernet II: {src_mac} → {dst_mac}",
                "layer_3": (
                    f"IPv4: {source_ip} → {destination_ip}, "
                    f"TTL={ttl}"
                ),
                "layer_4": "ICMP Echo",
                "decision": (
                    "Destination reached"
                    if hop == destination_device
                    else f"Forward toward {next_hop or destination_ip}"
                ),
            }
        )

    st.session_state.packet_analysis_output = analyses


def _checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"

    total = 0
    for offset in range(0, len(data), 2):
        total += (data[offset] << 8) + data[offset + 1]
        total = (total & 0xFFFF) + (total >> 16)

    return (~total) & 0xFFFF


def _mac_bytes(value: str) -> bytes:
    try:
        return bytes.fromhex(value.replace(":", ""))
    except ValueError:
        return b"\x00" * 6


def _ip_bytes(value: str) -> bytes:
    try:
        return ipaddress.ip_address(value).packed
    except ValueError:
        return b"\x00\x00\x00\x00"


def _icmp_frame(record: dict) -> bytes:
    payload = b"PeerNet Network Simulator"

    icmp = struct.pack(
        "!BBHHH",
        8,
        0,
        0,
        record["no"] & 0xFFFF,
        1,
    )
    icmp_checksum = _checksum(icmp + payload)
    icmp = struct.pack(
        "!BBHHH",
        8,
        0,
        icmp_checksum,
        record["no"] & 0xFFFF,
        1,
    ) + payload

    total_length = 20 + len(icmp)

    ip_header = struct.pack(
        "!BBHHHBBH4s4s",
        0x45,
        0,
        total_length,
        record["no"] & 0xFFFF,
        0,
        record.get("ttl", 64),
        1,
        0,
        _ip_bytes(record["source_ip"]),
        _ip_bytes(record["destination_ip"]),
    )

    ip_checksum = _checksum(ip_header)

    ip_header = struct.pack(
        "!BBHHHBBH4s4s",
        0x45,
        0,
        total_length,
        record["no"] & 0xFFFF,
        0,
        record.get("ttl", 64),
        1,
        ip_checksum,
        _ip_bytes(record["source_ip"]),
        _ip_bytes(record["destination_ip"]),
    )

    ethernet = (
        _mac_bytes(record["destination_mac"])
        + _mac_bytes(record["source_mac"])
        + struct.pack("!H", 0x0800)
    )

    return ethernet + ip_header + icmp


def build_pcap() -> Optional[Path]:
    records = st.session_state.get("packet_records", [])
    if not records:
        return None

    capture_dir = APP_DIR / "captures"
    capture_dir.mkdir(exist_ok=True)
    capture_path = capture_dir / "peernet_capture.pcap"

    with capture_path.open("wb") as handle:
        handle.write(
            struct.pack(
                "<IHHIIII",
                0xA1B2C3D4,
                2,
                4,
                0,
                0,
                65535,
                1,
            )
        )

        for record in records:
            frame = _icmp_frame(record)
            ts = float(record["time"])
            sec = int(ts)
            usec = int((ts - sec) * 1_000_000)

            handle.write(
                struct.pack(
                    "<IIII",
                    sec,
                    usec,
                    len(frame),
                    len(frame),
                )
            )
            handle.write(frame)

    st.session_state.last_capture_path = str(capture_path)
    return capture_path


def find_wireshark() -> Optional[str]:
    executable = shutil.which("wireshark")
    if executable:
        return executable

    candidates = [
        Path(r"C:\Program Files\Wireshark\Wireshark.exe"),
        Path(r"C:\Program Files (x86)\Wireshark\Wireshark.exe"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return None


def launch_wireshark(capture_path: Path) -> tuple[bool, str]:
    executable = find_wireshark()

    if not executable:
        return False, "Wireshark was not found on this computer."

    try:
        subprocess.Popen(
            [executable, str(capture_path.resolve())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True, "Opened the capture in Wireshark."
    except Exception as error:
        return False, f"Unable to open Wireshark: {error}"

def topology_payload() -> dict:
    return {
        "devices": {
            name: asdict(device)
            for name, device in st.session_state.devices.items()
        },
        "links": list(st.session_state.links),
        "positions": dict(st.session_state.positions),
    }


def restore_topology(payload: dict) -> None:
    devices: dict[str, Device] = {}

    for name, raw in (payload.get("devices") or {}).items():
        device = Device(
            name=name,
            device_type=raw.get("device_type", "Router"),
            routing_table=raw.get("routing_table", {}) or {},
            default_gateway=raw.get("default_gateway", "") or "",
            dns_server=raw.get("dns_server", "") or "",
            vlans={
                int(vlan): vlan_name
                for vlan, vlan_name in (raw.get("vlans") or {}).items()
            },
            route_distances={
                network: int(distance)
                for network, distance in (raw.get("route_distances") or {}).items()
            },
            routing_config=raw.get("routing_config", {}) or {},
            startup_config=raw.get("startup_config", {}) or {},
        )

        for if_name, raw_if in (raw.get("interfaces") or {}).items():
            device.interfaces[if_name] = Interface(
                name=if_name,
                ip_address=raw_if.get("ip_address", ""),
                status=raw_if.get("status", "up"),
                connected_to=raw_if.get("connected_to"),
                switchport_mode=raw_if.get("switchport_mode", "access"),
                access_vlan=int(raw_if.get("access_vlan", 1)),
                native_vlan=int(raw_if.get("native_vlan", 1)),
                trunk_allowed_vlans=[
                    int(vlan)
                    for vlan in raw_if.get("trunk_allowed_vlans", [])
                ],
                description=raw_if.get("description", ""),
                ipv6_address=raw_if.get("ipv6_address", ""),
                encapsulation_dot1q=raw_if.get("encapsulation_dot1q"),
                encapsulation_native=bool(raw_if.get("encapsulation_native", False)),
                ospfv3_process=raw_if.get("ospfv3_process", ""),
                ospfv3_area=raw_if.get("ospfv3_area", ""),
                tunnel_source=raw_if.get("tunnel_source", ""),
                tunnel_destination=raw_if.get("tunnel_destination", ""),
                tunnel_mode=raw_if.get("tunnel_mode", "gre ip"),
                ipsec_profile=raw_if.get("ipsec_profile", ""),
                access_group_in=raw_if.get("access_group_in", ""),
                access_group_out=raw_if.get("access_group_out", ""),
                nat_inside=bool(raw_if.get("nat_inside", False)),
                nat_outside=bool(raw_if.get("nat_outside", False)),
            )

        # Older saved switches may contain only Fa0/1-Fa0/8. Add the new
        # FastEthernet ports without replacing or changing any existing port.
        if device.device_type == "Switch":
            for port in range(1, 25):
                port_name = f"Fa0/{port}"
                device.interfaces.setdefault(port_name, Interface(port_name))

        ensure_switch_defaults(device)
        ensure_routing_defaults(device)
        devices[name] = device

    st.session_state.devices = devices
    st.session_state.links = payload.get("links", []) or []
    st.session_state.positions = payload.get("positions", {}) or {}
    st.session_state.cli_modes = {name: "user" for name in devices}
    st.session_state.cli_interfaces = {}
    st.session_state.cli_interface_ranges = {}
    st.session_state.cli_vlans = {}
    st.session_state.cli_routing_contexts = {}
    st.session_state.cli_route_map_contexts = {}
    st.session_state.cli_dhcp_contexts = {}
    st.session_state.cli_history = {name: [] for name in devices}
    st.session_state.cli_command_history = {name: [] for name in devices}
    st.session_state.deleted_device_undo = []
    st.session_state.booted = set()
    st.session_state.selected_device = (
        next(iter(devices)) if devices else None
    )
    st.session_state.topology_selected_device = None



def delete_device(device_name: str) -> None:
    if device_name not in st.session_state.devices:
        return

    snapshot = {
        "name": device_name,
        "device": copy.deepcopy(st.session_state.devices[device_name]),
        "links": copy.deepcopy([
            link for link in st.session_state.links
            if device_name in {link.get("source"), link.get("target")}
        ]),
        "position": copy.deepcopy(st.session_state.positions.get(device_name)),
        "cli_mode": st.session_state.cli_modes.get(device_name, "user"),
        "cli_interface": st.session_state.cli_interfaces.get(device_name),
        "cli_interface_range": copy.deepcopy(st.session_state.cli_interface_ranges.get(device_name)),
        "cli_vlan": st.session_state.cli_vlans.get(device_name),
        "cli_routing_context": copy.deepcopy(st.session_state.cli_routing_contexts.get(device_name)),
        "cli_route_map_context": copy.deepcopy(st.session_state.cli_route_map_contexts.get(device_name)),
        "cli_dhcp_context": copy.deepcopy(st.session_state.cli_dhcp_contexts.get(device_name)),
        "cli_history": copy.deepcopy(st.session_state.cli_history.get(device_name, [])),
        "cli_command_history": copy.deepcopy(st.session_state.cli_command_history.get(device_name, [])),
        "booted": device_name in st.session_state.booted,
    }
    undo_stack = st.session_state.deleted_device_undo
    undo_stack.append(snapshot)
    del undo_stack[:-20]

    # Clear peer interface references first.
    for device in st.session_state.devices.values():
        for interface in device.interfaces.values():
            if (
                interface.connected_to
                and interface.connected_to.startswith(
                    device_name + ":"
                )
            ):
                interface.connected_to = None

    st.session_state.links = [
        link
        for link in st.session_state.links
        if device_name not in {
            link.get("source"),
            link.get("target"),
        }
    ]

    st.session_state.devices.pop(device_name, None)
    st.session_state.positions.pop(device_name, None)
    st.session_state.cli_modes.pop(device_name, None)
    st.session_state.cli_interfaces.pop(device_name, None)
    st.session_state.cli_interface_ranges.pop(device_name, None)
    st.session_state.cli_vlans.pop(device_name, None)
    st.session_state.cli_routing_contexts.pop(device_name, None)
    st.session_state.cli_route_map_contexts.pop(device_name, None)
    st.session_state.cli_dhcp_contexts.pop(device_name, None)
    st.session_state.cli_history.pop(device_name, None)
    st.session_state.cli_command_history.pop(device_name, None)

    if device_name in st.session_state.booted:
        st.session_state.booted.remove(device_name)

    if st.session_state.selected_device == device_name:
        st.session_state.selected_device = (
            next(iter(st.session_state.devices), None)
        )
    if st.session_state.topology_selected_device == device_name:
        st.session_state.topology_selected_device = None

    st.session_state.dialog_mode = None
    st.session_state.dialog_device = None


def undo_delete_device() -> bool:
    """Restore the most recently deleted device and its surviving links."""
    stack = st.session_state.deleted_device_undo
    if not stack:
        return False
    snapshot = stack.pop()
    name = snapshot["name"]
    if name in st.session_state.devices:
        return False
    st.session_state.devices[name] = snapshot["device"]
    if snapshot.get("position"):
        st.session_state.positions[name] = snapshot["position"]
    st.session_state.cli_modes[name] = snapshot["cli_mode"]
    state_items = (
        ("cli_interfaces", "cli_interface"),
        ("cli_interface_ranges", "cli_interface_range"),
        ("cli_vlans", "cli_vlan"),
        ("cli_routing_contexts", "cli_routing_context"),
        ("cli_route_map_contexts", "cli_route_map_context"),
        ("cli_dhcp_contexts", "cli_dhcp_context"),
    )
    for state_name, snapshot_name in state_items:
        value = snapshot.get(snapshot_name)
        if value is not None:
            st.session_state[state_name][name] = value
    st.session_state.cli_history[name] = snapshot["cli_history"]
    st.session_state.cli_command_history[name] = snapshot["cli_command_history"]
    if snapshot["booted"]:
        st.session_state.booted.add(name)

    for link in snapshot["links"]:
        source, target = link.get("source"), link.get("target")
        if source not in st.session_state.devices or target not in st.session_state.devices:
            continue
        st.session_state.links.append(link)
        for endpoint, interface_key, peer, peer_key in (
            (source, "source_if", target, "target_if"),
            (target, "target_if", source, "source_if"),
        ):
            interface_name = link.get(interface_key)
            if interface_name in st.session_state.devices[endpoint].interfaces:
                st.session_state.devices[endpoint].interfaces[interface_name].connected_to = (
                    f"{peer}:{link.get(peer_key, '')}"
                )
    st.session_state.selected_device = name
    return True

def clear_topology() -> None:
    st.session_state.devices = {}
    st.session_state.links = []
    st.session_state.positions = {}
    st.session_state.cli_modes = {}
    st.session_state.cli_interfaces = {}
    st.session_state.cli_interface_ranges = {}
    st.session_state.cli_vlans = {}
    st.session_state.cli_routing_contexts = {}
    st.session_state.cli_route_map_contexts = {}
    st.session_state.cli_dhcp_contexts = {}
    st.session_state.cli_history = {}
    st.session_state.cli_command_history = {}
    st.session_state.deleted_device_undo = []
    st.session_state.booted = set()
    st.session_state.selected_device = None
    st.session_state.topology_selected_device = None


def load_demo() -> None:
    clear_topology()

    router = add_device("Router", {"x": 300, "y": 220})
    switch = add_device("Switch", {"x": 580, "y": 220})
    pc = add_device("PC", {"x": 860, "y": 220})
    cloud = add_device("Network Cloud", {"x": 300, "y": 420})

    st.session_state.devices[router].interfaces[
        "Gi0/0"
    ].ip_address = "192.168.1.1/24"

    st.session_state.devices[switch].interfaces[
        "Vlan1"
    ] = Interface("Vlan1", "192.168.1.2/24")

    st.session_state.devices[pc].interfaces[
        "eth0"
    ].ip_address = "192.168.1.10/24"

    connect_devices(router, switch)
    connect_devices(switch, pc)
    connect_devices(router, cloud)

    st.session_state.selected_device = router


def node_payload() -> list[dict]:
    result = []

    for name, device in st.session_state.devices.items():
        ip_value = ""

        for interface in device.interfaces.values():
            if interface.ip_address:
                ip_value = interface.ip_address.split("/")[0]
                break

        interface_labels = []
        for interface in device.interfaces.values():
            if interface.ip_address or interface.connected_to:
                if device.device_type not in {"Switch", "Multilayer Switch"}:
                    mode_text = "routed"
                    vlan_text = "not applicable"
                elif interface.switchport_mode == "trunk":
                    mode_text = "trunk"
                    vlan_text = f"trunk/native {interface.native_vlan}"
                else:
                    mode_text = "access"
                    vlan_text = f"access VLAN {interface.access_vlan}"
                interface_labels.append(
                    {
                        "name": interface.name,
                        "ip": interface.ip_address.split("/")[0] if interface.ip_address else "unassigned",
                        "connected": bool(interface.connected_to),
                        "peer": interface.connected_to or "unassigned",
                        "status": interface.status,
                        "mode": mode_text,
                        "vlan": vlan_text,
                    }
                )

        result.append(
            {
                "id": name,
                "label": name,
                "device_type": device.device_type,
                "ip": ip_value,
                "interfaces": interface_labels,
                "position": st.session_state.positions.get(
                    name,
                    {"x": 220, "y": 180},
                ),
            }
        )

    return result


def edge_payload() -> list[dict]:
    animation = st.session_state.get("packet_animation", {})
    if animation and animation.get("expires_at", 0) <= time.time():
        animation = {}
        st.session_state.packet_animation = {}
    animation_path = animation.get("path", [])
    animated_links: dict[str, tuple[int, bool]] = {}
    for order, (path_source, path_target) in enumerate(
        zip(animation_path, animation_path[1:])
    ):
        matching_link = next(
            (
                link
                for link in st.session_state.links
                if {link.get("source"), link.get("target")}
                == {path_source, path_target}
                and not link.get("forced_down")
            ),
            None,
        )
        if matching_link:
            animated_links[matching_link["id"]] = (
                order,
                matching_link.get("source") != path_source,
            )

    result = []
    for item in st.session_state.links:
        status, status_reason = link_operational_status(item)
        animation_data = animated_links.get(item["id"])
        source_details = topology_interface_details(
            item.get("source", ""), item.get("source_if", "")
        )
        target_details = topology_interface_details(
            item.get("target", ""), item.get("target_if", "")
        )
        result.append({
            "id": item["id"],
            "source": item["source"],
            "target": item["target"],
            "source_if": item.get("source_if", ""),
            "target_if": item.get("target_if", ""),
            "connector_type": item.get(
                "connector_type",
                "Ethernet / Copper",
            ),
            "status": status,
            "status_reason": status_reason,
            "animate": animation_data is not None and status == "up",
            "animation_order": animation_data[0] if animation_data else 0,
            "animation_reverse": animation_data[1] if animation_data else False,
            "animation_id": animation.get("id", ""),
            "animation_protocol": animation.get("protocol", "ICMP"),
            "source_details": source_details,
            "target_details": target_details,
        })
    return result


def handle_canvas_event(event: Optional[dict]) -> None:
    if not event:
        return

    if event.get("id") == st.session_state.last_event:
        return

    st.session_state.last_event = event.get("id")
    action = event.get("action")

    if action == "move":
        node_id = event.get("node_id")

        if node_id in st.session_state.devices:
            st.session_state.positions[node_id] = event.get(
                "position",
                {},
            )

    elif action == "connect":
        connect_devices(
            event.get("source"),
            event.get("target"),
        )
        st.rerun()

    elif action == "select_device":
        node_id = event.get("node_id")
        if node_id in st.session_state.devices:
            st.session_state.selected_device = node_id
            st.session_state.topology_selected_device = node_id
            st.rerun()

    elif action == "clear_selection":
        if st.session_state.topology_selected_device is not None:
            st.session_state.topology_selected_device = None
            st.rerun()

    elif action == "undo_delete":
        if undo_delete_device():
            st.rerun()

    elif action in {
        "configure",
        "open_console",
        "interfaces",
        "disconnect_link",
        "add_interface",
        "delete_device",
    }:
        node_id = event.get("node_id")

        if node_id not in st.session_state.devices:
            return

        st.session_state.selected_device = node_id
        device = st.session_state.devices[node_id]

        if action in {"configure", "open_console"}:
            boot(node_id)

            if (
                action == "configure"
                and device.device_type in PC_DEVICE_TYPES
            ):
                st.session_state.dialog_mode = "pc_config"
                st.session_state.dialog_device = node_id
            else:
                # The shared console is used for network devices and
                # "Open Console" on all devices.
                st.session_state.dialog_mode = None
                st.session_state.dialog_device = None

            st.rerun()

        elif action == "interfaces":
            st.session_state.dialog_mode = "interfaces"
            st.session_state.dialog_device = node_id
            st.rerun()

        elif action == "add_interface":
            st.session_state.dialog_mode = "add_interface"
            st.session_state.dialog_device = node_id
            st.rerun()

        elif action == "disconnect_link":
            st.session_state.dialog_mode = "disconnect_link"
            st.session_state.dialog_device = node_id
            st.rerun()

        elif action == "delete_device":
            delete_device(node_id)
            st.rerun()

    elif action == "select_for_connect":
        node_id = event.get("node_id")
        if node_id in st.session_state.devices:
            if not st.session_state.connect_source:
                st.session_state.connect_source = node_id
            elif node_id != st.session_state.connect_source:
                st.session_state.connect_target = node_id
            st.rerun()


@st.dialog("Device Configuration", width="large")
def configure_dialog(name: str) -> None:
    boot(name)
    device = st.session_state.devices[name]

    st.caption(f"{name} • {device.device_type}")
    st.code(
        "\n".join(st.session_state.cli_history[name]),
        language="text",
    )

    with st.form(
        f"cli_{name}",
        clear_on_submit=True,
        border=False,
    ):
        command = st.text_input(
            "Command",
            placeholder=f"{prompt(name)} ",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button(
            "Enter",
            width="stretch",
            type="primary",
        )

    if submitted:
        execute_cli(name, command)
        st.rerun()

    if st.button("Close", key=f"close_config_{name}"):
        st.session_state.dialog_mode = None
        st.rerun()



@st.dialog("PC IP Configuration", width="large")
def pc_config_dialog(name: str) -> None:
    device = st.session_state.devices[name]
    interface = primary_pc_interface(device)

    st.subheader(f"{name} — IP Configuration")

    if interface is None:
        st.error("No network adapter is available.")
    else:
        current_ip = ""
        current_mask = ""

        if interface.ip_address:
            try:
                parsed = ipaddress.ip_interface(
                    interface.ip_address
                )
                current_ip = str(parsed.ip)
                current_mask = str(parsed.network.netmask)
            except ValueError:
                pass

        with st.form(f"pc_config_{name}"):
            ip_value = st.text_input(
                "IP Address",
                value=current_ip,
                placeholder="10.1.1.3",
            )
            mask_value = st.text_input(
                "Subnet Mask",
                value=current_mask,
                placeholder="255.255.255.0",
            )
            gateway_value = st.text_input(
                "Default Gateway",
                value=device.default_gateway,
                placeholder="10.1.1.1",
            )
            dns_value = st.text_input(
                "DNS Server",
                value=device.dns_server,
                placeholder="8.8.8.8",
            )

            apply_clicked = st.form_submit_button(
                "Apply",
                type="primary",
                width="stretch",
            )

        if apply_clicked:
            ok, message = pc_apply_static_ip(
                device,
                ip_value,
                mask_value,
                gateway_value,
            )

            if ok:
                if dns_value:
                    try:
                        ipaddress.ip_address(dns_value)
                        device.dns_server = dns_value
                    except ValueError:
                        st.error("Invalid DNS server address.")
                        return

                st.success(message)
                st.session_state.dialog_mode = None
                st.rerun()
            else:
                st.error(message)

    if st.button("Close", key=f"close_pc_config_{name}"):
        st.session_state.dialog_mode = None
        st.rerun()


@st.dialog("Add Interface", width="small")
def add_interface_dialog(name: str) -> None:
    device = st.session_state.devices[name]

    port_family = st.selectbox(
        "Interface type",
        [
            "GigabitEthernet",
            "FastEthernet",
            "Ethernet",
            "Serial",
            "Fiber",
            "Wireless",
        ],
        key=f"ctx_port_family_{name}",
    )

    if st.button(
        "Add Interface",
        type="primary",
        width="stretch",
        key=f"ctx_add_port_{name}",
    ):
        ok, message = add_device_port(
            name,
            port_family,
        )

        if ok:
            st.success(message)
            st.session_state.dialog_mode = None
            st.rerun()
        else:
            st.error(message)

    if st.button("Close", key=f"close_add_if_{name}"):
        st.session_state.dialog_mode = None
        st.rerun()


@st.dialog("Interfaces", width="large")
def interfaces_dialog(name: str) -> None:
    device = st.session_state.devices[name]

    st.subheader(f"{name} — {device.device_type}")

    for interface in device.interfaces.values():
        state = "USED" if interface.connected_to else "FREE"
        st.write(
            f"**{interface.name}** — "
            f"`{interface.ip_address or 'unassigned'}` — "
            f"`{interface.status}` — "
            f"**{state}** — "
            f"`{interface.connected_to or 'not connected'}`"
        )

    st.divider()
    st.caption(
        "Use the right-side Ports tab to add more interfaces."
    )

    if st.button("Close", key=f"close_interfaces_{name}"):
        st.session_state.dialog_mode = None
        st.rerun()


@st.dialog("Disconnect Link", width="large")
def disconnect_link_dialog(name: str) -> None:
    device_links = links_for_device(name)
    st.subheader(f"{name} — Connected interfaces")

    if not device_links:
        st.info(
            f"{name} has no active connections. Its free interfaces are unassigned."
        )
    else:
        link_map = {link["id"]: link for link in device_links}
        selected_id = st.selectbox(
            "Select the connection to remove",
            list(link_map),
            format_func=lambda link_id: link_label(link_map[link_id]),
            key=f"dialog_disconnect_select_{name}",
        )
        selected_link = link_map[selected_id]
        left_col, right_col = st.columns(2)
        with left_col:
            st.markdown("**Source device side**")
            st.code(
                f"{selected_link['source']}:"
                f"{selected_link.get('source_if') or 'unassigned'}",
                language="text",
            )
        with right_col:
            st.markdown("**Destination device side**")
            st.code(
                f"{selected_link['target']}:"
                f"{selected_link.get('target_if') or 'unassigned'}",
                language="text",
            )

        confirmed = st.checkbox(
            "I understand that only this cable will be removed.",
            key=f"dialog_disconnect_confirm_{name}",
        )
        if st.button(
            "Disconnect selected link",
            type="primary",
            width="stretch",
            disabled=not confirmed,
            key=f"dialog_disconnect_btn_{name}",
        ):
            ok, message = disconnect_link(selected_id)
            if ok:
                st.success(message)
                st.session_state.dialog_mode = None
                st.session_state.dialog_device = None
                st.rerun()
            else:
                st.error(message)

    if st.button("Close", key=f"close_disconnect_{name}"):
        st.session_state.dialog_mode = None
        st.session_state.dialog_device = None
        st.rerun()


def auth_page() -> None:
    logo64 = base64.b64encode(LOGO.read_bytes()).decode()

    # Keep the original two-column login layout so the side illustration
    # remains present. Only the login-side presentation is redesigned.
    form_col, art_col = st.columns([1.02, 1.18], gap="large")

    with form_col:
        st.markdown(
            f"""
            <div class="pn-auth-eyebrow">Browser-Based Network Lab</div>
            <div class="pn-auth-logo">
                <img src="data:image/png;base64,{logo64}">
            </div>
            <div class="pn-auth-title">
                <span class="pn-auth-peer">PeerNet</span>
                <span class="pn-auth-network"> Network Simulator</span>
            </div>
            <div class="pn-auth-tagline">
                Design • Simulate • Test • Analyze
            </div>
            <div class="pn-auth-benefits">
                <span>Live CLI</span>
                <span>Visual Topology</span>
                <span>AI Assistance</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(
            border=True,
            key="peernet_auth_box",
        ):
            login_tab, signup_tab, reset_tab = st.tabs(
                ["Login", "Register", "Forgot password"]
            )

            with login_tab:
                with st.form("login"):
                    email = st.text_input(
                        "Gmail address",
                        placeholder="Enter your Gmail address",
                    )
                    password = st.text_input(
                        "Password",
                        type="password",
                        placeholder="Enter your password",
                    )
                    submitted = st.form_submit_button(
                        "Login →",
                        type="primary",
                        width="stretch",
                    )

                if submitted:
                    try:
                        sign_in(email, password)
                        st.rerun()
                    except Exception as error:
                        st.error(f"Unable to sign in: {error}")

            with signup_tab:
                with st.form("signup"):
                    full_name = st.text_input(
                        "Full name",
                        placeholder="Enter your full name",
                    )
                    username = st.text_input(
                        "Username",
                        key="signup_username",
                        placeholder="Choose a username",
                        help="Use at least 3 letters, numbers, or underscores.",
                    )
                    email = st.text_input(
                        "Gmail address",
                        key="signup_email",
                        placeholder="Enter your Gmail address",
                    )
                    password = st.text_input(
                        "Password",
                        type="password",
                        key="signup_password",
                        placeholder="Create a password",
                    )
                    confirm_password = st.text_input(
                        "Confirm password",
                        type="password",
                        key="signup_confirm_password",
                        placeholder="Re-enter your password",
                    )
                    accepted_terms = st.checkbox(
                        "I agree to the Terms of Use and Privacy Policy.",
                        key="signup_terms_accepted",
                    )
                    submitted = st.form_submit_button(
                        "Create account",
                        width="stretch",
                    )

                if submitted:
                    cleaned_username = username.strip()
                    if len(cleaned_username) < 3:
                        st.error("Username must contain at least 3 characters.")
                    elif not cleaned_username.replace("_", "").isalnum():
                        st.error(
                            "Username can contain only letters, numbers, and underscores."
                        )
                    elif password != confirm_password:
                        st.error("Passwords do not match. Please try again.")
                    elif not accepted_terms:
                        st.error(
                            "You must agree to the Terms of Use and Privacy Policy."
                        )
                    else:
                        try:
                            sign_up(
                                email,
                                password,
                                full_name,
                                cleaned_username,
                            )
                            st.success(
                                "Account created. Verify your email before signing in."
                            )
                        except Exception as error:
                            st.error(str(error))

            with reset_tab:
                email = st.text_input(
                    "Gmail address",
                    key="reset_email",
                    placeholder="Enter your Gmail address",
                )

                if st.button(
                    "Send reset link",
                    width="stretch",
                ):
                    try:
                        send_password_reset(email)
                        st.success("Password reset email sent.")
                    except Exception as error:
                        st.error(str(error))

        st.markdown(
            '<div class="pn-auth-side-caption">'
            '© 2026 PeerNet Solutions. All rights reserved.'
            '</div>',
            unsafe_allow_html=True,
        )

    with art_col:
        # Existing side image is intentionally preserved.
        with st.container(key="peernet_auth_art"):
            st.image(
                LOGIN_ART,
                width="stretch",
            )


apply_styles()
init_state()

if not st.session_state.authenticated:
    auth_page()
    st.stop()

logo64 = base64.b64encode(LOGO.read_bytes()).decode()
user = (
    st.session_state.get("user_name")
    or st.session_state.get("user_email")
    or "PeerNet User"
)
initial = str(user).strip()[:1].upper() or "P"

# ============================================================
# NATIVE LEFT SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown(
        '<div class="pn-left-card">',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="pn-logo">'
        f'<img src="data:image/png;base64,{logo64}">'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="pn-user-card">
            <div class="pn-avatar">
                {html.escape(initial)}
                <span class="pn-dot"></span>
            </div>
            <div class="pn-user-copy">
                <strong>{html.escape(str(user))}</strong>
                <small>Online</small>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="pn-section-title">▣ PROJECTS</div>',
        unsafe_allow_html=True,
    )

    try:
        projects = list_simulator_projects()
    except Exception:
        projects = []

    project_map = {
        f"{item.get('name','Untitled')} · "
        f"{str(item.get('id',''))[:6]}": item
        for item in projects
    }

    pending_project_name = st.session_state.pop(
        "_pending_project_name",
        None,
    )
    if pending_project_name is not None:
        st.session_state.project_name = pending_project_name

    project_name = st.text_input(
        "Project Name",
        value=st.session_state.get(
            "current_project_name",
            "Untitled topology",
        ),
        key="project_name",
    )

    if st.button(
        "Create Project",
        width="stretch",
        key="project_create",
    ):
        clear_topology()
        st.session_state.current_project_id = None
        st.session_state.current_project_name = (
            project_name or "Untitled topology"
        )
        st.rerun()

    selected_project = st.selectbox(
        "Select Project",
        ["New Project"] + list(project_map),
        key="project_select",
    )

    open_col, delete_col = st.columns(2)

    with open_col:
        if st.button(
            "📂 Open",
            width="stretch",
            disabled=selected_project not in project_map,
            key="project_open",
        ):
            try:
                project = load_simulator_project(
                    project_map[selected_project]["id"]
                )
                restore_topology(
                    project.get("topology_json", {}) or {}
                )
                st.session_state.current_project_id = project["id"]
                st.session_state.current_project_name = project["name"]
                st.session_state._pending_project_name = project["name"]
                st.rerun()
            except Exception as error:
                st.error(f"Unable to open project: {error}")

    with delete_col:
        if st.button(
            "🗑 Delete",
            width="stretch",
            disabled=selected_project not in project_map,
            key="project_delete",
        ):
            try:
                delete_simulator_project(
                    project_map[selected_project]["id"]
                )
                st.rerun()
            except Exception as error:
                st.error(f"Unable to delete project: {error}")

    if st.button(
        "💾 Save Project",
        width="stretch",
        key="project_save",
    ):
        try:
            if st.session_state.current_project_id:
                project = update_simulator_project(
                    st.session_state.current_project_id,
                    project_name or "Untitled topology",
                    topology_payload(),
                )
            else:
                project = create_simulator_project(
                    project_name or "Untitled topology",
                    topology_payload(),
                )

            st.session_state.current_project_id = project["id"]
            st.session_state.current_project_name = project["name"]
            st.success("Project saved.")
            st.rerun()
        except Exception as error:
            st.error(f"Unable to save project: {error}")

    st.markdown(
        '<div class="pn-section-title devices">◉ DEVICES</div>',
        unsafe_allow_html=True,
    )

    category = st.selectbox(
        "Select Category",
        list(DEVICE_GROUPS),
        key="device_category",
    )

    device_type = st.selectbox(
        "Select Device",
        DEVICE_GROUPS[category],
        key="device_type",
    )

    if st.button(
        f"＋ Add {device_type}",
        width="stretch",
        key="device_add",
    ):
        add_device(device_type)
        st.rerun()

    demo_col, reset_col = st.columns(2)

    with demo_col:
        if st.button(
            "Demo",
            width="stretch",
            key="load_demo",
        ):
            load_demo()
            st.rerun()

    with reset_col:
        if st.button(
            "Reset",
            width="stretch",
            key="reset_topology",
        ):
            clear_topology()
            st.rerun()

    with st.container(key="logout_btn"):
        if st.button(
            "↪ Logout",
            width="stretch",
        ):
            try:
                sign_out()
            except Exception:
                pass

            st.session_state.authenticated = False
            st.rerun()

    st.markdown(
        """
        <div class="pn-footer">
            Powered by <strong style="color:#2563eb">
            PeerNet Solutions</strong><br>
            <span class="pn-license">PeerNet Simulator License</span><br>
            © 2026 PeerNet Solutions. All rights reserved.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )

# ============================================================
# MAIN WORKSPACE
# ============================================================
title_col, toolbar_col = st.columns([1.6, 2.4])

with title_col:
    st.markdown(
        f"""
        <div class="pn-topbar">
            <div>
                <h2>⌘ Topology</h2>
                <div class="pn-subtitle">
                    {html.escape(st.session_state.current_project_name)}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with toolbar_col:
    greeting_space_col, greeting_col, delete_tool_col = st.columns(
        [0.8, 3.1, 1],
        gap="small",
    )
    ist_now = datetime.now(
        timezone(timedelta(hours=5, minutes=30))
    )
    if 5 <= ist_now.hour < 12:
        greeting = "Good Morning"
    elif 12 <= ist_now.hour < 17:
        greeting = "Good Afternoon"
    elif 17 <= ist_now.hour < 22:
        greeting = "Good Evening"
    else:
        greeting = "Good Night"

    with greeting_col:
        st.markdown(
            f"""
            <div class="pn-ist-greeting">
                {greeting}, {html.escape(str(user))} 👋
            </div>
            """,
            unsafe_allow_html=True,
        )

    with delete_tool_col:
        if st.button(
            "🗑 Delete",
            width="stretch",
            key="tool_delete",
        ):
            selected = st.session_state.topology_selected_device

            if selected in st.session_state.devices:
                delete_device(selected)
                st.rerun()

canvas_col, right_col = st.columns([4.8, 1.15], gap="small")

with canvas_col:
    st.markdown(
        '<div class="pn-canvas-card">',
        unsafe_allow_html=True,
    )

    event = topology_canvas(
        node_payload(),
        edge_payload(),
        selected_device=st.session_state.topology_selected_device,
        height=520,
        key="topology_canvas",
    )
    handle_canvas_event(event)

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )

with right_col:
    # Match the full rendered topology card (canvas plus component spacing).
    # Long tab content scrolls
    # inside this panel instead of pushing the Console farther down the page.
    with st.container(height=540, key="topology_side_panel"):
        connect_tab, disconnect_tab, device_tab, end_tab, port_tab = st.tabs(
            ["Connect", "Disconnect", "Devices", "End Users", "Ports"]
        )

    with connect_tab:
        device_names = list(st.session_state.devices)

        if len(device_names) < 2:
            st.info("Add at least two devices to create a link.")
        else:
            source_default = (
                st.session_state.connect_source
                if st.session_state.connect_source in device_names
                else device_names[0]
            )

            source = st.selectbox(
                "Source device",
                device_names,
                index=device_names.index(source_default),
                key="easy_connect_source",
            )
            st.session_state.connect_source = source

            source_free = free_interfaces(source)

            if source_free:
                source_if = st.selectbox(
                    "Free source interface",
                    source_free,
                    key="easy_source_if",
                )
            else:
                source_if = None
                st.warning(
                    f"{source} has no free interfaces. "
                    "Use the Ports tab to add one."
                )

            target_choices = [
                name
                for name in device_names
                if name != source
            ]

            target_default = (
                st.session_state.connect_target
                if st.session_state.connect_target in target_choices
                else target_choices[0]
            )

            target = st.selectbox(
                "Destination device",
                target_choices,
                index=target_choices.index(target_default),
                key="easy_connect_target",
            )
            st.session_state.connect_target = target

            target_free = free_interfaces(target)

            if target_free:
                target_if = st.selectbox(
                    "Free destination interface",
                    target_free,
                    key="easy_target_if",
                )
            else:
                target_if = None
                st.warning(
                    f"{target} has no free interfaces. "
                    "Use the Ports tab to add one."
                )

            connector = st.selectbox(
                "Connector type",
                list(CONNECTOR_TYPES),
                index=list(CONNECTOR_TYPES).index(
                    st.session_state.get(
                        "connector_type",
                        "Ethernet / Copper",
                    )
                ),
                key="easy_connector_type",
            )
            st.session_state.connector_type = connector
            st.markdown(
                connector_preview_html(connector),
                unsafe_allow_html=True,
            )

            if source_if and target_if:
                st.caption(
                    f"{source}:{source_if}  ↔  "
                    f"{target}:{target_if}"
                )

                if st.button(
                    "🔌 Connect Interfaces",
                    width="stretch",
                    type="primary",
                    key="easy_connect_btn",
                ):
                    ok, message = connect_interfaces(
                        source,
                        source_if,
                        target,
                        target_if,
                        connector,
                    )
                    if ok:
                        st.session_state.connect_source = None
                        st.session_state.connect_target = None
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

    with disconnect_tab:
        if not st.session_state.links:
            st.info("There are no active connections to remove.")
        else:
            disconnect_map = {
                link["id"]: link
                for link in st.session_state.links
            }
            disconnect_id = st.selectbox(
                "Active connection",
                list(disconnect_map),
                format_func=lambda link_id: link_label(
                    disconnect_map[link_id]
                ),
                key="easy_disconnect_link",
            )
            disconnect_item = disconnect_map[disconnect_id]
            link_status, link_reason = link_operational_status(disconnect_item)
            status_label = {
                "up": "🟢 Up",
                "down": "🔴 Down",
                "admin-down": "🟠 Administratively down",
            }[link_status]
            st.caption(f"Link status: {status_label} — {link_reason}")
            st.caption("Source device side")
            st.code(
                f"{disconnect_item['source']}:"
                f"{disconnect_item.get('source_if') or 'unassigned'}",
                language="text",
            )
            st.caption("Destination device side")
            st.code(
                f"{disconnect_item['target']}:"
                f"{disconnect_item.get('target_if') or 'unassigned'}",
                language="text",
            )
            if disconnect_item.get("forced_down"):
                if st.button(
                    "🛠 Restore Cable",
                    width="stretch",
                    key="restore_selected_link",
                ):
                    disconnect_item["forced_down"] = False
                    add_event(f"Cable restored: {link_label(disconnect_item)}.")
                    st.rerun()
            else:
                if st.button(
                    "⚠ Simulate Cable Failure",
                    width="stretch",
                    key="fail_selected_link",
                ):
                    disconnect_item["forced_down"] = True
                    add_event(f"Cable failure: {link_label(disconnect_item)}.")
                    st.rerun()
            confirm_disconnect = st.checkbox(
                "Confirm removal of this cable",
                key="easy_disconnect_confirm",
            )
            if st.button(
                "⛓ Disconnect Link",
                width="stretch",
                type="primary",
                disabled=not confirm_disconnect,
                key="easy_disconnect_btn",
            ):
                ok, message = disconnect_link(disconnect_id)
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

    with device_tab:
        for item in DEVICE_GROUPS["Network Devices"]:
            if st.button(
                item,
                width="stretch",
                key=f"right_add_{item}",
            ):
                add_device(item)
                st.rerun()

    with end_tab:
        for item in DEVICE_GROUPS["End Users"]:
            if st.button(
                item,
                width="stretch",
                key=f"right_add_{item}",
            ):
                add_device(item)
                st.rerun()

    with port_tab:
        if st.session_state.devices:
            port_device = st.selectbox(
                "Device",
                list(st.session_state.devices),
                key="port_device",
            )

            port_family = st.selectbox(
                "Port type",
                [
                    "GigabitEthernet",
                    "FastEthernet",
                    "Serial",
                    "Fiber",
                    "Wireless",
                    "Ethernet",
                ],
                key="port_family",
            )

            if st.button(
                "＋ Add Port",
                width="stretch",
                key="add_port_button",
            ):
                ok, message = add_device_port(
                    port_device,
                    port_family,
                )
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

            st.caption("Current interfaces")
            for interface in st.session_state.devices[
                port_device
            ].interfaces.values():
                state = (
                    "used"
                    if interface.connected_to
                    else "free"
                )
                st.write(
                    f"`{interface.name}` — {state}"
                )
        else:
            st.info("Add a device first.")

# Single interactive console plus network tools.
(
    console_tab,
    ping_tab,
    trace_tab,
    validation_tab,
    packet_tab,
    wireshark_tab,
    ai_tab,
) = st.tabs(
    [
        "Console",
        "Ping",
        "Traceroute",
        "Validation",
        "Packet Analysis",
        "Wireshark",
        "✨ AI Assistant",
    ]
)

# Native Streamlit tab markup can vary by release. Apply the AI tab styling
# directly after render so it remains at the far-right edge across versions.
components.html(
    """
    <script>
    (() => {
      const styleAI = () => {
        const doc = window.parent.document;
        const rows = Array.from(doc.querySelectorAll('[role="tablist"]'));
        const row = rows.find(item =>
          item.querySelectorAll('[role="tab"]').length === 7
        );
        if (!row) return false;

        const tabs = row.querySelectorAll('[role="tab"]');
        const ai = tabs[tabs.length - 1];
        row.style.setProperty('display', 'flex', 'important');
        row.style.setProperty('width', '100%', 'important');
        ai.style.setProperty('margin-left', 'auto', 'important');
        ai.style.setProperty('padding', '.45rem .9rem', 'important');
        ai.style.setProperty('border', '1px solid rgba(124,58,237,.38)', 'important');
        ai.style.setProperty('border-radius', '999px', 'important');
        ai.style.setProperty(
          'background',
          'linear-gradient(135deg,#7c3aed 0%,#2563eb 55%,#06b6d4 100%)',
          'important'
        );
        ai.style.setProperty('color', '#ffffff', 'important');
        ai.style.setProperty('font-weight', '850', 'important');
        ai.style.setProperty(
          'box-shadow',
          '0 6px 16px rgba(79,70,229,.28)',
          'important'
        );
        ai.querySelectorAll('*').forEach(child => {
          child.style.setProperty('color', '#ffffff', 'important');
          child.style.setProperty('font-weight', '850', 'important');
        });
        return true;
      };

      let attempts = 0;
      const timer = window.setInterval(() => {
        attempts += 1;
        if (styleAI() || attempts >= 40) window.clearInterval(timer);
      }, 100);
    })();
    </script>
    """,
    height=1,
)

selected_device = st.session_state.selected_device

with console_tab:
    if st.session_state.devices:
        device_names = list(st.session_state.devices)

        if selected_device not in device_names:
            selected_device = device_names[0]
            st.session_state.selected_device = selected_device

        selected_device = st.selectbox(
            "Console device",
            device_names,
            index=device_names.index(selected_device),
            key="console_device_select",
        )
        st.session_state.selected_device = selected_device
        boot(selected_device)

        terminal_history = "\n".join(
            st.session_state.cli_history[selected_device][-80:]
        )

        focus_terminal = (
            st.session_state.pop("terminal_focus_device", None)
            == selected_device
        )

        terminal_event = inline_terminal(
            history=terminal_history,
            prompt=prompt(selected_device),
            device_name=selected_device,
            command_history=st.session_state.cli_command_history.setdefault(
                selected_device, []
            ),
            prefill=st.session_state.get("terminal_prefill", ""),
            focus_input=focus_terminal,
            height=390,
            key=f"inline_terminal_{selected_device}",
        )
        st.session_state.terminal_prefill = ""

        if (
            terminal_event
            and terminal_event.get("id")
            != st.session_state.last_terminal_event
        ):
            st.session_state.last_terminal_event = terminal_event.get("id")

            if terminal_event.get("action") == "command":
                submitted_command = terminal_event.get("command", "")
                command_lines = [
                    line.strip()
                    for line in submitted_command.replace("\r", "\n").split("\n")
                    if line.strip()
                ]
                command_history = st.session_state.cli_command_history.setdefault(
                    selected_device, []
                )
                command_history.extend(command_lines)
                del command_history[:-100]
                execute_cli(
                    selected_device,
                    submitted_command,
                )
                st.session_state.terminal_focus_device = selected_device
                st.rerun()

            elif terminal_event.get("action") == "tab":
                partial = terminal_event.get("command", "")
                matches = tab_matches(selected_device, partial)

                if len(matches) == 1:
                    st.session_state.terminal_prefill = matches[0]
                elif len(matches) > 1:
                    append_cli(
                        selected_device,
                        f"{prompt(selected_device)} {partial}",
                    )
                    append_cli(
                        selected_device,
                        "\n".join(matches),
                    )
                    st.session_state.terminal_prefill = partial
                else:
                    append_cli(
                        selected_device,
                        f"{prompt(selected_device)} {partial}",
                    )
                    append_cli(
                        selected_device,
                        "% No matching commands.",
                    )
                    st.session_state.terminal_prefill = partial

                st.session_state.terminal_focus_device = selected_device
                st.rerun()

        quick1, quick2, quick3, quick4 = st.columns(4)

        with quick1:
            if st.button(
                "show ip int brief",
                width="stretch",
                key="quick_interfaces",
            ):
                execute_cli(
                    selected_device,
                    "show ip interface brief",
                )
                st.rerun()

        with quick2:
            if st.button(
                "show ip route",
                width="stretch",
                key="quick_routes",
            ):
                execute_cli(
                    selected_device,
                    "show ip route",
                )
                st.rerun()

        with quick3:
            if st.button(
                "show run",
                width="stretch",
                key="quick_run",
            ):
                execute_cli(
                    selected_device,
                    "show running-config",
                )
                st.rerun()

        with quick4:
            if st.button(
                "Clear Console",
                width="stretch",
                key="quick_clear",
            ):
                st.session_state.cli_history[selected_device] = [
                    "Welcome to PeerNet Network Simulator",
                    "",
                ]
                st.rerun()

        st.caption(
            "Click anywhere inside the black console, type the command, "
            "and press Enter. No separate CLI input box is used."
        )

    else:
        st.info(
            "Add a device first. The interactive console will appear here."
        )

with ai_tab:
    st.subheader("PeerNet AI Command Assistant")
    st.caption(
        "Ask for simulator-compatible configuration or troubleshooting "
        "commands. AI suggestions are never executed automatically."
    )

    if st.session_state.devices:
        ai_selected = st.session_state.selected_device
        if ai_selected not in st.session_state.devices:
            ai_selected = next(iter(st.session_state.devices))

        if st.session_state.ai_answer:
            st.markdown(st.session_state.ai_answer)

        if st.session_state.ai_commands:
            st.markdown("#### Copy commands to Console")
            st.code(
                "\n".join(st.session_state.ai_commands),
                language="text",
            )

        if st.session_state.ai_answer:
            st.markdown("---")
            st.markdown("#### Ask a follow-up question")

        ai_request = st.text_area(
            "What do you want to configure or troubleshoot?",
            key="ai_request",
            placeholder=(
                "Example: Configure OSPF area 0 on this router and provide "
                "verification commands"
            ),
            height=110,
        )

        generate_col, clear_ai_col, ai_action_space = st.columns(
            [1.25, .55, 6.2]
        )
        with generate_col:
            generate_ai = st.button(
                "Generate Commands",
                type="primary",
                width="content",
                key="generate_ai_commands",
            )
        with clear_ai_col:
            if st.button(
                "Clear",
                width="content",
                key="clear_ai_answer",
            ):
                st.session_state.ai_answer = ""
                st.session_state.ai_commands = []
                st.rerun()

        if generate_ai:
            if not ai_request.strip():
                st.warning("Enter a configuration or troubleshooting request.")
            else:
                try:
                    with st.spinner("PeerNet AI is preparing commands..."):
                        answer = generate_command_guidance(
                            ai_request,
                            st.session_state.devices,
                            st.session_state.links,
                            ai_selected,
                            previous_answer=st.session_state.ai_answer,
                        )
                    st.session_state.ai_answer = answer
                    st.session_state.ai_commands = extract_commands(answer)
                    st.rerun()
                except Exception as error:
                    st.error(f"Unable to generate commands: {error}")

    else:
        st.info("Add a device first so PeerNet AI can use its topology context.")

with ping_tab:
    if st.session_state.devices:
        source = st.selectbox(
            "Source device",
            list(st.session_state.devices),
            key="ping_source",
        )
        source_ips = []
        for interface in st.session_state.devices[source].interfaces.values():
            if not interface.ip_address:
                continue
            try:
                source_ips.append(
                    str(ipaddress.ip_interface(interface.ip_address).ip)
                )
            except ValueError:
                continue

        ping_source_col, ping_destination_col = st.columns(2)
        with ping_source_col:
            source_ip = st.selectbox(
                "Source IP",
                source_ips or ["Unassigned"],
                key="ping_source_ip",
            )
        with ping_destination_col:
            destination = st.text_input(
                "Destination IP",
                key="ping_destination",
                placeholder="192.168.1.10",
            )

        ping_run_col, ping_stop_col = st.columns(2)
        run_ping_clicked = ping_run_col.button(
            "Run Ping",
            key="run_ping",
            type="primary",
            width="stretch",
        )
        if ping_stop_col.button(
            "⏹ Stop Ping",
            key="stop_ping_animation",
            width="stretch",
        ):
            st.session_state.packet_animation = {}
            add_event("Ping animation stopped by user.")
            st.rerun()

        if run_ping_clicked:
            if source_ip == "Unassigned":
                st.session_state.ping_output = (
                    f"PING failed: {source} has no configured source IP."
                )
            elif destination.strip():
                record_packet_analysis(
                    source,
                    destination.strip(),
                    "Ping",
                    source_ip,
                )
                add_event(
                    f"Ping started: {source} ({source_ip}) → "
                    f"{destination.strip()}"
                )
            if source_ip == "Unassigned":
                pass
            elif not destination.strip():
                st.session_state.ping_output = (
                    "Please enter a destination IP address."
                )
            elif source in st.session_state.devices:
                route_result = evaluate_bidirectional_route(
                    source,
                    source_ip,
                    destination.strip(),
                    st.session_state.devices,
                    st.session_state.links,
                )
                if route_result.reachable:
                    start_packet_animation(route_result.path, "ICMP")
                    st.session_state.ping_output = (
                        f"PING {destination.strip()} from "
                        f"{source_ip} ({source})\n"
                        f"Route: {' → '.join(route_result.path)}\n"
                        f"Reply from {destination.strip()}: "
                        "bytes=32 time<1ms TTL=255\n"
                        f"Reply from {destination.strip()}: "
                        "bytes=32 time<1ms TTL=255\n\n"
                        "Success rate is 100 percent (2/2)"
                    )
                else:
                    st.session_state.packet_animation = {}
                    details = "\n".join(route_result.decisions)
                    st.session_state.ping_output = (
                        f"PING {destination.strip()} from "
                        f"{source_ip} ({source})\n"
                        "Request timed out.\nRequest timed out.\n\n"
                        "Success rate is 0 percent (0/2)\n"
                        f"Reason: {route_result.reason}"
                        + (f"\n{details}" if details else "")
                    )
                st.rerun()

        if st.session_state.get("ping_output"):
            ping_title_col, ping_clear_col = st.columns([4, 1])

            with ping_title_col:
                st.markdown("#### Ping Output")

            with ping_clear_col:
                if st.button(
                    "Clear Ping Output",
                    key="clear_ping_output",
                    width="stretch",
                ):
                    st.session_state.ping_output = ""
                    st.rerun()

            st.code(
                st.session_state.ping_output,
                language="text",
            )
    else:
        st.info("Add devices first.")

with trace_tab:
    if st.session_state.devices:
        source = st.selectbox(
            "Source device",
            list(st.session_state.devices),
            key="trace_source",
        )
        source_ips = []
        for interface in st.session_state.devices[source].interfaces.values():
            if not interface.ip_address:
                continue
            try:
                source_ips.append(
                    str(ipaddress.ip_interface(interface.ip_address).ip)
                )
            except ValueError:
                continue

        trace_source_col, trace_destination_col = st.columns(2)
        with trace_source_col:
            source_ip = st.selectbox(
                "Source IP",
                source_ips or ["Unassigned"],
                key="trace_source_ip",
            )
        with trace_destination_col:
            destination = st.text_input(
                "Destination IP",
                key="trace_destination",
                placeholder="192.168.1.10",
            )

        trace_run_col, trace_stop_col = st.columns(2)
        run_trace_clicked = trace_run_col.button(
            "Run Traceroute",
            key="run_trace",
            type="primary",
            width="stretch",
        )
        if trace_stop_col.button(
            "⏹ Stop Traceroute",
            key="stop_trace_animation",
            width="stretch",
        ):
            st.session_state.packet_animation = {}
            add_event("Traceroute animation stopped by user.")
            st.rerun()

        if run_trace_clicked:
            if source_ip == "Unassigned":
                st.session_state.traceroute_output = (
                    f"Traceroute failed: {source} has no configured source IP."
                )
            elif destination.strip():
                record_packet_analysis(
                    source,
                    destination.strip(),
                    "Traceroute",
                    source_ip,
                )
                add_event(
                    f"Traceroute started: {source} ({source_ip}) → "
                    f"{destination.strip()}"
                )
            if source_ip == "Unassigned":
                pass
            elif not destination.strip():
                st.session_state.traceroute_output = (
                    "Please enter a destination IP address."
                )
            else:
                route_result = evaluate_bidirectional_route(
                    source,
                    source_ip,
                    destination.strip(),
                    st.session_state.devices,
                    st.session_state.links,
                )
                lines = [
                    f"Tracing route from {source_ip} ({source}) to "
                    f"{destination.strip()}",
                    "",
                ]
                for hop_number, hop_name in enumerate(
                    route_result.path[1:], start=1
                ):
                    hop_ip = _first_device_ip(hop_name)
                    lines.append(
                        f"{hop_number:<3} <1 ms   {hop_name} ({hop_ip})"
                    )
                if route_result.reachable:
                    start_packet_animation(route_result.path, "ICMP Traceroute")
                    lines.extend(["", "Trace complete."])
                else:
                    st.session_state.packet_animation = {}
                    lines.extend(["", f"Trace failed: {route_result.reason}"])
                if route_result.decisions:
                    lines.extend(["", "Routing decisions:"])
                    lines.extend(
                        f"  {decision}" for decision in route_result.decisions
                    )
                st.session_state.traceroute_output = "\n".join(lines)
                st.rerun()

        if st.session_state.get("traceroute_output"):
            trace_title_col, trace_clear_col = st.columns([4, 1])

            with trace_title_col:
                st.markdown("#### Traceroute Output")

            with trace_clear_col:
                if st.button(
                    "Clear Traceroute Output",
                    key="clear_trace_output",
                    width="stretch",
                ):
                    st.session_state.traceroute_output = ""
                    st.rerun()

            st.code(
                st.session_state.traceroute_output,
                language="text",
            )
    else:
        st.info("Add devices first.")

with validation_tab:
    st.subheader("Configuration Validation")
    st.caption(
        "Checks duplicate IPs, gateways, masks, overlapping networks, "
        "VLAN references, and router subinterface encapsulation."
    )
    validation_link_states = [
        link_operational_status(link)[0]
        for link in st.session_state.links
    ]
    validation_up_links = validation_link_states.count("up")
    validation_down_links = len(validation_link_states) - validation_up_links
    st.markdown(
        f"""
        <div class="pn-validation-stats">
            <div class="pn-validation-stat devices">
                <span>Devices</span><strong>{len(st.session_state.devices)}</strong>
            </div>
            <div class="pn-validation-stat links">
                <span>Links</span><strong>{len(st.session_state.links)}</strong>
            </div>
            <div class="pn-validation-stat up">
                <span>Up</span><strong>{validation_up_links}</strong>
            </div>
            <div class="pn-validation-stat down">
                <span>Down</span><strong>{validation_down_links}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    validation_devices = list(st.session_state.devices)
    if not validation_devices:
        st.info("Add a device to the topology to run validation.")
    else:
        validation_device = st.selectbox(
            "Choose Device",
            validation_devices,
            key="validation_device_select",
        )
        issues, success_messages = audit_device(
            st.session_state.devices,
            st.session_state.links,
            validation_device,
        )
        error_count = sum(issue.severity == "error" for issue in issues)
        warning_count = sum(issue.severity == "warning" for issue in issues)
        st.write(
            f"Selected device: **{validation_device}** · "
            f"Errors: **{error_count}** · Warnings: **{warning_count}**"
        )
        for issue in issues:
            message = (
                f"{issue.device}:{issue.interface} — {issue.message}"
            )
            if issue.severity == "error":
                st.error(message)
            else:
                st.warning(message)
        for message in success_messages:
            st.success(message)

with packet_tab:
    packet_title_col, packet_clear_col = st.columns([4, 1])

    with packet_title_col:
        st.subheader("Packet Analysis")

    with packet_clear_col:
        if st.button(
            "Clear Packet Analysis",
            key="clear_packet_analysis",
            width="stretch",
        ):
            st.session_state.packet_analysis_output = []
            st.rerun()

    analysis = st.session_state.get(
        "packet_analysis_output",
        [],
    )

    if not analysis:
        st.info(
            "Run Ping or Traceroute to generate hop-by-hop "
            "packet analysis."
        )
    else:
        path_text = "  →  ".join(
            item["device"] for item in analysis
        )
        st.success(f"Packet flow: {path_text}")

        for item in analysis:
            with st.expander(
                f"Packet {item['packet_no']} · "
                f"Hop {item['hop']} · {item['device']}",
                expanded=True,
            ):
                st.write(f"**Layer 2:** {item['layer_2']}")
                st.write(f"**Layer 3:** {item['layer_3']}")
                st.write(f"**Layer 4:** {item['layer_4']}")
                st.write(
                    f"**Forwarding decision:** "
                    f"{item['decision']}"
                )

with wireshark_tab:
    ws_title_col, ws_clear_col = st.columns([4, 1])

    with ws_title_col:
        st.subheader("Wireshark")

    with ws_clear_col:
        if st.button(
            "Clear Capture",
            key="clear_capture",
            width="stretch",
        ):
            st.session_state.packet_records = []
            st.session_state.last_capture_path = ""
            st.rerun()

    records = st.session_state.get("packet_records", [])

    if not records:
        st.info(
            "Run Ping or Traceroute first. The simulated "
            "packet capture will appear here."
        )
    else:
        st.caption(f"Captured packets: {len(records)}")

        for record in records[-25:]:
            elapsed = record["time"] - records[0]["time"]

            st.code(
                f"No. {record['no']}  "
                f"Time {elapsed:.6f}  "
                f"{record['source_ip']} → "
                f"{record['destination_ip']}  "
                f"{record['protocol']}  "
                f"Len={record['length']}\n"
                f"{record['info']}",
                language="text",
            )

        capture_path = build_pcap()

        if capture_path and capture_path.exists():
            st.download_button(
                "Download PCAP",
                data=capture_path.read_bytes(),
                file_name="peernet_capture.pcap",
                mime="application/vnd.tcpdump.pcap",
                width="stretch",
                key="download_capture",
            )

            if st.button(
                "Open in Wireshark (Local)",
                type="primary",
                width="stretch",
                key="open_capture_wireshark",
            ):
                ok, message = launch_wireshark(capture_path)

                if ok:
                    st.success(message)
                else:
                    st.error(message)

            st.caption(
                "Open in Wireshark works when this Streamlit "
                "app is running locally on the same Windows "
                "computer where Wireshark is installed. "
                "For Streamlit Cloud, download the PCAP and "
                "open it locally."
            )

if (
    st.session_state.dialog_mode == "pc_config"
    and st.session_state.dialog_device in st.session_state.devices
):
    pc_config_dialog(st.session_state.dialog_device)

if (
    st.session_state.dialog_mode == "add_interface"
    and st.session_state.dialog_device in st.session_state.devices
):
    add_interface_dialog(st.session_state.dialog_device)

if (
    st.session_state.dialog_mode == "interfaces"
    and st.session_state.dialog_device in st.session_state.devices
):
    interfaces_dialog(st.session_state.dialog_device)

if (
    st.session_state.dialog_mode == "disconnect_link"
    and st.session_state.dialog_device in st.session_state.devices
):
    disconnect_link_dialog(st.session_state.dialog_device)
