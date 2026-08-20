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

