"""NAT/PAT configuration and translation tracking for PeerNet."""

from __future__ import annotations

import ipaddress
from typing import Any


def ensure_nat(device: Any) -> dict:
    config = getattr(device, "routing_config", None)
    if not isinstance(config, dict):
        config = {}
        device.routing_config = config
    nat = config.setdefault("nat", {})
    nat.setdefault("static", [])
    nat.setdefault("overload", [])
    nat.setdefault("translations", [])
    return nat


def configure_nat_global(device: Any, command: str) -> tuple[bool, str]:
    tokens = command.split()
    lowered = command.lower().strip()
    remove = lowered.startswith("no ip nat inside source ")
    values = tokens[1:] if remove else tokens
    if not (lowered.startswith("ip nat inside source ") or remove):
        return False, ""
    nat = ensure_nat(device)
    try:
        if values[4].lower() == "static":
            local = str(ipaddress.IPv4Address(values[5]))
            global_ip = str(ipaddress.IPv4Address(values[6]))
            entry = {"local": local, "global": global_ip}
            if remove:
                nat["static"] = [item for item in nat["static"] if item != entry]
            elif entry not in nat["static"]:
                nat["static"].append(entry)
            return True, ""
        if values[4].lower() == "list" and values[6].lower() == "interface" and values[-1].lower() == "overload":
            entry = {"acl": values[5], "interface": values[7]}
            if remove:
                nat["overload"] = [item for item in nat["overload"] if item != entry]
            elif entry not in nat["overload"]:
                nat["overload"].append(entry)
            return True, ""
    except (IndexError, ValueError, ipaddress.AddressValueError):
        pass
    return True, "% Use static NAT or 'ip nat inside source list <acl> interface <name> overload'."


def configure_nat_interface(interfaces: list[Any], command: str) -> tuple[bool, str]:
    lowered = command.lower().strip()
    mapping = {
        "ip nat inside": ("nat_inside", True),
        "no ip nat inside": ("nat_inside", False),
        "ip nat outside": ("nat_outside", True),
        "no ip nat outside": ("nat_outside", False),
    }
    if lowered not in mapping:
        return False, ""
    attribute, value = mapping[lowered]
    for interface in interfaces:
        setattr(interface, attribute, value)
    return True, ""


def translate_destination(devices: dict[str, Any], destination: str) -> tuple[str, str]:
    for name, device in devices.items():
        for entry in ensure_nat(device)["static"]:
            if entry["global"] == destination:
                _record(device, "icmp", entry["global"], entry["local"], destination, entry["local"], "static")
                return entry["local"], f"{name}: static NAT {entry['global']} → {entry['local']}"
    return destination, ""


def _source_permitted(device: Any, acl_name: str, source: str) -> bool:
    rules = (getattr(device, "routing_config", {}) or {}).get("access_lists", {}).get(str(acl_name), [])
    value = int(ipaddress.IPv4Address(source))
    for rule in rules:
        expression = rule["source"]
        address = int(ipaddress.IPv4Address(expression["address"]))
        wildcard = int(ipaddress.IPv4Address(expression["wildcard"]))
        if (value & ~wildcard) == (address & ~wildcard):
            return rule["action"] == "permit"
    return False


def record_source_translation(devices: dict[str, Any], path: list[str], source: str, destination: str) -> str:
    for name in path:
        device = devices[name]
        nat = ensure_nat(device)
        for rule in nat["overload"]:
            interface = device.interfaces.get(rule["interface"])
            if not interface or not getattr(interface, "ip_address", "") or not _source_permitted(device, rule["acl"], source):
                continue
            global_ip = str(ipaddress.ip_interface(interface.ip_address).ip)
            _record(device, "icmp", global_ip, source, destination, destination, "dynamic overload")
            return f"{name}: PAT {source} → {global_ip} using {rule['interface']}"
    return ""


def _record(device: Any, protocol: str, inside_global: str, inside_local: str, outside_local: str, outside_global: str, kind: str) -> None:
    entry = {
        "protocol": protocol,
        "inside_global": inside_global,
        "inside_local": inside_local,
        "outside_local": outside_local,
        "outside_global": outside_global,
        "type": kind,
    }
    translations = ensure_nat(device)["translations"]
    if entry not in translations:
        translations.append(entry)


def clear_translations(device: Any) -> None:
    ensure_nat(device)["translations"] = []


def show_translations(device: Any) -> str:
    rows = ["Pro  Inside global      Inside local       Outside local      Outside global"]
    for item in ensure_nat(device)["translations"]:
        rows.append(
            f"{item['protocol']:<4} {item['inside_global']:<18} {item['inside_local']:<18} "
            f"{item['outside_local']:<18} {item['outside_global']}"
        )
    return "\n".join(rows + ([] if len(rows) > 1 else ["No active translations."]))


def show_statistics(device: Any) -> str:
    nat = ensure_nat(device)
    inside = [item.name for item in device.interfaces.values() if getattr(item, "nat_inside", False)]
    outside = [item.name for item in device.interfaces.values() if getattr(item, "nat_outside", False)]
    return (
        f"Total active translations: {len(nat['translations'])}\n"
        f"Static mappings: {len(nat['static'])}\n"
        f"Inside interfaces: {', '.join(inside) or 'none'}\n"
        f"Outside interfaces: {', '.join(outside) or 'none'}"
    )


def nat_running_config(device: Any) -> list[str]:
    nat = ensure_nat(device)
    rows = [f"ip nat inside source static {item['local']} {item['global']}" for item in nat["static"]]
    rows.extend(f"ip nat inside source list {item['acl']} interface {item['interface']} overload" for item in nat["overload"])
    return rows + (["!"] if rows else [])
