from __future__ import annotations

import ipaddress
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from supabase_service import (
    create_simulator_project,
    delete_simulator_project,
    list_simulator_projects,
    load_simulator_project,
    send_password_reset,
    sign_in,
    sign_out,
    sign_up,
    update_simulator_project,
)


APP_DIR = Path(__file__).resolve().parent
FAVICON = APP_DIR / "assets" / "favicon.png"
COMPANY_LOGO = APP_DIR / "assets" / "peernet-solutions-logo.png"
LOGIN_ILLUSTRATION = APP_DIR / "assets" / "network-lab-illustration.jpg"

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
    description: str = ""


ICONS = {
    "Router": "🛰️",
    "Switch": "🔀",
    "PC": "💻",
    "Firewall": "🛡️",
    "Cloud": "☁️",
    "Server": "🖥️",
}

COLORS = {
    "Router": "#2563EB",
    "Switch": "#06B6D4",
    "PC": "#7C3AED",
    "Firewall": "#EF4444",
    "Cloud": "#64748B",
    "Server": "#16A34A",
}


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --pn-blue:#2563eb;
            --pn-navy:#08244e;
            --pn-purple:#7c3aed;
            --pn-line:rgba(37,99,235,.14);
            --pn-muted:#64748b;
        }

        .stApp {
            background:
                radial-gradient(circle at 92% 0%,rgba(124,58,237,.10),transparent 26%),
                linear-gradient(180deg,#fbfdff 0%,#f2f7ff 100%);
        }

        .block-container {
            max-width:1550px;
            padding-top:1rem;
            padding-bottom:2rem;
        }

        [data-testid="stSidebar"] {
            background:
                radial-gradient(circle at 20% 0%,rgba(37,99,235,.12),transparent 28%),
                linear-gradient(180deg,#f8fbff,#ffffff);
            border-right:1px solid var(--pn-line);
        }

        .pn-head {
            display:flex;
            justify-content:space-between;
            align-items:center;
            gap:1rem;
            padding:1.2rem 1.4rem;
            margin-bottom:1rem;
            border-radius:24px;
            color:#fff;
            background:
                radial-gradient(circle at 82% 30%,rgba(6,182,212,.30),transparent 25%),
                linear-gradient(120deg,#08244e,#1d4ed8 55%,#7c3aed);
            box-shadow:0 18px 45px rgba(31,72,145,.18);
        }

        .pn-head h1 {
            margin:0;
            font-size:clamp(1.8rem,4vw,3rem);
        }

        .pn-head p {
            margin:.35rem 0 0;
            color:#dbeafe;
        }

        .pn-badge {
            padding:.55rem .85rem;
            border:1px solid rgba(255,255,255,.24);
            border-radius:999px;
            background:rgba(255,255,255,.14);
            font-weight:800;
            white-space:nowrap;
        }

        .pn-device-card {
            min-height:145px;
            padding:.9rem;
            border:1px solid var(--pn-line);
            border-radius:18px;
            background:#fff;
            box-shadow:0 10px 24px rgba(31,72,145,.07);
            text-align:center;
            transition:.18s ease;
        }

        .pn-device-card:hover {
            transform:translateY(-3px);
            box-shadow:0 15px 30px rgba(31,72,145,.13);
        }

        .pn-device-card .icon {
            font-size:2rem;
        }

        .pn-device-card strong {
            display:block;
            margin-top:.35rem;
            color:#102348;
        }

        .pn-device-card small {
            color:var(--pn-muted);
        }

        [class*="st-key-device_open_"] button {
            margin-top:-3.3rem !important;
            min-height:145px !important;
            border:0 !important;
            color:transparent !important;
            background:transparent !important;
            box-shadow:none !important;
        }

        [class*="st-key-device_open_"] button:hover {
            background:rgba(37,99,235,.04) !important;
        }

        .pn-console {
            min-height:350px;
            padding:1rem;
            border-radius:16px;
            color:#b9f6ca;
            background:#06101d;
            box-shadow:inset 0 0 0 1px rgba(96,165,250,.15);
            font-family:Consolas,"Courier New",monospace;
            font-size:.84rem;
            white-space:pre-wrap;
            overflow:auto;
        }

        .pn-device-title {
            display:flex;
            align-items:center;
            gap:.7rem;
            padding:.75rem 1rem;
            margin-bottom:.8rem;
            border-radius:16px;
            background:linear-gradient(90deg,#eaf3ff,#f3edff);
        }

        .pn-device-title span {
            font-size:1.8rem;
        }

        div[data-testid="stMetric"] {
            border:1px solid var(--pn-line);
            border-radius:18px;
            padding:.8rem 1rem;
            background:#fff;
            box-shadow:0 9px 24px rgba(31,72,145,.06);
        }

        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button {
            border-radius:12px;
            font-weight:750;
        }

        @media(max-width:700px) {
            .block-container {
                padding-left:.55rem;
                padding-right:.55rem;
            }

            .pn-head {
                flex-direction:column;
                align-items:flex-start;
            }

            .pn-badge {
                font-size:.72rem;
            }

            .pn-device-card {
                min-height:125px;
            }

            [class*="st-key-device_open_"] button {
                min-height:125px !important;
                margin-top:-3rem !important;
            }
        }


        /* =========================================================
           COLORFUL PEERNET LOGIN
           ========================================================= */
        .pn-login-shell {
            position:relative;
            overflow:hidden;
            margin:-.2rem 0 1.15rem;
            padding:1.5rem 1.1rem 1.2rem;
            border-radius:30px;
            background:
                radial-gradient(circle at 8% 14%,rgba(34,211,238,.24),transparent 22%),
                radial-gradient(circle at 92% 10%,rgba(244,114,182,.24),transparent 24%),
                radial-gradient(circle at 80% 90%,rgba(124,58,237,.20),transparent 28%),
                linear-gradient(130deg,#f7fbff 0%,#edf5ff 38%,#f3edff 72%,#fff1f7 100%);
            box-shadow:
                0 24px 70px rgba(42,78,145,.14),
                inset 0 1px 0 rgba(255,255,255,.9);
        }

        .pn-login-shell::before,
        .pn-login-shell::after {
            content:"";
            position:absolute;
            border-radius:50%;
            pointer-events:none;
            filter:blur(1px);
        }

        .pn-login-shell::before {
            width:190px;
            height:190px;
            left:-65px;
            bottom:-80px;
            background:linear-gradient(145deg,rgba(14,165,233,.18),rgba(99,102,241,.08));
        }

        .pn-login-shell::after {
            width:230px;
            height:230px;
            right:-90px;
            top:-95px;
            background:linear-gradient(145deg,rgba(236,72,153,.15),rgba(124,58,237,.10));
        }

        .pn-login-head {
            position:relative;
            z-index:2;
            max-width:900px;
            margin:.1rem auto 1.15rem;
            text-align:center;
        }

        .pn-login-eyebrow {
            display:inline-flex;
            align-items:center;
            gap:.4rem;
            padding:.42rem .78rem;
            border:1px solid rgba(99,102,241,.15);
            border-radius:999px;
            color:#4f46e5;
            background:rgba(255,255,255,.72);
            box-shadow:0 7px 18px rgba(79,70,229,.08);
            font-size:.72rem;
            font-weight:900;
            letter-spacing:.04em;
        }

        .pn-login-head h1 {
            margin:.65rem 0 0;
            color:#08244e;
            font-size:clamp(2.15rem,4.4vw,3.55rem);
            line-height:1.02;
            letter-spacing:-.045em;
            font-weight:950;
        }

        .pn-login-head h1 span {
            background:linear-gradient(90deg,#2563eb 0%,#7c3aed 48%,#ec4899 78%,#06b6d4 100%);
            -webkit-background-clip:text;
            -webkit-text-fill-color:transparent;
        }

        .pn-login-head p {
            max-width:720px;
            margin:.75rem auto 0;
            color:#5f6f8f;
            font-size:1rem;
            line-height:1.65;
        }

        .pn-login-stats {
            display:flex;
            flex-wrap:wrap;
            justify-content:center;
            gap:.55rem;
            margin-top:.85rem;
        }

        .pn-login-stats span {
            padding:.4rem .68rem;
            border-radius:999px;
            color:#17325d;
            background:rgba(255,255,255,.78);
            box-shadow:0 6px 16px rgba(31,72,145,.07);
            font-size:.68rem;
            font-weight:800;
        }

        /* Left login card */
        [data-testid="stHorizontalBlock"]:has(.st-key-login_visual)
        > [data-testid="column"]:first-child {
            position:relative;
            z-index:3;
            padding:1.05rem 1.1rem 1.15rem !important;
            border:1px solid rgba(255,255,255,.82);
            border-radius:24px;
            background:
                linear-gradient(145deg,rgba(255,255,255,.96),rgba(245,249,255,.88));
            box-shadow:
                0 20px 50px rgba(39,76,145,.15),
                inset 0 1px 0 rgba(255,255,255,.95);
            backdrop-filter:blur(18px);
        }

        [data-testid="stHorizontalBlock"]:has(.st-key-login_visual)
        > [data-testid="column"]:first-child [data-testid="stImage"] {
            display:flex;
            justify-content:center;
        }

        [data-testid="stHorizontalBlock"]:has(.st-key-login_visual)
        > [data-testid="column"]:first-child img {
            max-width:205px !important;
            filter:drop-shadow(0 12px 24px rgba(37,99,235,.18));
        }

        [data-testid="stHorizontalBlock"]:has(.st-key-login_visual)
        > [data-testid="column"]:first-child div[data-testid="stTabs"] {
            margin-top:.35rem;
        }

        [data-testid="stHorizontalBlock"]:has(.st-key-login_visual)
        > [data-testid="column"]:first-child div[data-testid="stTabs"] button {
            min-height:44px;
            border-radius:12px 12px 0 0;
            color:#31425f;
            font-size:.72rem;
            font-weight:850;
        }

        [data-testid="stHorizontalBlock"]:has(.st-key-login_visual)
        > [data-testid="column"]:first-child div[data-testid="stForm"] {
            padding:.9rem;
            border:1px solid rgba(37,99,235,.12);
            border-radius:18px;
            background:linear-gradient(145deg,#ffffff,#f7fbff);
            box-shadow:0 9px 24px rgba(37,99,235,.06);
        }

        [data-testid="stHorizontalBlock"]:has(.st-key-login_visual)
        > [data-testid="column"]:first-child input {
            min-height:46px;
            border:1px solid rgba(37,99,235,.16) !important;
            border-radius:13px !important;
            background:
                linear-gradient(90deg,#f8fbff,#f4f2ff) !important;
        }

        [data-testid="stHorizontalBlock"]:has(.st-key-login_visual)
        > [data-testid="column"]:first-child div[data-testid="stFormSubmitButton"] > button,
        [data-testid="stHorizontalBlock"]:has(.st-key-login_visual)
        > [data-testid="column"]:first-child div[data-testid="stButton"] > button {
            min-height:47px;
            border:0 !important;
            border-radius:13px !important;
            color:#fff !important;
            background:
                linear-gradient(90deg,#2563eb 0%,#7c3aed 55%,#ec4899 100%) !important;
            box-shadow:
                0 12px 26px rgba(99,70,220,.26),
                0 0 0 4px rgba(124,58,237,.06) !important;
            font-weight:900 !important;
        }

        .pn-login-note {
            margin-top:.75rem;
            padding:.72rem .82rem;
            border:1px solid rgba(6,182,212,.13);
            border-radius:14px;
            color:#375276;
            background:
                linear-gradient(90deg,rgba(224,247,255,.86),rgba(238,242,255,.88));
            font-size:.75rem;
            line-height:1.55;
        }

        /* Right visual */
        .st-key-login_visual {
            position:relative;
            z-index:3;
            height:100%;
            padding:.6rem;
            border:1px solid rgba(255,255,255,.78) !important;
            border-radius:26px !important;
            overflow:hidden !important;
            background:
                linear-gradient(145deg,rgba(255,255,255,.86),rgba(230,240,255,.58)) !important;
            box-shadow:
                0 24px 55px rgba(27,62,125,.17),
                inset 0 1px 0 rgba(255,255,255,.95) !important;
            backdrop-filter:blur(16px);
        }

        .st-key-login_visual img {
            width:100% !important;
            min-height:455px;
            max-height:560px;
            border-radius:20px !important;
            object-fit:cover !important;
            object-position:center !important;
            box-shadow:0 18px 42px rgba(15,55,110,.20) !important;
        }
</style>
        """,
        unsafe_allow_html=True,
    )


def initialize_state() -> None:
    defaults = {
        "devices": {},
        "links": [],
        "events": [],
        "selected_device": None,
        "cli_modes": {},
        "cli_interfaces": {},
        "cli_history": {},
        "booted_devices": set(),
        "authenticated": False,
        "current_project_id": None,
        "current_project_name": "Untitled topology",
        "lab_configs": {
            "vlans": [],
            "ospf": [],
            "bgp": [],
            "acls": [],
            "nat": [],
            "dhcp": [],
            "sdwan": [],
        },
        "user_email": "",
        "user_name": "",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def log(message: str) -> None:
    st.session_state.events.insert(0, message)
    st.session_state.events = st.session_state.events[:200]


def reset() -> None:
    st.session_state.devices = {}
    st.session_state.links = []
    st.session_state.events = []
    st.session_state.selected_device = None
    st.session_state.cli_modes = {}
    st.session_state.cli_interfaces = {}
    st.session_state.cli_history = {}
    st.session_state.booted_devices = set()


def add_device(name: str, device_type: str, description: str = "") -> str:
    name = name.strip()

    if not name:
        return "Device name is required."

    if name in st.session_state.devices:
        return f"Device {name} already exists."

    st.session_state.devices[name] = Device(
        name=name,
        device_type=device_type,
        description=description.strip(),
    )
    st.session_state.cli_modes[name] = "user"
    st.session_state.cli_history[name] = []
    log(f"Added {device_type}: {name}")
    return f"Added {device_type} {name}."


def add_interface(device_name: str, interface_name: str, ip_address: str = "") -> str:
    device = st.session_state.devices.get(device_name)

    if not device:
        return "Device not found."

    interface_name = interface_name.strip()

    if not interface_name:
        return "Interface name is required."

    if ip_address:
        try:
            ipaddress.ip_interface(ip_address)
        except ValueError:
            return "Use CIDR format, for example 10.0.0.1/24."

    device.interfaces[interface_name] = Interface(interface_name, ip_address)
    log(f"Configured {device_name}:{interface_name} {ip_address or 'without IP'}")
    return "Interface added."


def connect(device_a: str, interface_a: str, device_b: str, interface_b: str) -> str:
    if device_a == device_b:
        return "Select two different devices."

    dev_a = st.session_state.devices.get(device_a)
    dev_b = st.session_state.devices.get(device_b)

    if not dev_a or not dev_b:
        return "Both devices must exist."

    if interface_a not in dev_a.interfaces or interface_b not in dev_b.interfaces:
        return "Both interfaces must exist."

    if dev_a.interfaces[interface_a].connected_to or dev_b.interfaces[interface_b].connected_to:
        return "One interface is already connected."

    st.session_state.links.append(
        (device_a, interface_a, device_b, interface_b)
    )
    dev_a.interfaces[interface_a].connected_to = f"{device_b}:{interface_b}"
    dev_b.interfaces[interface_b].connected_to = f"{device_a}:{interface_a}"
    log(f"Connected {device_a}:{interface_a} ↔ {device_b}:{interface_b}")
    return "Link created."


def adjacency() -> Dict[str, List[str]]:
    result = {name: [] for name in st.session_state.devices}

    for device_a, interface_a, device_b, interface_b in st.session_state.links:
        if (
            st.session_state.devices[device_a].interfaces[interface_a].status == "up"
            and st.session_state.devices[device_b].interfaces[interface_b].status == "up"
        ):
            result[device_a].append(device_b)
            result[device_b].append(device_a)

    return result


def destination_device_for_ip(destination_ip: str) -> Optional[str]:
    try:
        target = ipaddress.ip_address(destination_ip)
    except ValueError:
        return None

    for device in st.session_state.devices.values():
        for interface in device.interfaces.values():
            if not interface.ip_address:
                continue
            try:
                if ipaddress.ip_interface(interface.ip_address).ip == target:
                    return device.name
            except ValueError:
                continue

    return None


def find_path(source: str, destination: str) -> Optional[List[str]]:
    queue = [(source, [source])]
    seen = {source}
    graph = adjacency()

    while queue:
        current, current_path = queue.pop(0)

        if current == destination:
            return current_path

        for neighbor in graph.get(current, []):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, current_path + [neighbor]))

    return None


def ping(source: str, destination_ip: str) -> List[str]:
    destination = destination_device_for_ip(destination_ip)

    if not destination:
        return [f"Destination {destination_ip} is not configured."]

    route = find_path(source, destination)

    if route:
        log(f"Ping {source} → {destination_ip}: SUCCESS")
        return [
            f"PING {destination_ip}",
            f"Reply from {destination_ip}: path={' → '.join(route)}",
            "Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)",
        ]

    log(f"Ping {source} → {destination_ip}: FAILED")
    return [
        f"PING {destination_ip}",
        "Destination unreachable: no active path found.",
        "Packets: Sent = 4, Received = 0, Lost = 4 (100% loss)",
    ]


def traceroute(source: str, destination_ip: str) -> List[str]:
    destination = destination_device_for_ip(destination_ip)

    if not destination:
        return [f"Destination {destination_ip} is not configured."]

    route = find_path(source, destination)

    if not route:
        return ["Traceroute failed: no active path found."]

    return (
        [f"Tracing route to {destination_ip}"]
        + [
            f"{hop:<3} {device:<15} 1 ms 1 ms 2 ms"
            for hop, device in enumerate(route, 1)
        ]
        + ["Trace complete."]
    )


def show_ip_interface_brief(device: Device) -> str:
    lines = ["Interface              IP-Address        Status   Protocol"]

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
        lines.append(
            f"{interface.name:<22} {ip_value:<17} "
            f"{interface.status:<8} {protocol}"
        )

    return "\n".join(lines)


def show_ip_route(device: Device) -> str:
    lines = ["Codes: C - connected, S - static", ""]

    for interface in device.interfaces.values():
        if interface.ip_address and interface.status == "up":
            network = ipaddress.ip_interface(interface.ip_address).network
            lines.append(
                f"C    {network} is directly connected, {interface.name}"
            )

    for network, next_hop in device.routing_table.items():
        lines.append(f"S    {network} [1/0] via {next_hop}")

    return "\n".join(lines) if len(lines) > 2 else "Gateway of last resort is not set."


def running_config(device: Device) -> str:
    lines = [
        f"hostname {device.name}",
        f"! device-type {device.device_type}",
    ]

    for interface in device.interfaces.values():
        lines.extend(
            [
                f"interface {interface.name}",
                f" ip address {interface.ip_address or 'unassigned'}",
                f" {'no shutdown' if interface.status == 'up' else 'shutdown'}",
                "!",
            ]
        )

    for network, next_hop in device.routing_table.items():
        lines.append(f"ip route {network} {next_hop}")

    return "\n".join(lines)


def topology_dot() -> str:
    lines = [
        "graph topology {",
        'graph [bgcolor="transparent",rankdir=LR,pad=0.3,nodesep=0.7];',
        'node [shape=box,style="rounded,filled",fontname="Arial",fontcolor="white"];',
        'edge [penwidth=2,fontname="Arial",fontsize=9];',
    ]

    for device in st.session_state.devices.values():
        icon = ICONS.get(device.device_type, "●")
        color = COLORS.get(device.device_type, "#2563EB")
        lines.append(
            f'"{device.name}" '
            f'[label="{icon} {device.name}\\n{device.device_type}",'
            f'fillcolor="{color}"];'
        )

    for device_a, interface_a, device_b, interface_b in st.session_state.links:
        active = (
            st.session_state.devices[device_a].interfaces[interface_a].status == "up"
            and st.session_state.devices[device_b].interfaces[interface_b].status == "up"
        )
        color = "#22C55E" if active else "#EF4444"
        style = "solid" if active else "dashed"
        lines.append(
            f'"{device_a}" -- "{device_b}" '
            f'[label="{interface_a} ↔ {interface_b}",'
            f'color="{color}",style="{style}"];'
        )

    lines.append("}")
    return "\n".join(lines)


def topology_payload() -> dict:
    return {
        "devices": {
            name: asdict(device)
            for name, device in st.session_state.devices.items()
        },
        "links": st.session_state.links,
        "events": st.session_state.events,
        "lab_configs": st.session_state.get("lab_configs", {}),
    }


def export_json() -> str:
    return json.dumps(topology_payload(), indent=2)


def import_json(raw: str) -> None:
    data = json.loads(raw)
    devices: Dict[str, Device] = {}

    for name, raw_device in data.get("devices", {}).items():
        device = Device(
            raw_device["name"],
            raw_device["device_type"],
            routing_table=raw_device.get("routing_table", {}),
            description=raw_device.get("description", ""),
        )

        for interface_name, raw_interface in raw_device.get("interfaces", {}).items():
            device.interfaces[interface_name] = Interface(**raw_interface)

        devices[name] = device

    st.session_state.devices = devices
    st.session_state.links = [tuple(item) for item in data.get("links", [])]
    st.session_state.events = data.get("events", [])
    st.session_state.lab_configs = data.get(
        "lab_configs",
        {
            "vlans": [],
            "ospf": [],
            "bgp": [],
            "acls": [],
            "nat": [],
            "dhcp": [],
            "sdwan": [],
        },
    )
    st.session_state.cli_modes = {name: "user" for name in devices}
    st.session_state.cli_history = {name: [] for name in devices}
    st.session_state.cli_interfaces = {}
    st.session_state.booted_devices = set()
    log("Imported topology")


def import_topology_payload(payload: dict) -> None:
    import_json(json.dumps(payload))


def load_demo() -> None:
    reset()

    for name, device_type in [
        ("PC1", "PC"),
        ("SW1", "Switch"),
        ("R1", "Router"),
        ("FW1", "Firewall"),
        ("R2", "Router"),
        ("PC2", "PC"),
        ("Internet", "Cloud"),
    ]:
        add_device(name, device_type)

    for values in [
        ("PC1", "eth0", "10.0.1.10/24"),
        ("SW1", "Gi0/1", ""),
        ("SW1", "Gi0/2", ""),
        ("R1", "Gi0/0", "10.0.1.1/24"),
        ("R1", "Gi0/1", "172.16.0.1/30"),
        ("FW1", "Gi0/0", "172.16.0.2/30"),
        ("FW1", "Gi0/1", "172.16.1.1/30"),
        ("R2", "Gi0/0", "172.16.1.2/30"),
        ("R2", "Gi0/1", "10.0.2.1/24"),
        ("PC2", "eth0", "10.0.2.10/24"),
        ("FW1", "Gi0/2", "203.0.113.2/24"),
        ("Internet", "wan0", "203.0.113.1/24"),
    ]:
        add_interface(*values)

    for values in [
        ("PC1", "eth0", "SW1", "Gi0/1"),
        ("SW1", "Gi0/2", "R1", "Gi0/0"),
        ("R1", "Gi0/1", "FW1", "Gi0/0"),
        ("FW1", "Gi0/1", "R2", "Gi0/0"),
        ("R2", "Gi0/1", "PC2", "eth0"),
        ("FW1", "Gi0/2", "Internet", "wan0"),
    ]:
        connect(*values)

    st.session_state.devices["R1"].routing_table["10.0.2.0/24"] = "172.16.0.2"
    st.session_state.devices["R2"].routing_table["10.0.1.0/24"] = "172.16.1.1"
    log("Loaded enhanced demo topology")


def prompt_for(device_name: str) -> str:
    mode = st.session_state.cli_modes.get(device_name, "user")

    if mode == "privileged":
        return f"{device_name}#"
    if mode == "config":
        return f"{device_name}(config)#"
    if mode == "interface":
        interface_name = st.session_state.cli_interfaces.get(device_name, "")
        return f"{device_name}(config-if-{interface_name})#"

    return f"{device_name}>"


def append_cli(device_name: str, line: str) -> None:
    st.session_state.cli_history.setdefault(device_name, []).append(line)
    st.session_state.cli_history[device_name] = (
        st.session_state.cli_history[device_name][-150:]
    )


def boot_device(device_name: str) -> None:
    if device_name in st.session_state.booted_devices:
        return

    device = st.session_state.devices[device_name]
    boot_lines = [
        "System Bootstrap, Version 1.0",
        f"Loading PeerNet Virtual OS for {device.device_type}...",
        "Initializing virtual interfaces...",
        "Loading startup configuration...",
        "Press RETURN to get started!",
        "",
        prompt_for(device_name),
    ]

    st.session_state.cli_history[device_name] = boot_lines
    st.session_state.booted_devices.add(device_name)


def execute_cli(device_name: str, command: str) -> None:
    command = command.strip()
    device = st.session_state.devices[device_name]
    mode = st.session_state.cli_modes.get(device_name, "user")
    current_prompt = prompt_for(device_name)

    if not command:
        append_cli(device_name, current_prompt)
        return

    append_cli(device_name, f"{current_prompt} {command}")
    lowered = command.lower()
    words = command.split()

    if lowered in {"enable", "en"}:
        st.session_state.cli_modes[device_name] = "privileged"
        return

    if lowered in {"disable"}:
        st.session_state.cli_modes[device_name] = "user"
        return

    if lowered in {"configure terminal", "conf t", "config t"}:
        if mode not in {"privileged", "config", "interface"}:
            append_cli(device_name, "% Privileged EXEC mode required. Enter 'enable'.")
        else:
            st.session_state.cli_modes[device_name] = "config"
        return

    if lowered in {"end"}:
        st.session_state.cli_modes[device_name] = "privileged"
        st.session_state.cli_interfaces.pop(device_name, None)
        return

    if lowered in {"exit"}:
        if mode == "interface":
            st.session_state.cli_modes[device_name] = "config"
            st.session_state.cli_interfaces.pop(device_name, None)
        elif mode == "config":
            st.session_state.cli_modes[device_name] = "privileged"
        elif mode == "privileged":
            st.session_state.cli_modes[device_name] = "user"
        return

    if lowered.startswith("interface "):
        if mode not in {"config", "interface"}:
            append_cli(device_name, "% Enter global configuration mode first.")
            return

        interface_name = command.split(maxsplit=1)[1].strip()
        if interface_name not in device.interfaces:
            device.interfaces[interface_name] = Interface(interface_name)
            log(f"Created {device_name}:{interface_name} from CLI")

        st.session_state.cli_modes[device_name] = "interface"
        st.session_state.cli_interfaces[device_name] = interface_name
        return

    if lowered.startswith("hostname "):
        if mode != "config":
            append_cli(device_name, "% Hostname can only be changed in global configuration mode.")
            return

        new_name = command.split(maxsplit=1)[1].strip()
        if not new_name or new_name in st.session_state.devices:
            append_cli(device_name, "% Invalid or duplicate hostname.")
            return

        old_name = device_name
        device.name = new_name
        st.session_state.devices[new_name] = device
        del st.session_state.devices[old_name]

        st.session_state.selected_device = new_name
        st.session_state.cli_modes[new_name] = st.session_state.cli_modes.pop(old_name)
        st.session_state.cli_history[new_name] = st.session_state.cli_history.pop(old_name)
        st.session_state.booted_devices.discard(old_name)
        st.session_state.booted_devices.add(new_name)

        if old_name in st.session_state.cli_interfaces:
            st.session_state.cli_interfaces[new_name] = (
                st.session_state.cli_interfaces.pop(old_name)
            )

        updated_links = []
        for device_a, interface_a, device_b, interface_b in st.session_state.links:
            updated_links.append(
                (
                    new_name if device_a == old_name else device_a,
                    interface_a,
                    new_name if device_b == old_name else device_b,
                    interface_b,
                )
            )
        st.session_state.links = updated_links
        append_cli(new_name, f"Hostname changed from {old_name} to {new_name}.")
        return

    if lowered.startswith("ip address "):
        if mode != "interface":
            append_cli(device_name, "% Enter interface configuration mode first.")
            return

        interface_name = st.session_state.cli_interfaces.get(device_name)
        values = words[2:]

        try:
            if len(values) == 1 and "/" in values[0]:
                cidr = str(ipaddress.ip_interface(values[0]))
            elif len(values) == 2:
                network = ipaddress.IPv4Network(
                    f"0.0.0.0/{values[1]}"
                )
                cidr = str(
                    ipaddress.ip_interface(
                        f"{values[0]}/{network.prefixlen}"
                    )
                )
            else:
                raise ValueError
        except ValueError:
            append_cli(
                device_name,
                "% Use: ip address 10.0.0.1/24 "
                "or ip address 10.0.0.1 255.255.255.0",
            )
            return

        device.interfaces[interface_name].ip_address = cidr
        log(f"CLI configured {device_name}:{interface_name} {cidr}")
        return

    if lowered in {"shutdown", "shut"}:
        if mode != "interface":
            append_cli(device_name, "% Enter interface configuration mode first.")
            return
        interface_name = st.session_state.cli_interfaces[device_name]
        device.interfaces[interface_name].status = "down"
        log(f"CLI shutdown {device_name}:{interface_name}")
        return

    if lowered in {"no shutdown", "no shut"}:
        if mode != "interface":
            append_cli(device_name, "% Enter interface configuration mode first.")
            return
        interface_name = st.session_state.cli_interfaces[device_name]
        device.interfaces[interface_name].status = "up"
        log(f"CLI enabled {device_name}:{interface_name}")
        return

    if lowered.startswith("ip route "):
        if mode != "config":
            append_cli(device_name, "% Enter global configuration mode first.")
            return

        route_values = words[2:]

        try:
            if len(route_values) == 2 and "/" in route_values[0]:
                network = str(ipaddress.ip_network(route_values[0], strict=False))
                next_hop = str(ipaddress.ip_address(route_values[1]))
            elif len(route_values) == 3:
                prefix = ipaddress.IPv4Network(f"0.0.0.0/{route_values[1]}").prefixlen
                network = str(
                    ipaddress.ip_network(
                        f"{route_values[0]}/{prefix}",
                        strict=False,
                    )
                )
                next_hop = str(ipaddress.ip_address(route_values[2]))
            else:
                raise ValueError
        except ValueError:
            append_cli(
                device_name,
                "% Use: ip route 10.0.2.0/24 172.16.0.2",
            )
            return

        device.routing_table[network] = next_hop
        log(f"CLI static route {device_name}: {network} via {next_hop}")
        return

    if lowered in {"show ip interface brief", "show ip int brief"}:
        append_cli(device_name, show_ip_interface_brief(device))
        return

    if lowered == "show ip route":
        append_cli(device_name, show_ip_route(device))
        return

    if lowered in {"show running-config", "show run"}:
        append_cli(device_name, running_config(device))
        return

    if lowered == "show version":
        append_cli(
            device_name,
            f"PeerNet Virtual OS Software\n"
            f"Device: {device.name}\n"
            f"Platform: Virtual {device.device_type}\n"
            f"Interfaces: {len(device.interfaces)}\n"
            f"Uptime: simulated",
        )
        return

    if lowered.startswith("ping "):
        destination_ip = command.split(maxsplit=1)[1]
        append_cli(device_name, "\n".join(ping(device_name, destination_ip)))
        return

    if lowered.startswith("traceroute "):
        destination_ip = command.split(maxsplit=1)[1]
        append_cli(
            device_name,
            "\n".join(traceroute(device_name, destination_ip)),
        )
        return

    if lowered in {"help", "?"}:
        append_cli(
            device_name,
            "Supported commands:\n"
            " enable\n"
            " configure terminal\n"
            " interface <name>\n"
            " ip address <CIDR>\n"
            " shutdown | no shutdown\n"
            " ip route <network/CIDR> <next-hop>\n"
            " show ip interface brief\n"
            " show ip route\n"
            " show running-config\n"
            " show version\n"
            " ping <IP>\n"
            " traceroute <IP>\n"
            " exit | end",
        )
        return

    append_cli(device_name, f"% Invalid input detected at '^' marker: {command}")


def render_device_console(device_name: str) -> None:
    boot_device(device_name)
    device = st.session_state.devices[device_name]
    icon = ICONS.get(device.device_type, "●")

    st.markdown(
        f"""
        <div class="pn-device-title">
            <span>{icon}</span>
            <div>
                <strong>{device.name}</strong><br>
                <small>{device.device_type} configuration console</small>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    output = "\n".join(st.session_state.cli_history.get(device_name, []))
    st.markdown(
        f'<div class="pn-console">{output}</div>',
        unsafe_allow_html=True,
    )

    with st.form(
        f"cli_form_{device_name}",
        clear_on_submit=True,
        border=False,
    ):
        command = st.text_input(
            "CLI command",
            placeholder="Type a command and press Enter, for example: enable",
            label_visibility="collapsed",
            key=f"cli_input_{device_name}",
        )
        submitted = st.form_submit_button("Submit command")

    st.markdown(
        '<div class="pn-cli-hint">Press <b>Enter</b> to run the command. Type <code>help</code> to list supported commands.</div>',
        unsafe_allow_html=True,
    )

    if submitted:
        execute_cli(device_name, command)
        st.rerun()


def authentication_page() -> None:
    st.markdown(
        """
        <section class="pn-login-shell">
            <div class="pn-login-head">
                <div class="pn-login-eyebrow">✦ NEXT-GENERATION NETWORK LAB</div>
                <h1>Welcome to <span>PeerNet Network Simulator</span></h1>
                <p>
                    Build colorful topologies, configure devices with a Cisco-style CLI,
                    practice advanced protocols, and securely save labs to Supabase.
                </p>
                <div class="pn-login-stats">
                    <span>🌐 Visual Topologies</span>
                    <span>⌨ Manual CLI</span>
                    <span>🧠 Advanced Labs</span>
                    <span>☁ Cloud Save</span>
                    <span>🛡 Secure Login</span>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    form_col, visual_col = st.columns([.9, 1.2], gap="large")

    with form_col:
        st.image(COMPANY_LOGO, width=210)
        login_tab, register_tab, reset_tab = st.tabs(
            ["Login", "Create account", "Forgot password"]
        )

        with login_tab:
            with st.form("simulator_login"):
                email = st.text_input(
                    "Gmail address",
                    placeholder="yourname@gmail.com",
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Enter your password",
                )
                login_submitted = st.form_submit_button(
                    "Login →",
                    type="primary",
                    use_container_width=True,
                )

            if login_submitted:
                try:
                    sign_in(email, password)
                    st.rerun()
                except Exception as error:
                    st.error(f"Unable to sign in: {error}")

        with register_tab:
            with st.form("simulator_register"):
                full_name = st.text_input("Full name")
                register_email = st.text_input(
                    "Gmail address",
                    placeholder="yourname@gmail.com",
                    key="register_gmail",
                )
                register_password = st.text_input(
                    "Password",
                    type="password",
                    key="register_password",
                )
                confirm_password = st.text_input(
                    "Confirm password",
                    type="password",
                )
                register_submitted = st.form_submit_button(
                    "Create account",
                    use_container_width=True,
                )

            if register_submitted:
                if register_password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    try:
                        response = sign_up(
                            register_email,
                            register_password,
                            full_name,
                            "",
                        )
                        if getattr(response, "session", None):
                            st.success("Account created. You can continue.")
                        else:
                            st.success(
                                "Account created. Check Gmail and verify your email before logging in."
                            )
                    except Exception as error:
                        st.error(f"Unable to register: {error}")

        with reset_tab:
            reset_email = st.text_input(
                "Registered Gmail address",
                key="reset_gmail",
            )
            if st.button(
                "Send reset link",
                use_container_width=True,
            ):
                try:
                    send_password_reset(reset_email)
                    st.success("Password-reset link sent to Gmail.")
                except Exception as error:
                    st.error(f"Unable to send reset link: {error}")

        st.markdown(
            '<div class="pn-login-note">Your password is handled by Supabase Authentication. Secrets are not stored in GitHub.</div>',
            unsafe_allow_html=True,
        )

    with visual_col:
        with st.container(key="login_visual"):
            st.image(LOGIN_ILLUSTRATION, use_container_width=True)

apply_styles()
initialize_state()

if not st.session_state.get("authenticated"):
    authentication_page()
    st.stop()

st.markdown(
    """
    <section class="pn-head">
        <div>
            <h1>🌐 PeerNet Network Simulator</h1>
            <p>Build, configure, visualize, test and troubleshoot logical network topologies.</p>
        </div>
        <div class="pn-badge">PeerNet Solutions</div>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.image(COMPANY_LOGO, use_container_width=True)
    st.caption(
        f"Signed in as **{st.session_state.get('user_name') or st.session_state.get('user_email')}**"
    )
    if st.button("Logout", use_container_width=True):
        sign_out()
        st.rerun()

    st.title("Simulator Controls")

    if st.button(
        "⚡ Load Demo Topology",
        use_container_width=True,
    ):
        load_demo()
        st.rerun()

    if st.button(
        "🧹 Reset Simulator",
        use_container_width=True,
    ):
        reset()
        st.rerun()

    st.divider()
    st.subheader("Save / Open")

    st.download_button(
        "⬇ Download topology",
        export_json(),
        "peernet_topology.json",
        "application/json",
        use_container_width=True,
    )

    uploaded_topology = st.file_uploader(
        "Open topology",
        type=["json"],
    )

    if uploaded_topology and st.button(
        "Import topology",
        use_container_width=True,
    ):
        import_json(uploaded_topology.getvalue().decode("utf-8"))
        st.rerun()

    st.divider()
    st.subheader("☁ Supabase Cloud")

    cloud_name = st.text_input(
        "Project name",
        value=st.session_state.get(
            "current_project_name",
            "Untitled topology",
        ),
        key="cloud_project_name",
    )

    save_label = (
        "Update cloud project"
        if st.session_state.get("current_project_id")
        else "Save new cloud project"
    )

    if st.button(
        save_label,
        use_container_width=True,
        type="primary",
    ):
        try:
            current_id = st.session_state.get("current_project_id")
            if current_id:
                project = update_simulator_project(
                    current_id,
                    cloud_name,
                    topology_payload(),
                )
            else:
                project = create_simulator_project(
                    cloud_name,
                    topology_payload(),
                )

            st.session_state.current_project_id = project["id"]
            st.session_state.current_project_name = project["name"]
            st.success("Topology saved securely to Supabase.")
            st.rerun()
        except Exception as error:
            st.error(f"Cloud save failed: {error}")

    try:
        cloud_projects = list_simulator_projects()
    except Exception as error:
        cloud_projects = []
        st.caption(f"Cloud projects unavailable: {error}")

    if cloud_projects:
        project_options = {
            f"{item['name']} · {str(item['id'])[:8]}": item
            for item in cloud_projects
        }
        selected_project_label = st.selectbox(
            "Saved projects",
            list(project_options),
            key="saved_cloud_project",
        )
        selected_project = project_options[selected_project_label]

        open_col, delete_col = st.columns(2)

        with open_col:
            if st.button(
                "Open",
                key="open_cloud_project",
                use_container_width=True,
            ):
                try:
                    project = load_simulator_project(
                        selected_project["id"]
                    )
                    import_topology_payload(project["topology_json"])
                    st.session_state.current_project_id = project["id"]
                    st.session_state.current_project_name = project["name"]
                    st.success("Cloud project loaded.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Unable to open project: {error}")

        with delete_col:
            if st.button(
                "Delete",
                key="delete_cloud_project",
                use_container_width=True,
            ):
                try:
                    delete_simulator_project(selected_project["id"])
                    if (
                        st.session_state.get("current_project_id")
                        == selected_project["id"]
                    ):
                        st.session_state.current_project_id = None
                        st.session_state.current_project_name = (
                            "Untitled topology"
                        )
                    st.success("Cloud project deleted.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Unable to delete project: {error}")
    else:
        st.caption("No cloud projects saved yet.")

    st.caption("PeerNet Solutions • Logical Network Lab")


active_interfaces = sum(
    1
    for device in st.session_state.devices.values()
    for interface in device.interfaces.values()
    if interface.status == "up"
)

for column, (label, value) in zip(
    st.columns(4),
    [
        ("Devices", len(st.session_state.devices)),
        ("Links", len(st.session_state.links)),
        ("Active interfaces", active_interfaces),
        ("Events", len(st.session_state.events)),
    ],
):
    column.metric(label, value)


tabs = st.tabs(
    [
        "🧩 Build",
        "🗺 Topology",
        "🖥 Device Console",
        "🧪 Test",
        "🧠 Advanced Labs",
        "⚠ Failures",
        "📜 Events",
    ]
)

with tabs[0]:
    add_col, interface_col, link_col = st.columns(3)

    with add_col:
        st.subheader("Add Device")

        with st.form("add_device_form", clear_on_submit=True):
            device_name = st.text_input(
                "Device name",
                placeholder="R1",
            )
            device_type = st.selectbox(
                "Device type",
                list(ICONS),
            )
            description = st.text_input(
                "Description",
                placeholder="Branch router",
            )
            submitted = st.form_submit_button(
                "Add Device",
                use_container_width=True,
            )

            if submitted:
                st.info(
                    add_device(
                        device_name,
                        device_type,
                        description,
                    )
                )

    with interface_col:
        st.subheader("Configure Interface")

        if st.session_state.devices:
            with st.form("add_interface_form", clear_on_submit=True):
                selected_device = st.selectbox(
                    "Device",
                    list(st.session_state.devices),
                    key="interface_device",
                )
                interface_name = st.text_input(
                    "Interface name",
                    placeholder="Gi0/0",
                )
                interface_ip = st.text_input(
                    "IP address/CIDR",
                    placeholder="10.0.0.1/24",
                )
                submitted = st.form_submit_button(
                    "Add Interface",
                    use_container_width=True,
                )

                if submitted:
                    st.info(
                        add_interface(
                            selected_device,
                            interface_name,
                            interface_ip,
                        )
                    )
        else:
            st.warning("Add a device first.")

    with link_col:
        st.subheader("Create Link")

        candidates = [
            name
            for name, device in st.session_state.devices.items()
            if device.interfaces
        ]

        if len(candidates) >= 2:
            device_a = st.selectbox(
                "Device A",
                candidates,
                key="device_a",
            )
            interface_a = st.selectbox(
                "Interface A",
                list(st.session_state.devices[device_a].interfaces),
                key="interface_a",
            )
            device_b = st.selectbox(
                "Device B",
                [name for name in candidates if name != device_a],
                key="device_b",
            )
            interface_b = st.selectbox(
                "Interface B",
                list(st.session_state.devices[device_b].interfaces),
                key="interface_b",
            )

            if st.button(
                "Connect Devices",
                use_container_width=True,
            ):
                st.info(
                    connect(
                        device_a,
                        interface_a,
                        device_b,
                        interface_b,
                    )
                )
        else:
            st.warning("At least two devices with interfaces are required.")

    st.subheader("Device Inventory — click a device to configure it")

    if not st.session_state.devices:
        st.info("Add a device or load the demo topology.")
    else:
        devices = list(st.session_state.devices.values())
        columns = st.columns(min(4, len(devices)))

        for index, device in enumerate(devices):
            with columns[index % len(columns)]:
                icon = ICONS.get(device.device_type, "●")
                st.markdown(
                    f"""
                    <div class="pn-device-card">
                        <div class="icon">{icon}</div>
                        <strong>{device.name}</strong>
                        <small>{device.device_type} • {len(device.interfaces)} interfaces</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if st.button(
                    f"Open {device.name}",
                    key=f"device_open_{device.name}",
                    use_container_width=True,
                ):
                    st.session_state.selected_device = device.name
                    boot_device(device.name)
                    st.rerun()

with tabs[1]:
    if st.session_state.devices:
        st.graphviz_chart(
            topology_dot(),
            use_container_width=True,
        )
        st.caption(
            "Green links are active. Red dashed links contain a down interface."
        )

        st.subheader("Open a device")
        device_columns = st.columns(
            min(5, len(st.session_state.devices))
        )

        for index, device_name in enumerate(st.session_state.devices):
            with device_columns[index % len(device_columns)]:
                device = st.session_state.devices[device_name]
                if st.button(
                    f"{ICONS.get(device.device_type, '●')} {device_name}",
                    key=f"topology_device_{device_name}",
                    use_container_width=True,
                ):
                    st.session_state.selected_device = device_name
                    boot_device(device_name)
                    st.rerun()
    else:
        st.info("Load the demo or create devices.")

with tabs[2]:
    if st.session_state.selected_device in st.session_state.devices:
        render_device_console(st.session_state.selected_device)
    elif st.session_state.devices:
        st.info("Select a device below to open its boot and CLI console.")
        selection = st.selectbox(
            "Device",
            list(st.session_state.devices),
            key="console_device_selection",
        )
        if st.button(
            "Boot and Open Device",
            type="primary",
        ):
            st.session_state.selected_device = selection
            boot_device(selection)
            st.rerun()
    else:
        st.warning("No devices are available.")

with tabs[3]:
    if st.session_state.devices:
        source = st.selectbox(
            "Source device",
            list(st.session_state.devices),
            key="test_source",
        )
        destination_ip = st.text_input(
            "Destination IP",
            placeholder="10.0.2.10",
        )
        test_type = st.radio(
            "Test type",
            ["Ping", "Traceroute"],
            horizontal=True,
        )

        if st.button(
            "Run Test",
            type="primary",
        ):
            output = (
                ping(source, destination_ip)
                if test_type == "Ping"
                else traceroute(source, destination_ip)
            )
            st.code("\n".join(output), language="text")
    else:
        st.warning("Load the demo or build a topology.")

with tabs[4]:
    st.subheader("Next-Generation Network Labs")
    st.caption(
        "This release adds a functional configuration foundation for advanced protocols. "
        "It is a logical simulator—not a packet-level IOS emulator."
    )

    if not st.session_state.devices:
        st.info("Load the demo topology or add devices before creating protocol labs.")
    else:
        lab_type = st.selectbox(
            "Lab type",
            ["VLAN", "OSPF", "BGP", "ACL", "NAT", "DHCP", "SD-WAN"],
            key="advanced_lab_type",
        )

        device_name = st.selectbox(
            "Target device",
            list(st.session_state.devices),
            key="advanced_lab_device",
        )

        config = st.session_state.lab_configs

        if lab_type == "VLAN":
            with st.form("vlan_lab_form", clear_on_submit=True):
                vlan_id = st.number_input("VLAN ID", 1, 4094, 10)
                vlan_name = st.text_input("VLAN name", "USERS")
                submitted_lab = st.form_submit_button("Apply VLAN")
            if submitted_lab:
                entry = {"device": device_name, "vlan_id": int(vlan_id), "name": vlan_name.strip()}
                config["vlans"].append(entry)
                append_cli(device_name, f"{device_name}(config)# vlan {int(vlan_id)}")
                append_cli(device_name, f"{device_name}(config-vlan)# name {vlan_name.strip()}")
                log(f"VLAN {int(vlan_id)} configured on {device_name}")
                st.success("VLAN configuration added.")

        elif lab_type == "OSPF":
            with st.form("ospf_lab_form", clear_on_submit=True):
                process_id = st.number_input("Process ID", 1, 65535, 1)
                network = st.text_input("Network/CIDR", "10.0.0.0/24")
                area = st.number_input("Area", 0, 4294967295, 0)
                submitted_lab = st.form_submit_button("Apply OSPF")
            if submitted_lab:
                try:
                    normalized = str(ipaddress.ip_network(network, strict=False))
                    entry = {"device": device_name, "process_id": int(process_id), "network": normalized, "area": int(area)}
                    config["ospf"].append(entry)
                    append_cli(device_name, f"{device_name}(config)# router ospf {int(process_id)}")
                    append_cli(device_name, f"{device_name}(config-router)# network {normalized} area {int(area)}")
                    log(f"OSPF configured on {device_name}")
                    st.success("OSPF configuration added.")
                except ValueError:
                    st.error("Enter a valid IPv4 network in CIDR notation.")

        elif lab_type == "BGP":
            with st.form("bgp_lab_form", clear_on_submit=True):
                local_as = st.number_input("Local AS", 1, 4294967295, 65001)
                neighbor_ip = st.text_input("Neighbor IP", "172.16.0.2")
                remote_as = st.number_input("Remote AS", 1, 4294967295, 65002)
                submitted_lab = st.form_submit_button("Apply BGP")
            if submitted_lab:
                try:
                    neighbor = str(ipaddress.ip_address(neighbor_ip))
                    entry = {"device": device_name, "local_as": int(local_as), "neighbor": neighbor, "remote_as": int(remote_as)}
                    config["bgp"].append(entry)
                    append_cli(device_name, f"{device_name}(config)# router bgp {int(local_as)}")
                    append_cli(device_name, f"{device_name}(config-router)# neighbor {neighbor} remote-as {int(remote_as)}")
                    log(f"BGP neighbor configured on {device_name}")
                    st.success("BGP configuration added.")
                except ValueError:
                    st.error("Enter a valid neighbor IP.")

        elif lab_type == "ACL":
            with st.form("acl_lab_form", clear_on_submit=True):
                acl_name = st.text_input("ACL name", "BLOCK_GUEST")
                action = st.selectbox("Action", ["permit", "deny"])
                protocol = st.selectbox("Protocol", ["ip", "tcp", "udp", "icmp"])
                source = st.text_input("Source", "any")
                destination = st.text_input("Destination", "any")
                submitted_lab = st.form_submit_button("Apply ACL")
            if submitted_lab:
                entry = {
                    "device": device_name, "name": acl_name.strip(), "action": action,
                    "protocol": protocol, "source": source.strip(), "destination": destination.strip()
                }
                config["acls"].append(entry)
                append_cli(device_name, f"{device_name}(config)# ip access-list extended {acl_name.strip()}")
                append_cli(device_name, f"{device_name}(config-ext-nacl)# {action} {protocol} {source.strip()} {destination.strip()}")
                log(f"ACL {acl_name.strip()} configured on {device_name}")
                st.success("ACL configuration added.")

        elif lab_type == "NAT":
            with st.form("nat_lab_form", clear_on_submit=True):
                inside_network = st.text_input("Inside network/CIDR", "10.0.1.0/24")
                outside_interface = st.text_input("Outside interface", "Gi0/1")
                submitted_lab = st.form_submit_button("Apply NAT overload")
            if submitted_lab:
                try:
                    normalized = str(ipaddress.ip_network(inside_network, strict=False))
                    entry = {"device": device_name, "inside_network": normalized, "outside_interface": outside_interface.strip()}
                    config["nat"].append(entry)
                    append_cli(device_name, f"{device_name}(config)# access-list 1 permit {normalized}")
                    append_cli(device_name, f"{device_name}(config)# ip nat inside source list 1 interface {outside_interface.strip()} overload")
                    log(f"NAT overload configured on {device_name}")
                    st.success("NAT configuration added.")
                except ValueError:
                    st.error("Enter a valid inside network.")

        elif lab_type == "DHCP":
            with st.form("dhcp_lab_form", clear_on_submit=True):
                pool_name = st.text_input("Pool name", "LAN_POOL")
                network = st.text_input("Network/CIDR", "10.0.1.0/24")
                gateway = st.text_input("Default gateway", "10.0.1.1")
                submitted_lab = st.form_submit_button("Apply DHCP")
            if submitted_lab:
                try:
                    normalized = str(ipaddress.ip_network(network, strict=False))
                    gateway_ip = str(ipaddress.ip_address(gateway))
                    entry = {"device": device_name, "pool": pool_name.strip(), "network": normalized, "gateway": gateway_ip}
                    config["dhcp"].append(entry)
                    append_cli(device_name, f"{device_name}(config)# ip dhcp pool {pool_name.strip()}")
                    append_cli(device_name, f"{device_name}(dhcp-config)# network {normalized}")
                    append_cli(device_name, f"{device_name}(dhcp-config)# default-router {gateway_ip}")
                    log(f"DHCP pool configured on {device_name}")
                    st.success("DHCP configuration added.")
                except ValueError:
                    st.error("Enter a valid network and gateway.")

        else:
            with st.form("sdwan_lab_form", clear_on_submit=True):
                site_id = st.number_input("Site ID", 1, 999999, 100)
                system_ip = st.text_input("System IP", "1.1.1.1")
                color = st.selectbox("TLOC color", ["biz-internet", "mpls", "public-internet", "lte", "metro-ethernet"])
                role = st.selectbox("Role", ["vEdge", "cEdge", "vManage", "vSmart", "vBond"])
                submitted_lab = st.form_submit_button("Apply SD-WAN identity")
            if submitted_lab:
                try:
                    system = str(ipaddress.ip_address(system_ip))
                    entry = {"device": device_name, "site_id": int(site_id), "system_ip": system, "color": color, "role": role}
                    config["sdwan"].append(entry)
                    append_cli(device_name, f"{device_name}(config-system)# site-id {int(site_id)}")
                    append_cli(device_name, f"{device_name}(config-system)# system-ip {system}")
                    append_cli(device_name, f"{device_name}(config-tunnel-interface)# color {color}")
                    log(f"SD-WAN identity configured on {device_name}")
                    st.success("SD-WAN lab identity added.")
                except ValueError:
                    st.error("Enter a valid system IP.")

        st.divider()
        st.subheader("Configured lab objects")
        configured_count = sum(len(items) for items in config.values())
        if configured_count:
            st.json(config, expanded=False)
        else:
            st.info("No advanced lab configuration has been added yet.")

        st.markdown(
            """
            **Next roadmap**

            - Canvas drag-and-drop topology editor
            - Ethernet frame, ARP and packet-event engine
            - VLAN access/trunk forwarding and STP state calculation
            - OSPF adjacency and SPF route calculation
            - BGP neighbor state and best-path selection
            - NAT/ACL packet-policy evaluation
            - SD-WAN controller, TLOC, OMP and BFD state simulation
            - PeerNet AI configuration and troubleshooting assistant
            """
        )


with tabs[5]:
    interfaces = [
        (device.name, interface.name)
        for device in st.session_state.devices.values()
        for interface in device.interfaces.values()
    ]

    if interfaces:
        selected = st.selectbox(
            "Interface",
            interfaces,
            format_func=lambda value: f"{value[0]}:{value[1]}",
        )
        down_col, up_col = st.columns(2)

        with down_col:
            if st.button(
                "🔴 Shut Interface",
                use_container_width=True,
            ):
                st.session_state.devices[selected[0]].interfaces[
                    selected[1]
                ].status = "down"
                log(f"{selected[0]}:{selected[1]} down")
                st.rerun()

        with up_col:
            if st.button(
                "🟢 Restore Interface",
                use_container_width=True,
            ):
                st.session_state.devices[selected[0]].interfaces[
                    selected[1]
                ].status = "up"
                log(f"{selected[0]}:{selected[1]} up")
                st.rerun()
    else:
        st.info("Add interfaces to simulate failures.")

with tabs[6]:
    if st.session_state.events:
        for event in st.session_state.events:
            st.write(f"• {event}")
    else:
        st.info("No events yet.")

st.divider()
st.caption(
    "PeerNet Solutions Network Simulator • Logical simulation for learning, testing and demonstrations"
)
