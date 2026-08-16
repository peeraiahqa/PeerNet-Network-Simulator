from __future__ import annotations

import base64
import html
import ipaddress
import shutil
import struct
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Optional

import streamlit as st
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


@dataclass
class Device:
    name: str
    device_type: str
    interfaces: Dict[str, Interface] = field(default_factory=dict)
    routing_table: Dict[str, str] = field(default_factory=dict)
    default_gateway: str = ""
    dns_server: str = ""


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
        "Fa0/1", "Fa0/2", "Fa0/3", "Fa0/4",
        "Fa0/5", "Fa0/6", "Fa0/7", "Fa0/8"
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
            font-size:1.15rem;
        }

        .pn-subtitle {
            color:#64748b;
            font-size:.7rem;
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

[class*="st-key-run_ping"] button {
    background: linear-gradient(135deg,#2563eb,#3b82f6) !important;
    color:#ffffff !important;
    border:0 !important;
}

[class*="st-key-run_trace"] button {
    background: linear-gradient(135deg,#7c3aed,#9333ea) !important;
    color:#ffffff !important;
    border:0 !important;
}


/* =========================================================
   LOGIN PAGE ONLY
   ========================================================= */

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
    margin:0 auto .9rem;
    text-align:center;
    color:#64748b;
    font-size:.98rem;
    font-weight:700;
    letter-spacing:.025em;
}

.pn-auth-side-caption {
    margin:.4rem 0 0;
    text-align:center;
    color:#64748b;
    font-size:.72rem;
}

/* Boxed auth container generated by st.container(border=True). */
[class*="st-key-peernet_auth_box"] {
    padding:.5rem .65rem .75rem !important;
    border:1px solid #dbe5f2 !important;
    border-radius:18px !important;
    background:rgba(255,255,255,.97) !important;
    box-shadow:0 14px 34px rgba(37,99,235,.10) !important;
}

/* Keep inputs soft and modern only inside login box. */
[class*="st-key-peernet_auth_box"] input {
    border-radius:10px !important;
}

[class*="st-key-peernet_auth_box"] [data-testid="stForm"] {
    border:0 !important;
    padding:.25rem 0 !important;
}

/* Login-only spacing on smaller screens. */
@media(max-width:900px) {
    .pn-auth-logo img {
        width:175px;
    }

    .pn-auth-title {
        font-size:2rem;
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
        "cli_history": {},
        "booted": set(),
        "selected_device": None,
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
        "events_log": [],
        "last_capture_path": "",
        "connect_source": None,
        "connect_target": None,
        "connector_type": "Ethernet / Copper",
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

    count = len(st.session_state.devices)
    st.session_state.positions[name] = position or {
        "x": 150 + ((count - 1) % 4) * 190,
        "y": 135 + ((count - 1) // 4) * 145,
    }

    st.session_state.cli_modes[name] = "user"
    st.session_state.cli_history[name] = []
    st.session_state.selected_device = name
    return name


CONNECTOR_TYPES = {
    "Ethernet / Copper": "wired",
    "Fiber / Optical": "optical",
    "Serial": "serial",
    "Wireless": "wireless",
}


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

    return (
        True,
        f"Connected {source}:{source_if} ↔ "
        f"{target}:{target_if} using {connector_type}.",
    )


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

    return f"{name}>"


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
    rows = ["Codes: C - connected, S - static", ""]

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
        rows.append(f"S    {network} [1/0] via {next_hop}")

    return "\n".join(rows)


def running_config(device: Device) -> str:
    rows = [f"hostname {device.name}", "!"]

    for interface in device.interfaces.values():
        rows.extend(
            [
                f"interface {interface.name}",
                f" ip address {interface.ip_address or 'unassigned'}",
                f" {'no shutdown' if interface.status == 'up' else 'shutdown'}",
                "!",
            ]
        )

    for network, next_hop in device.routing_table.items():
        rows.append(f"ip route {network} {next_hop}")

    return "\n".join(rows)



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

    ports = ", ".join(
        interface.name
        for interface in device.interfaces.values()
        if not interface.name.lower().startswith("vlan")
    ) or "none"

    return (
        "VLAN Name                             Status    Ports\n"
        "---- -------------------------------- --------- -------------------------------\n"
        f"1    default                          active    {ports}\n"
        "1002 fddi-default                     act/unsup\n"
        "1003 token-ring-default               act/unsup"
    )


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
            lines.append(
                f"1       {mac}    DYNAMIC     {interface.name}"
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
        "interfaces          Interface information",
        "ip                  IP information",
        "running-config      Current operating configuration",
        "startup-config      Saved configuration",
        "version             System hardware and software status",
    ]

    if device.device_type in {"Switch", "Multilayer Switch"}:
        common.extend(
            [
                "interfaces status   Interface switchport status",
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
        "show ?",
        "show arp",
        "show cdp neighbors",
        "show interfaces",
        "show ip ?",
        "show ip interface brief",
        "show ip route",
        "show running-config",
        "show startup-config",
        "show version",
    ]

    if device.device_type in {"Switch", "Multilayer Switch"}:
        commands.extend(
            [
                "show interfaces status",
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
                "interface ",
                "ip route ",
                "end",
            ]
        )

    if mode == "interface":
        commands.extend(
            [
                "ip address ",
                "shutdown",
                "no shutdown",
                "exit",
                "end",
            ]
        )

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

        return [
            f"interface {interface_name}"
            for interface_name in device.interfaces
            if interface_name.startswith(typed_interface)
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

    if old_name in st.session_state.cli_history:
        st.session_state.cli_history[new_name] = st.session_state.cli_history.pop(old_name)

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


def resolve_interface_case_sensitive(device: Device, requested: str) -> Optional[str]:
    if requested in device.interfaces:
        return requested
    return None

PC_DEVICE_TYPES = {
    "PC",
    "Laptop",
    "Server",
    "Authentication Server",
    "Camera / PC Video",
}


def primary_pc_interface(device: Device) -> Optional[Interface]:
    preferred = ("eth0", "Ethernet0", "Gi0/0", "wlan0")
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

    interface.ip_address = str(ip_iface)
    interface.status = "up"
    device.default_gateway = gateway

    return True, "IP configuration applied successfully."


def pc_ping_result(
    source_name: str,
    destination_ip: str,
) -> str:
    try:
        destination = ipaddress.ip_address(destination_ip)
    except ValueError:
        return f"Ping request could not find host {destination_ip}."

    source_device = st.session_state.devices[source_name]
    source_if = primary_pc_interface(source_device)

    if not source_if or not source_if.ip_address:
        return "PING failed: source PC has no IP address."

    # Logical reachability check:
    # 1) destination belongs to any configured interface in topology
    # 2) same subnet, or PC has a default gateway configured
    destination_owner = None
    destination_interface = None

    for device_name, device in st.session_state.devices.items():
        for interface in device.interfaces.values():
            if not interface.ip_address:
                continue
            try:
                configured_ip = ipaddress.ip_interface(
                    interface.ip_address
                ).ip
            except ValueError:
                continue

            if configured_ip == destination:
                destination_owner = device_name
                destination_interface = interface
                break

        if destination_owner:
            break

    if not destination_owner:
        return (
            f"Pinging {destination_ip} with 32 bytes of data:\n"
            "Request timed out.\n"
            "Request timed out.\n\n"
            "Packets: Sent = 2, Received = 0, Lost = 2 (100% loss)"
        )

    try:
        source_network = ipaddress.ip_interface(
            source_if.ip_address
        ).network
        same_subnet = destination in source_network
    except ValueError:
        same_subnet = False

    reachable = same_subnet or bool(source_device.default_gateway)

    if reachable:
        return (
            f"Pinging {destination_ip} with 32 bytes of data:\n"
            f"Reply from {destination_ip}: bytes=32 time<1ms TTL=128\n"
            f"Reply from {destination_ip}: bytes=32 time<1ms TTL=128\n\n"
            "Packets: Sent = 2, Received = 2, Lost = 0 (0% loss)"
        )

    return (
        f"Pinging {destination_ip} with 32 bytes of data:\n"
        "Destination host unreachable.\n\n"
        "Packets: Sent = 1, Received = 0, Lost = 1 (100% loss)"
    )


def pc_help() -> str:
    return (
        "ip <address> <mask> [gateway]    Configure static IPv4\n"
        "ipconfig                         Show IP configuration\n"
        "ipconfig /all                    Show detailed IP configuration\n"
        "gateway <ip>                     Set default gateway\n"
        "dns <ip>                         Set DNS server\n"
        "ping <ip>                        Test logical connectivity\n"
        "tracert <ip>                     Trace logical path\n"
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
            device.default_gateway = value
            append_cli(name, f"Default gateway set to {value}.")
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
        destination = stripped.split(maxsplit=1)[1].strip()
        append_cli(
            name,
            pc_ping_result(name, destination),
        )
        return True

    if lowered.startswith("tracert "):
        destination = stripped.split(maxsplit=1)[1].strip()
        append_cli(
            name,
            f"Tracing route to {destination}\n"
            f"  1    <1 ms    {device.default_gateway or destination}\n"
            f"Trace complete.",
        )
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

def execute_cli(name: str, command: str) -> None:
    command = command.strip()
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

    if lowered.startswith("interface "):
        if mode not in {"config", "interface"}:
            append_cli(name, "% Enter global configuration mode first.")
            return

        # Cisco command keyword is case-insensitive, but the simulator keeps
        # interface identifiers exact/case-sensitive by design.
        interface_name = command.split(maxsplit=1)[1].strip()
        exact_interface = resolve_interface_case_sensitive(
            device,
            interface_name,
        )

        if exact_interface is None:
            case_match = next(
                (
                    existing
                    for existing in device.interfaces
                    if existing.lower() == interface_name.lower()
                ),
                None,
            )

            if case_match:
                append_cli(
                    name,
                    f"% Invalid interface case '{interface_name}'. "
                    f"Use exact interface name: {case_match}",
                )
            else:
                append_cli(
                    name,
                    f"% Invalid interface '{interface_name}'.\n"
                    f"Available interfaces: "
                    f"{', '.join(device.interfaces.keys())}",
                )
            return

        st.session_state.cli_modes[name] = "interface"
        st.session_state.cli_interfaces[name] = exact_interface
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
        device.interfaces[interface_name].ip_address = cidr
        return

    if lowered in {"shutdown", "shut"}:
        if mode == "interface":
            device.interfaces[
                st.session_state.cli_interfaces[name]
            ].status = "down"
        return

    if lowered in {"no shutdown", "no shut"}:
        if mode == "interface":
            device.interfaces[
                st.session_state.cli_interfaces[name]
            ].status = "up"
        return

    if lowered == "exit":
        if mode == "interface":
            st.session_state.cli_modes[name] = "config"
            st.session_state.cli_interfaces.pop(name, None)
        elif mode == "config":
            st.session_state.cli_modes[name] = "privileged"
        elif mode == "privileged":
            st.session_state.cli_modes[name] = "user"
        return

    if lowered == "end":
        st.session_state.cli_modes[name] = "privileged"
        st.session_state.cli_interfaces.pop(name, None)
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

    if lowered == "show interfaces status":
        append_cli(name, show_interfaces_status(device))
        return

    if lowered == "show ip route":
        append_cli(name, show_ip_route(device))
        return

    if lowered in {"show running-config", "show run"}:
        append_cli(name, running_config(device))
        return

    if lowered == "show startup-config":
        append_cli(name, running_config(device))
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
) -> None:
    destination_device = _device_for_ip(destination_ip)
    path = (
        _topology_path(source, destination_device)
        if destination_device
        else [source]
    )

    if not path:
        path = [source]

    source_ip = _first_device_ip(source)
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
        )

        for if_name, raw_if in (raw.get("interfaces") or {}).items():
            device.interfaces[if_name] = Interface(
                name=if_name,
                ip_address=raw_if.get("ip_address", ""),
                status=raw_if.get("status", "up"),
                connected_to=raw_if.get("connected_to"),
            )

        devices[name] = device

    st.session_state.devices = devices
    st.session_state.links = payload.get("links", []) or []
    st.session_state.positions = payload.get("positions", {}) or {}
    st.session_state.cli_modes = {name: "user" for name in devices}
    st.session_state.cli_interfaces = {}
    st.session_state.cli_history = {name: [] for name in devices}
    st.session_state.booted = set()
    st.session_state.selected_device = (
        next(iter(devices)) if devices else None
    )



def delete_device(device_name: str) -> None:
    if device_name not in st.session_state.devices:
        return

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
    st.session_state.cli_history.pop(device_name, None)

    if device_name in st.session_state.booted:
        st.session_state.booted.remove(device_name)

    if st.session_state.selected_device == device_name:
        st.session_state.selected_device = (
            next(iter(st.session_state.devices), None)
        )

    st.session_state.dialog_mode = None
    st.session_state.dialog_device = None

def clear_topology() -> None:
    st.session_state.devices = {}
    st.session_state.links = []
    st.session_state.positions = {}
    st.session_state.cli_modes = {}
    st.session_state.cli_interfaces = {}
    st.session_state.cli_history = {}
    st.session_state.booted = set()
    st.session_state.selected_device = None


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
                interface_labels.append(
                    {
                        "name": interface.name,
                        "ip": interface.ip_address.split("/")[0] if interface.ip_address else "unassigned",
                        "connected": bool(interface.connected_to),
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
    return [
        {
            "id": item["id"],
            "source": item["source"],
            "target": item["target"],
            "source_if": item.get("source_if", ""),
            "target_if": item.get("target_if", ""),
            "connector_type": item.get(
                "connector_type",
                "Ethernet / Copper",
            ),
        }
        for item in st.session_state.links
    ]


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

    elif action in {
        "configure",
        "open_console",
        "interfaces",
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
            use_container_width=True,
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
                use_container_width=True,
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
        use_container_width=True,
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


def auth_page() -> None:
    logo64 = base64.b64encode(LOGO.read_bytes()).decode()

    # Keep the original two-column login layout so the side illustration
    # remains present. Only the login-side presentation is redesigned.
    form_col, art_col = st.columns([1.02, 1.18], gap="large")

    with form_col:
        st.markdown(
            f"""
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
            """,
            unsafe_allow_html=True,
        )

        with st.container(
            border=True,
            key="peernet_auth_box",
        ):
            login_tab, signup_tab, reset_tab = st.tabs(
                ["Login", "Create account", "Forgot password"]
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
                        use_container_width=True,
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
                    submitted = st.form_submit_button(
                        "Create account",
                        use_container_width=True,
                    )

                if submitted:
                    try:
                        sign_up(email, password, full_name, "")
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
                    use_container_width=True,
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
        st.image(
            LOGIN_ART,
            use_container_width=True,
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

    selected_project = st.selectbox(
        "Select Project",
        ["＋ New Project"] + list(project_map),
        key="project_select",
    )

    project_name = st.text_input(
        "Project name",
        value=st.session_state.current_project_name,
        key="project_name",
    )

    if st.button(
        "＋ Create Project",
        use_container_width=True,
        key="project_create",
    ):
        clear_topology()
        st.session_state.current_project_id = None
        st.session_state.current_project_name = (
            project_name or "Untitled topology"
        )
        st.rerun()

    if st.button(
        "💾 Save Project",
        use_container_width=True,
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

    open_col, delete_col = st.columns(2)

    with open_col:
        if st.button(
            "📂 Open",
            use_container_width=True,
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
                st.rerun()
            except Exception as error:
                st.error(f"Unable to open project: {error}")

    with delete_col:
        if st.button(
            "🗑 Delete",
            use_container_width=True,
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
        use_container_width=True,
        key="device_add",
    ):
        add_device(device_type)
        st.rerun()

    demo_col, reset_col = st.columns(2)

    with demo_col:
        if st.button(
            "Demo",
            use_container_width=True,
            key="load_demo",
        ):
            load_demo()
            st.rerun()

    with reset_col:
        if st.button(
            "Reset",
            use_container_width=True,
            key="reset_topology",
        ):
            clear_topology()
            st.rerun()

    with st.container(key="logout_btn"):
        if st.button(
            "↪ Logout",
            use_container_width=True,
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
    tool_cols = st.columns(5)

    with tool_cols[0]:
        st.button(
            "↖ Select",
            use_container_width=True,
            key="tool_select",
        )
    with tool_cols[1]:
        if st.button(
            "🔗 Connect",
            use_container_width=True,
            key="tool_connect",
        ):
            if st.session_state.selected_device:
                st.session_state.connect_source = (
                    st.session_state.selected_device
                )
            st.rerun()
    with tool_cols[2]:
        st.button(
            "✥ Move",
            use_container_width=True,
            key="tool_move",
        )
    with tool_cols[3]:
        if st.button(
            "🗑 Delete",
            use_container_width=True,
            key="tool_delete",
        ):
            selected = st.session_state.selected_device

            if selected in st.session_state.devices:
                del st.session_state.devices[selected]
                st.session_state.positions.pop(selected, None)
                st.session_state.links = [
                    link
                    for link in st.session_state.links
                    if selected
                    not in {link["source"], link["target"]}
                ]
                st.session_state.selected_device = None
                st.rerun()

    with tool_cols[4]:
        st.button(
            "⛶ Full",
            use_container_width=True,
            key="tool_fullscreen",
            help="Use your browser full-screen mode for the largest workspace.",
        )

canvas_col, right_col = st.columns([4.8, 1.15], gap="small")

with canvas_col:
    st.markdown(
        '<div class="pn-canvas-card">',
        unsafe_allow_html=True,
    )

    event = topology_canvas(
        node_payload(),
        edge_payload(),
        height=520,
        key="topology_canvas",
    )
    handle_canvas_event(event)

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )

with right_col:
    st.markdown(
        '<div class="pn-right-card">',
        unsafe_allow_html=True,
    )

    connect_tab, device_tab, end_tab, port_tab = st.tabs(
        ["Connect", "Devices", "End Users", "Ports"]
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

            if source_if and target_if:
                st.caption(
                    f"{source}:{source_if}  ↔  "
                    f"{target}:{target_if}"
                )

                if st.button(
                    "🔌 Connect Interfaces",
                    use_container_width=True,
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

    with device_tab:
        for item in DEVICE_GROUPS["Network Devices"]:
            if st.button(
                item,
                use_container_width=True,
                key=f"right_add_{item}",
            ):
                add_device(item)
                st.rerun()

    with end_tab:
        for item in DEVICE_GROUPS["End Users"]:
            if st.button(
                item,
                use_container_width=True,
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
                use_container_width=True,
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


    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )


# Single interactive console plus network tools.
console_tab, ping_tab, trace_tab, packet_tab, wireshark_tab, events_tab = st.tabs(
    [
        "Console",
        "Ping",
        "Traceroute",
        "Packet Analysis",
        "Wireshark",
        "Events",
    ]
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

        terminal_event = inline_terminal(
            history=terminal_history,
            prompt=prompt(selected_device),
            device_name=selected_device,
            prefill=st.session_state.get("terminal_prefill", ""),
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
                execute_cli(
                    selected_device,
                    terminal_event.get("command", ""),
                )
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

                st.rerun()

        quick1, quick2, quick3, quick4 = st.columns(4)

        with quick1:
            if st.button(
                "show ip int brief",
                use_container_width=True,
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
                use_container_width=True,
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
                use_container_width=True,
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
                use_container_width=True,
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

with ping_tab:
    if st.session_state.devices:
        source = st.selectbox(
            "Source device",
            list(st.session_state.devices),
            key="ping_source",
        )
        destination = st.text_input(
            "Destination IP",
            key="ping_destination",
            placeholder="192.168.1.10",
        )

        if st.button(
            "Run Ping",
            key="run_ping",
            type="primary",
        ):
            if destination.strip():
                record_packet_analysis(
                    source,
                    destination.strip(),
                    "Ping",
                )
                add_event(
                    f"Ping started: {source} → {destination.strip()}"
                )
            if not destination.strip():
                st.session_state.ping_output = (
                    "Please enter a destination IP address."
                )
            elif source in st.session_state.devices:
                source_device = st.session_state.devices[source]

                if source_device.device_type in PC_DEVICE_TYPES:
                    st.session_state.ping_output = pc_ping_result(
                        source,
                        destination.strip(),
                    )
                else:
                    try:
                        target_ip = ipaddress.ip_address(
                            destination.strip()
                        )
                        found = False

                        for device in st.session_state.devices.values():
                            for interface in device.interfaces.values():
                                if not interface.ip_address:
                                    continue

                                try:
                                    configured_ip = ipaddress.ip_interface(
                                        interface.ip_address
                                    ).ip
                                except ValueError:
                                    continue

                                if configured_ip == target_ip:
                                    found = True
                                    break

                            if found:
                                break

                        if found:
                            st.session_state.ping_output = (
                                f"PING {destination.strip()} from {source}\n"
                                f"Reply from {destination.strip()}: "
                                "bytes=32 time<1ms TTL=255\n"
                                f"Reply from {destination.strip()}: "
                                "bytes=32 time<1ms TTL=255\n\n"
                                "Success rate is 100 percent (2/2)"
                            )
                        else:
                            st.session_state.ping_output = (
                                f"PING {destination.strip()} from {source}\n"
                                "Request timed out.\n"
                                "Request timed out.\n\n"
                                "Success rate is 0 percent (0/2)"
                            )

                    except ValueError:
                        st.session_state.ping_output = (
                            f"Invalid destination IP: "
                            f"{destination.strip()}"
                        )

        if st.session_state.get("ping_output"):
            ping_title_col, ping_clear_col = st.columns([4, 1])

            with ping_title_col:
                st.markdown("#### Ping Output")

            with ping_clear_col:
                if st.button(
                    "Clear Ping Output",
                    key="clear_ping_output",
                    use_container_width=True,
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
        destination = st.text_input(
            "Destination IP",
            key="trace_destination",
            placeholder="192.168.1.10",
        )

        if st.button(
            "Run Traceroute",
            key="run_trace",
            type="primary",
        ):
            if destination.strip():
                record_packet_analysis(
                    source,
                    destination.strip(),
                    "Traceroute",
                )
                add_event(
                    f"Traceroute started: {source} → {destination.strip()}"
                )
            if not destination.strip():
                st.session_state.traceroute_output = (
                    "Please enter a destination IP address."
                )
            else:
                try:
                    target_ip = ipaddress.ip_address(
                        destination.strip()
                    )

                    destination_device = None

                    for device_name, device in (
                        st.session_state.devices.items()
                    ):
                        for interface in device.interfaces.values():
                            if not interface.ip_address:
                                continue

                            try:
                                configured_ip = ipaddress.ip_interface(
                                    interface.ip_address
                                ).ip
                            except ValueError:
                                continue

                            if configured_ip == target_ip:
                                destination_device = device_name
                                break

                        if destination_device:
                            break

                    if destination_device is None:
                        st.session_state.traceroute_output = (
                            f"Tracing route from {source} to "
                            f"{destination.strip()}\n"
                            "Destination not found in the current topology."
                        )
                    else:
                        adjacency = {
                            name: []
                            for name in st.session_state.devices
                        }

                        for link in st.session_state.links:
                            src = link.get("source")
                            dst = link.get("target")

                            if src in adjacency and dst in adjacency:
                                adjacency[src].append(dst)
                                adjacency[dst].append(src)

                        queue = [(source, [source])]
                        visited = {source}
                        route = None

                        while queue:
                            current, path = queue.pop(0)

                            if current == destination_device:
                                route = path
                                break

                            for neighbor in adjacency.get(current, []):
                                if neighbor not in visited:
                                    visited.add(neighbor)
                                    queue.append(
                                        (
                                            neighbor,
                                            path + [neighbor],
                                        )
                                    )

                        if route:
                            lines = [
                                f"Tracing route from {source} to "
                                f"{destination.strip()}",
                                "",
                            ]

                            for hop_number, hop_name in enumerate(
                                route[1:],
                                start=1,
                            ):
                                hop_ip = "unassigned"

                                for interface in (
                                    st.session_state.devices[
                                        hop_name
                                    ].interfaces.values()
                                ):
                                    if interface.ip_address:
                                        hop_ip = (
                                            interface.ip_address
                                            .split("/")[0]
                                        )
                                        break

                                lines.append(
                                    f"{hop_number:<3} <1 ms   "
                                    f"{hop_name} ({hop_ip})"
                                )

                            lines.extend(["", "Trace complete."])
                            st.session_state.traceroute_output = (
                                "\n".join(lines)
                            )
                        else:
                            st.session_state.traceroute_output = (
                                f"Tracing route from {source} to "
                                f"{destination.strip()}\n"
                                "No logical path found in the current topology."
                            )

                except ValueError:
                    st.session_state.traceroute_output = (
                        f"Invalid destination IP: "
                        f"{destination.strip()}"
                    )

        if st.session_state.get("traceroute_output"):
            trace_title_col, trace_clear_col = st.columns([4, 1])

            with trace_title_col:
                st.markdown("#### Traceroute Output")

            with trace_clear_col:
                if st.button(
                    "Clear Traceroute Output",
                    key="clear_trace_output",
                    use_container_width=True,
                ):
                    st.session_state.traceroute_output = ""
                    st.rerun()

            st.code(
                st.session_state.traceroute_output,
                language="text",
            )
    else:
        st.info("Add devices first.")

with packet_tab:
    packet_title_col, packet_clear_col = st.columns([4, 1])

    with packet_title_col:
        st.subheader("Packet Analysis")

    with packet_clear_col:
        if st.button(
            "Clear Packet Analysis",
            key="clear_packet_analysis",
            use_container_width=True,
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
            use_container_width=True,
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
                use_container_width=True,
                key="download_capture",
            )

            if st.button(
                "Open in Wireshark (Local)",
                type="primary",
                use_container_width=True,
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

with events_tab:
    events_title_col, events_clear_col = st.columns([4, 1])

    with events_title_col:
        st.subheader("Events")

    with events_clear_col:
        if st.button(
            "Clear Events",
            key="clear_events",
            use_container_width=True,
        ):
            st.session_state.events_log = []
            st.rerun()

    st.write(f"Devices: {len(st.session_state.devices)}")
    st.write(f"Links: {len(st.session_state.links)}")
    st.write(
        f"Selected device: "
        f"{st.session_state.selected_device or 'None'}"
    )

    if st.session_state.get("events_log"):
        st.markdown("#### Event Log")

        for event in reversed(
            st.session_state.events_log[-50:]
        ):
            st.code(
                f"[{event['time']}] {event['message']}",
                language="text",
            )
    else:
        st.info("No events recorded yet.")


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
