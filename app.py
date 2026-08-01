import streamlit as st
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import ipaddress

st.set_page_config(page_title="PeerNet Solutions", page_icon="🌐", layout="wide")

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

    def add_interface(self, name: str, ip_address: str = "") -> None:
        self.interfaces[name] = Interface(name=name, ip_address=ip_address)


def initialize_state() -> None:
    if "devices" not in st.session_state:
        st.session_state.devices = {}
    if "links" not in st.session_state:
        st.session_state.links = []
    if "events" not in st.session_state:
        st.session_state.events = []


def log(message: str) -> None:
    st.session_state.events.insert(0, message)


def add_device(name: str, device_type: str) -> str:
    name = name.strip()
    if not name:
        return "Device name is required."
    if name in st.session_state.devices:
        return f"Device {name} already exists."
    st.session_state.devices[name] = Device(name=name, device_type=device_type)
    log(f"Added {device_type}: {name}")
    return f"Added {device_type} {name}."


def add_interface(device_name: str, interface_name: str, ip_address: str) -> str:
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
    device.add_interface(interface_name, ip_address)
    log(f"Configured {device_name} {interface_name} {ip_address or 'without IP'}")
    return f"Interface {interface_name} added to {device_name}."


def connect_devices(device_a: str, interface_a: str, device_b: str, interface_b: str) -> str:
    if device_a == device_b:
        return "Select two different devices."
    dev_a = st.session_state.devices.get(device_a)
    dev_b = st.session_state.devices.get(device_b)
    if not dev_a or not dev_b:
        return "Both devices must exist."
    if interface_a not in dev_a.interfaces or interface_b not in dev_b.interfaces:
        return "Both interfaces must exist."
    link = (device_a, interface_a, device_b, interface_b)
    reverse = (device_b, interface_b, device_a, interface_a)
    if link in st.session_state.links or reverse in st.session_state.links:
        return "Link already exists."
    st.session_state.links.append(link)
    dev_a.interfaces[interface_a].connected_to = f"{device_b}:{interface_b}"
    dev_b.interfaces[interface_b].connected_to = f"{device_a}:{interface_a}"
    log(f"Connected {device_a}:{interface_a} ↔ {device_b}:{interface_b}")
    return "Link created successfully."


def network_of(cidr: str):
    try:
        return ipaddress.ip_interface(cidr).network
    except ValueError:
        return None


def simulate_ping(source: str, destination_ip: str) -> List[str]:
    destination_ip = destination_ip.strip()
    try:
        target = ipaddress.ip_address(destination_ip)
    except ValueError:
        return ["Invalid destination IP address."]

    devices = st.session_state.devices
    if source not in devices:
        return ["Source device not found."]

    destination_device = None
    for device in devices.values():
        for interface in device.interfaces.values():
            if interface.ip_address:
                try:
                    if ipaddress.ip_interface(interface.ip_address).ip == target:
                        destination_device = device.name
                        break
                except ValueError:
                    continue
        if destination_device:
            break

    if not destination_device:
        return [f"Destination {destination_ip} is not configured on any device."]

    adjacency: Dict[str, List[str]] = {name: [] for name in devices}
    for a, ia, b, ib in st.session_state.links:
        if devices[a].interfaces[ia].status == "up" and devices[b].interfaces[ib].status == "up":
            adjacency[a].append(b)
            adjacency[b].append(a)

    queue = [(source, [source])]
    visited = {source}
    while queue:
        current, path = queue.pop(0)
        if current == destination_device:
            log(f"Ping {source} → {destination_ip}: SUCCESS via {' → '.join(path)}")
            return [
                f"PING {destination_ip}",
                f"Reply from {destination_ip}: path={' → '.join(path)}",
                "Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)",
            ]
        for neighbor in adjacency[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    log(f"Ping {source} → {destination_ip}: FAILED")
    return [
        f"PING {destination_ip}",
        "Destination unreachable: no active path found.",
        "Packets: Sent = 4, Received = 0, Lost = 4 (100% loss)",
    ]


def show_ip_interface_brief(device: Device) -> str:
    lines = ["Interface              IP-Address        Status   Protocol"]
    for interface in device.interfaces.values():
        ip_value = interface.ip_address.split('/')[0] if interface.ip_address else "unassigned"
        protocol = "up" if interface.status == "up" and interface.connected_to else "down"
        lines.append(f"{interface.name:<22} {ip_value:<17} {interface.status:<8} {protocol}")
    return "\n".join(lines)


def show_topology() -> str:
    if not st.session_state.links:
        return "No links configured."
    return "\n".join(
        f"{a}:{ia} <--> {b}:{ib}" for a, ia, b, ib in st.session_state.links
    )


initialize_state()

st.title("🌐 PeerNet Solutions")
st.caption("Lightweight Network Simulator • Build, connect, test and troubleshoot virtual network devices")

with st.sidebar:
    st.header("Simulator Controls")
    if st.button("Load Demo Topology", use_container_width=True):
        st.session_state.devices = {}
        st.session_state.links = []
        st.session_state.events = []
        for name, dtype in [("PC1", "PC"), ("SW1", "Switch"), ("R1", "Router"), ("PC2", "PC")]:
            add_device(name, dtype)
        add_interface("PC1", "eth0", "10.0.1.10/24")
        add_interface("SW1", "Gi0/1", "")
        add_interface("SW1", "Gi0/2", "")
        add_interface("R1", "Gi0/0", "10.0.1.1/24")
        add_interface("R1", "Gi0/1", "10.0.2.1/24")
        add_interface("PC2", "eth0", "10.0.2.10/24")
        connect_devices("PC1", "eth0", "SW1", "Gi0/1")
        connect_devices("SW1", "Gi0/2", "R1", "Gi0/0")
        connect_devices("R1", "Gi0/1", "PC2", "eth0")
        st.success("Demo loaded")
    if st.button("Reset Simulator", use_container_width=True):
        st.session_state.devices = {}
        st.session_state.links = []
        st.session_state.events = []
        st.rerun()

col1, col2, col3 = st.columns(3)
col1.metric("Devices", len(st.session_state.devices))
col2.metric("Links", len(st.session_state.links))
col3.metric("Active Events", len(st.session_state.events))

tab1, tab2, tab3, tab4 = st.tabs(["Build Topology", "Ping Test", "CLI Console", "Event Log"])

with tab1:
    left, right = st.columns(2)
    with left:
        st.subheader("Add Device")
        with st.form("add_device_form"):
            device_name = st.text_input("Device name", placeholder="R1")
            device_type = st.selectbox("Device type", ["Router", "Switch", "PC"])
            submitted = st.form_submit_button("Add Device")
            if submitted:
                st.info(add_device(device_name, device_type))

        st.subheader("Add Interface")
        if st.session_state.devices:
            with st.form("add_interface_form"):
                selected_device = st.selectbox("Select device", list(st.session_state.devices), key="if_dev")
                interface_name = st.text_input("Interface name", placeholder="Gi0/0")
                interface_ip = st.text_input("IP address/CIDR", placeholder="10.0.0.1/24")
                submitted_if = st.form_submit_button("Add Interface")
                if submitted_if:
                    st.info(add_interface(selected_device, interface_name, interface_ip))
        else:
            st.warning("Add a device first.")

    with right:
        st.subheader("Create Link")
        candidates = [name for name, dev in st.session_state.devices.items() if dev.interfaces]
        if len(candidates) >= 2:
            dev_a = st.selectbox("Device A", candidates, key="dev_a")
            int_a = st.selectbox("Interface A", list(st.session_state.devices[dev_a].interfaces), key="int_a")
            dev_b = st.selectbox("Device B", candidates, index=1, key="dev_b")
            int_b = st.selectbox("Interface B", list(st.session_state.devices[dev_b].interfaces), key="int_b")
            if st.button("Connect Devices"):
                st.info(connect_devices(dev_a, int_a, dev_b, int_b))
        else:
            st.warning("At least two devices with interfaces are required.")

        st.subheader("Current Topology")
        st.code(show_topology(), language="text")

    st.subheader("Device Inventory")
    for device in st.session_state.devices.values():
        with st.expander(f"{device.device_type}: {device.name}"):
            if not device.interfaces:
                st.write("No interfaces configured.")
            for interface in device.interfaces.values():
                st.write(
                    f"**{interface.name}** — IP: `{interface.ip_address or 'unassigned'}` — "
                    f"Status: `{interface.status}` — Connected: `{interface.connected_to or 'No'}`"
                )

with tab2:
    st.subheader("Simulate Ping")
    if st.session_state.devices:
        source = st.selectbox("Source device", list(st.session_state.devices), key="ping_source")
        destination = st.text_input("Destination IP", placeholder="10.0.2.10")
        if st.button("Run Ping"):
            st.code("\n".join(simulate_ping(source, destination)), language="text")
    else:
        st.warning("Load the demo or build a topology.")

with tab3:
    st.subheader("Cisco-style CLI Console")
    if st.session_state.devices:
        cli_device_name = st.selectbox("Device", list(st.session_state.devices), key="cli_dev")
        command = st.selectbox(
            "Command",
            ["show ip interface brief", "show topology", "show running-config"],
        )
        if st.button("Execute Command"):
            device = st.session_state.devices[cli_device_name]
            if command == "show ip interface brief":
                output = show_ip_interface_brief(device)
            elif command == "show topology":
                output = show_topology()
            else:
                output_lines = [f"hostname {device.name}"]
                for interface in device.interfaces.values():
                    output_lines.extend([
                        f"interface {interface.name}",
                        f" ip address {interface.ip_address or 'unassigned'}",
                        f" {'no shutdown' if interface.status == 'up' else 'shutdown'}",
                    ])
                output = "\n".join(output_lines)
            st.code(output, language="text")
    else:
        st.warning("No devices available.")

with tab4:
    st.subheader("Simulation Events")
    if st.session_state.events:
        for event in st.session_state.events:
            st.write(f"• {event}")
    else:
        st.info("No events yet.")

st.divider()
st.caption("PeerNet Solutions Network Simulator • Suggested deployment URL: peernet-solutions.streamlit.app")
