"""Cisco-style Layer-2 switch commands for PeerNet Network Simulator."""

from __future__ import annotations

import re
from typing import Iterable


SWITCH_TYPES = {"Switch", "Multilayer Switch"}
DEFAULT_VLANS = {
    1: "default",
    1002: "fddi-default",
    1003: "token-ring-default",
    1004: "fddinet-default",
    1005: "trnet-default",
}


def is_switch(device) -> bool:
    return device.device_type in SWITCH_TYPES


def ensure_switch_defaults(device) -> None:
    """Backfill switch state for new devices and older saved projects."""
    if not is_switch(device):
        return

    if not getattr(device, "vlans", None):
        device.vlans = dict(DEFAULT_VLANS)
    else:
        device.vlans = {int(vlan): name for vlan, name in device.vlans.items()}
        for vlan, name in DEFAULT_VLANS.items():
            device.vlans.setdefault(vlan, name)

    for interface in device.interfaces.values():
        if interface.name.lower().startswith("vlan"):
            continue
        interface.switchport_mode = getattr(interface, "switchport_mode", "access")
        interface.access_vlan = int(getattr(interface, "access_vlan", 1))
        interface.native_vlan = int(getattr(interface, "native_vlan", 1))
        allowed = getattr(interface, "trunk_allowed_vlans", [])
        interface.trunk_allowed_vlans = [int(vlan) for vlan in allowed]
        interface.description = getattr(interface, "description", "")


def validate_vlan_id(value: str) -> tuple[int | None, str | None]:
    try:
        vlan_id = int(value)
    except ValueError:
        return None, "% VLAN ID must be a number from 1 to 4094."

    if not 1 <= vlan_id <= 4094:
        return None, "% VLAN ID must be from 1 to 4094."
    return vlan_id, None


def parse_vlan_list(value: str) -> tuple[list[int] | None, str | None]:
    """Parse Cisco VLAN lists such as 10,20,30-40."""
    vlan_ids: set[int] = set()
    value = value.strip()
    if not value:
        return None, "% VLAN list is required."

    for part in value.split(","):
        part = part.strip()
        if not part:
            return None, "% Invalid VLAN list."
        if "-" in part:
            bounds = part.split("-", 1)
            start, start_error = validate_vlan_id(bounds[0].strip())
            end, end_error = validate_vlan_id(bounds[1].strip())
            if start_error or end_error or start is None or end is None or start > end:
                return None, f"% Invalid VLAN range: {part}"
            vlan_ids.update(range(start, end + 1))
        else:
            vlan_id, error = validate_vlan_id(part)
            if error or vlan_id is None:
                return None, error
            vlan_ids.add(vlan_id)

    return sorted(vlan_ids), None


def _interface_parts(name: str) -> tuple[str, int] | None:
    match = re.fullmatch(r"(.+?)(\d+)", name)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def _normalize_interface_name(name: str) -> str:
    name = name.strip()
    lowered = name.lower()
    aliases = (
        ("fastethernet", "Fa"),
        ("fast", "Fa"),
        ("fa", "Fa"),
        ("f", "Fa"),
        ("gigabitethernet", "Gi"),
        ("gigabit", "Gi"),
        ("gi", "Gi"),
        ("g", "Gi"),
    )
    for prefix, canonical in aliases:
        if lowered.startswith(prefix):
            suffix = name[len(prefix):]
            if suffix and (suffix[0].isdigit() or suffix[0] == "/"):
                return canonical + suffix
    return name


def _stored_interface_name(device, requested: str) -> str | None:
    normalized = _normalize_interface_name(requested)
    return next(
        (name for name in device.interfaces if name.lower() == normalized.lower()),
        None,
    )


def resolve_interface_range(device, expression: str) -> tuple[list[str] | None, str | None]:
    """Resolve Fa0/1-4, Fa0/1-Fa0/4, or comma-separated ranges."""
    selected: list[str] = []
    for item in expression.split(","):
        item = item.strip()
        if not item:
            return None, "% Invalid interface range."

        if " - " in item:
            start_name, end_name = (part.strip() for part in item.split(" - ", 1))
        elif "-" in item:
            start_name, end_name = (part.strip() for part in item.split("-", 1))
        else:
            start_name = end_name = item

        start_name = _normalize_interface_name(start_name)
        start_parts = _interface_parts(start_name)
        if not start_parts:
            return None, f"% Invalid interface name: {start_name}"
        prefix, start_number = start_parts

        if end_name.isdigit():
            end_name = f"{prefix}{end_name}"
        else:
            end_name = _normalize_interface_name(end_name)
        end_parts = _interface_parts(end_name)
        if not end_parts or end_parts[0] != prefix or end_parts[1] < start_number:
            return None, f"% Invalid interface range: {item}"

        for number in range(start_number, end_parts[1] + 1):
            candidate = f"{prefix}{number}"
            stored_name = _stored_interface_name(device, candidate)
            if stored_name is None:
                return None, f"% Interface {candidate} does not exist."
            if stored_name not in selected:
                selected.append(stored_name)

    return selected, None


def configure_switchports(device, interface_names: Iterable[str], command: str) -> tuple[bool, str | None]:
    """Apply one interface-mode switchport command to all selected ports."""
    if not is_switch(device):
        return False, None
    ensure_switch_defaults(device)
    lowered = command.lower().strip()
    interfaces = [device.interfaces[name] for name in interface_names]

    if lowered == "switchport mode access":
        for interface in interfaces:
            interface.switchport_mode = "access"
        return True, None

    if lowered == "switchport mode trunk":
        for interface in interfaces:
            interface.switchport_mode = "trunk"
        return True, None

    if lowered.startswith("switchport access vlan "):
        vlan_id, error = validate_vlan_id(command.split()[-1])
        if error or vlan_id is None:
            return True, error
        if vlan_id not in device.vlans:
            return True, f"% Access VLAN {vlan_id} does not exist. Create it first."
        for interface in interfaces:
            interface.access_vlan = vlan_id
        return True, None

    if lowered.startswith("switchport trunk native vlan "):
        vlan_id, error = validate_vlan_id(command.split()[-1])
        if error or vlan_id is None:
            return True, error
        if vlan_id not in device.vlans:
            return True, f"% Native VLAN {vlan_id} does not exist. Create it first."
        for interface in interfaces:
            interface.native_vlan = vlan_id
        return True, None

    prefix = "switchport trunk allowed vlan "
    if lowered.startswith(prefix):
        value = command[len(prefix):].strip()
        operation = "replace"
        for candidate in ("add", "remove", "except"):
            if value.lower().startswith(candidate + " "):
                operation = candidate
                value = value[len(candidate):].strip()
                break

        if value.lower() == "all":
            vlan_ids = []
        elif value.lower() == "none":
            vlan_ids = [-1]
        else:
            vlan_ids, error = parse_vlan_list(value)
            if error or vlan_ids is None:
                return True, error
            missing = [vlan for vlan in vlan_ids if vlan not in device.vlans]
            if missing:
                return True, "% VLAN(s) do not exist: " + ", ".join(map(str, missing))

        for interface in interfaces:
            current = set(interface.trunk_allowed_vlans)
            if operation == "add":
                current.update(vlan_ids)
            elif operation == "remove":
                if not current:
                    current = set(device.vlans)
                current.difference_update(vlan_ids)
            elif operation == "except":
                current = set(device.vlans).difference(vlan_ids)
            else:
                current = set(vlan_ids)
            interface.trunk_allowed_vlans = sorted(current)
        return True, None

    if lowered == "no switchport access vlan":
        for interface in interfaces:
            interface.access_vlan = 1
        return True, None

    if lowered == "no switchport trunk native vlan":
        for interface in interfaces:
            interface.native_vlan = 1
        return True, None

    if lowered == "no switchport trunk allowed vlan":
        for interface in interfaces:
            interface.trunk_allowed_vlans = []
        return True, None

    if lowered.startswith("description "):
        description = command.split(maxsplit=1)[1].strip()
        for interface in interfaces:
            interface.description = description
        return True, None

    if lowered == "no description":
        for interface in interfaces:
            interface.description = ""
        return True, None

    return False, None


def allowed_vlan_text(interface) -> str:
    allowed = interface.trunk_allowed_vlans
    if not allowed:
        return "all"
    if allowed == [-1]:
        return "none"
    return ",".join(map(str, allowed))


def show_vlan_brief(device) -> str:
    ensure_switch_defaults(device)
    lines = [
        "VLAN Name                             Status    Ports",
        "---- -------------------------------- --------- -------------------------------",
    ]
    for vlan_id, vlan_name in sorted(device.vlans.items()):
        ports = [
            interface.name
            for interface in device.interfaces.values()
            if not interface.name.lower().startswith("vlan")
            and interface.switchport_mode == "access"
            and interface.access_vlan == vlan_id
        ]
        status = "act/unsup" if vlan_id in range(1002, 1006) else "active"
        lines.append(
            f"{vlan_id:<4} {vlan_name:<32} {status:<9} {', '.join(ports)}"
        )
    return "\n".join(lines)


def show_interfaces_status(device) -> str:
    ensure_switch_defaults(device)
    lines = ["Port          Name        Status       Vlan       Duplex  Speed  Type"]
    for interface in device.interfaces.values():
        connected = "connected" if interface.connected_to else "notconnect"
        vlan = "trunk" if interface.switchport_mode == "trunk" else str(interface.access_vlan)
        name = interface.description[:10] or "--"
        lines.append(
            f"{interface.name:<13} {name:<11} {connected:<12} "
            f"{vlan:<10} auto    auto   virtual"
        )
    return "\n".join(lines)


def show_interfaces_trunk(device) -> str:
    ensure_switch_defaults(device)
    trunks = [
        interface for interface in device.interfaces.values()
        if interface.switchport_mode == "trunk"
    ]
    if not trunks:
        return "No operational trunk ports found."
    lines = [
        "Port        Mode         Encapsulation  Status        Native vlan",
    ]
    for interface in trunks:
        status = "trunking" if interface.status == "up" else "not-trunking"
        lines.append(
            f"{interface.name:<11} on           802.1q         {status:<13} {interface.native_vlan}"
        )
    lines.extend(["", "Port        Vlans allowed on trunk"])
    for interface in trunks:
        lines.append(f"{interface.name:<11} {allowed_vlan_text(interface)}")
    return "\n".join(lines)


def show_interface_switchport(device, interface_name: str) -> str:
    ensure_switch_defaults(device)
    interface = device.interfaces.get(interface_name)
    if interface is None:
        return f"% Invalid interface '{interface_name}'."
    trunk = interface.switchport_mode == "trunk"
    return (
        f"Name: {interface.name}\n"
        "Switchport: Enabled\n"
        f"Administrative Mode: static {'trunk' if trunk else 'access'}\n"
        f"Operational Mode: {'trunk' if trunk else 'static access'}\n"
        f"Access Mode VLAN: {interface.access_vlan} ({device.vlans.get(interface.access_vlan, 'inactive')})\n"
        f"Trunking Native Mode VLAN: {interface.native_vlan}\n"
        f"Trunking VLANs Enabled: {allowed_vlan_text(interface)}"
    )
