"""Configuration validation for PeerNet Network Simulator."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationIssue:
    severity: str
    device: str
    interface: str
    message: str


def _ipv4_interface(value: str):
    try:
        parsed = ipaddress.ip_interface(value)
    except ValueError:
        return None
    return parsed if parsed.version == 4 else None


def validate_interface_address(
    devices: dict[str, Any],
    device_name: str,
    interface_name: str,
    cidr: str,
) -> tuple[bool, str]:
    parsed = _ipv4_interface(cidr)
    if parsed is None:
        return False, "% Invalid IPv4 address or subnet mask."
    if parsed.network.prefixlen <= 30 and parsed.ip in {
        parsed.network.network_address,
        parsed.network.broadcast_address,
    }:
        return False, f"% {parsed.ip} is a network or broadcast address."

    for other_device_name, device in devices.items():
        for other_interface_name, interface in device.interfaces.items():
            if (
                other_device_name == device_name
                and other_interface_name == interface_name
            ):
                continue
            other = _ipv4_interface(getattr(interface, "ip_address", ""))
            if other and other.ip == parsed.ip:
                return (
                    False,
                    f"% Duplicate IP {parsed.ip} is already configured on "
                    f"{other_device_name}:{other_interface_name}.",
                )
    return True, ""


def validate_gateway(device: Any, gateway: str) -> tuple[bool, str]:
    try:
        gateway_ip = ipaddress.ip_address(gateway)
    except ValueError:
        return False, "% Invalid default gateway address."
    networks = [
        parsed.network
        for parsed in (
            _ipv4_interface(getattr(interface, "ip_address", ""))
            for interface in device.interfaces.values()
        )
        if parsed
    ]
    if networks and not any(gateway_ip in network for network in networks):
        return False, f"% Default gateway {gateway} is outside all local subnets."
    return True, ""


def audit_topology(devices: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    addresses: dict[str, tuple[str, str]] = {}
    networks: list[tuple[str, str, ipaddress.IPv4Network]] = []

    for device_name, device in devices.items():
        for interface_name, interface in device.interfaces.items():
            parsed = _ipv4_interface(getattr(interface, "ip_address", ""))
            if not parsed:
                continue
            address = str(parsed.ip)
            if address in addresses:
                owner_device, owner_interface = addresses[address]
                issues.append(ValidationIssue(
                    "error", device_name, interface_name,
                    f"Duplicate IP {address}; also used by "
                    f"{owner_device}:{owner_interface}.",
                ))
            else:
                addresses[address] = (device_name, interface_name)
            if parsed.network.prefixlen <= 30 and parsed.ip in {
                parsed.network.network_address,
                parsed.network.broadcast_address,
            }:
                issues.append(ValidationIssue(
                    "error", device_name, interface_name,
                    f"{address} is a network or broadcast address.",
                ))
            networks.append((device_name, interface_name, parsed.network))

        gateway = getattr(device, "default_gateway", "")
        if gateway:
            ok, message = validate_gateway(device, gateway)
            if not ok:
                issues.append(ValidationIssue(
                    "error", device_name, "gateway", message.lstrip("% "),
                ))

        vlans = getattr(device, "vlans", {}) or {}
        if getattr(device, "device_type", "") in {"Switch", "Multilayer Switch"}:
            for interface_name, interface in device.interfaces.items():
                mode = getattr(interface, "switchport_mode", "access")
                if mode == "access" and getattr(interface, "access_vlan", 1) not in vlans:
                    issues.append(ValidationIssue(
                        "warning", device_name, interface_name,
                        f"Access VLAN {interface.access_vlan} is not created.",
                    ))
                if mode == "trunk":
                    referenced = {getattr(interface, "native_vlan", 1)} | set(
                        getattr(interface, "trunk_allowed_vlans", [])
                    )
                    missing = sorted(vlan for vlan in referenced if vlan not in vlans)
                    if missing:
                        issues.append(ValidationIssue(
                            "warning", device_name, interface_name,
                            "Trunk references missing VLANs: "
                            + ",".join(map(str, missing)),
                        ))

        subinterface_vlans: dict[tuple[str, int], str] = {}
        for interface_name, interface in device.interfaces.items():
            if "." not in interface_name:
                continue
            vlan = getattr(interface, "encapsulation_dot1q", None)
            if vlan is None:
                issues.append(ValidationIssue(
                    "error", device_name, interface_name,
                    "Router subinterface has no encapsulation dot1Q VLAN.",
                ))
                continue
            parent = interface_name.rsplit(".", 1)[0]
            key = (parent, vlan)
            if key in subinterface_vlans:
                issues.append(ValidationIssue(
                    "error", device_name, interface_name,
                    f"Duplicate dot1Q VLAN {vlan} on {parent}; also used by "
                    f"{subinterface_vlans[key]}.",
                ))
            else:
                subinterface_vlans[key] = interface_name

    for index, (dev_a, if_a, net_a) in enumerate(networks):
        for dev_b, if_b, net_b in networks[index + 1:]:
            if net_a == net_b or not net_a.overlaps(net_b):
                continue
            issues.append(ValidationIssue(
                "warning", dev_b, if_b,
                f"Overlapping prefixes {net_a} ({dev_a}:{if_a}) and {net_b}.",
            ))

    return issues


def audit_device(
    devices: dict[str, Any],
    links: list[dict[str, Any]],
    device_name: str,
) -> tuple[list[ValidationIssue], list[str]]:
    """Return configuration issues and readiness successes for one device."""
    if device_name not in devices:
        return [ValidationIssue(
            "error", device_name, "device", "Device does not exist."
        )], []

    device = devices[device_name]
    issues = [
        issue for issue in audit_topology(devices)
        if issue.device == device_name
    ]
    interfaces = getattr(device, "interfaces", {}) or {}
    device_type = getattr(device, "device_type", "Device")

    active_connected: set[str] = set()
    failed_links = 0
    for link in links:
        endpoint_interface = ""
        if str(link.get("source", "")) == device_name:
            endpoint_interface = str(link.get("source_if") or "")
        elif str(link.get("target", "")) == device_name:
            endpoint_interface = str(link.get("target_if") or "")
        else:
            continue

        interface = interfaces.get(endpoint_interface)
        is_active = str(getattr(interface, "status", "up")).lower() not in {
            "down", "administratively down", "disabled"
        }
        if link.get("forced_down") or not is_active:
            failed_links += 1
        else:
            active_connected.add(endpoint_interface)

    if not active_connected:
        detail = (
            "has connections, but none are operational."
            if failed_links
            else "is not connected to any topology device."
        )
        issues.append(ValidationIssue(
            "warning", device_name, "connectivity", f"{device_name} {detail}"
        ))

    configured_ipv4 = {
        name: parsed
        for name, interface in interfaces.items()
        for parsed in [_ipv4_interface(getattr(interface, "ip_address", ""))]
        if parsed
    }

    # A pure Layer-2 switch forwards frames without an interface IPv4 address.
    if device_type != "Switch":
        if not configured_ipv4:
            issues.append(ValidationIssue(
                "warning", device_name, "addressing",
                f"{device_name} has no configured IPv4 address.",
            ))
        for interface_name in sorted(active_connected):
            if interface_name not in configured_ipv4:
                issues.append(ValidationIssue(
                    "warning", device_name, interface_name,
                    "Connected interface has no configured IPv4 address.",
                ))

    end_host_types = {
        "PC", "Laptop", "Server", "Authentication Server",
        "Camera / PC Video", "IP Phone",
    }
    if device_type in end_host_types and configured_ipv4 and active_connected:
        configured_names = set(configured_ipv4)
        if configured_names.isdisjoint(active_connected):
            issues.append(ValidationIssue(
                "error", device_name, "addressing",
                "The IPv4 address is configured on a disconnected adapter; "
                "move it to the active connected interface.",
            ))

    successes: list[str] = []
    if not issues:
        connection_count = len(active_connected)
        if device_type == "Switch":
            successes.append(
                f"{device_name} passed validation as a Layer 2 switch: "
                f"{connection_count} active connection(s); interface IP is optional."
            )
        else:
            successes.append(
                f"{device_name} passed configuration validation: "
                f"{connection_count} active connection(s) and "
                f"{len(configured_ipv4)} configured IPv4 interface(s)."
            )

    return issues, successes
