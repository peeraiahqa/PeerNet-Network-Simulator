"""Cisco-style numbered IPv4 ACL configuration and packet filtering."""

from __future__ import annotations

import ipaddress
from typing import Any, Iterable


def ensure_acls(device: Any) -> dict[str, list[dict]]:
    config = getattr(device, "routing_config", None)
    if not isinstance(config, dict):
        config = {}
        device.routing_config = config
    return config.setdefault("access_lists", {})


def _address(tokens: list[str], index: int) -> tuple[dict, int]:
    if index >= len(tokens):
        raise ValueError
    if tokens[index].lower() == "any":
        return {"address": "0.0.0.0", "wildcard": "255.255.255.255"}, index + 1
    if tokens[index].lower() == "host" and index + 1 < len(tokens):
        return {"address": str(ipaddress.IPv4Address(tokens[index + 1])), "wildcard": "0.0.0.0"}, index + 2
    if index + 1 >= len(tokens):
        raise ValueError
    return {
        "address": str(ipaddress.IPv4Address(tokens[index])),
        "wildcard": str(ipaddress.IPv4Address(tokens[index + 1])),
    }, index + 2


def configure_access_list(device: Any, command: str) -> tuple[bool, str]:
    tokens = command.split()
    lowered = command.lower().strip()
    if lowered.startswith("no access-list "):
        if len(tokens) != 3:
            return True, "% Use: no access-list <number>"
        ensure_acls(device).pop(tokens[2], None)
        return True, ""
    if not lowered.startswith("access-list "):
        return False, ""
    try:
        number = int(tokens[1])
        action = tokens[2].lower()
        if action not in {"permit", "deny"} or not (1 <= number <= 199):
            raise ValueError
        rule = {"action": action, "hits": 0}
        if number <= 99:
            source, end = _address(tokens, 3)
            if end != len(tokens):
                raise ValueError
            rule.update({"type": "standard", "protocol": "ip", "source": source})
        else:
            protocol = tokens[3].lower()
            if protocol not in {"ip", "icmp", "tcp", "udp"}:
                raise ValueError
            source, index = _address(tokens, 4)
            destination, end = _address(tokens, index)
            if end != len(tokens):
                raise ValueError
            rule.update({"type": "extended", "protocol": protocol, "source": source, "destination": destination})
    except (IndexError, ValueError, ipaddress.AddressValueError):
        return True, "% Use standard ACL 1-99 or extended ACL 100-199 with permit/deny."
    ensure_acls(device).setdefault(str(number), []).append(rule)
    return True, ""


def configure_access_group(interfaces: list[Any], command: str) -> tuple[bool, str]:
    tokens = command.split()
    lowered = command.lower().strip()
    remove = lowered.startswith("no ip access-group ")
    if not (lowered.startswith("ip access-group ") or remove):
        return False, ""
    try:
        number_index = 3 if remove else 2
        number, direction = tokens[number_index], tokens[number_index + 1].lower()
        if direction not in {"in", "out"}:
            raise ValueError
    except (IndexError, ValueError):
        return True, "% Use: ip access-group <acl> {in|out}"
    attribute = f"access_group_{direction}"
    for interface in interfaces:
        setattr(interface, attribute, "" if remove else number)
    return True, ""


def _matches(ip_value: str, expression: dict) -> bool:
    ip_int = int(ipaddress.IPv4Address(ip_value))
    address = int(ipaddress.IPv4Address(expression["address"]))
    wildcard = int(ipaddress.IPv4Address(expression["wildcard"]))
    return (ip_int & ~wildcard) == (address & ~wildcard)


def _permit(device: Any, acl_name: str, source: str, destination: str, protocol: str) -> bool:
    rules = ensure_acls(device).get(str(acl_name), [])
    for rule in rules:
        if rule["protocol"] not in {"ip", protocol} or not _matches(source, rule["source"]):
            continue
        if rule["type"] == "extended" and not _matches(destination, rule["destination"]):
            continue
        rule["hits"] = int(rule.get("hits", 0)) + 1
        return rule["action"] == "permit"
    return False


def enforce_path_acls(devices: dict[str, Any], links: Iterable[dict], path: list[str], source: str, destination: str, protocol: str = "icmp") -> tuple[bool, str]:
    for previous, current in zip(path, path[1:]):
        link = next((item for item in links if {item.get("source"), item.get("target")} == {previous, current}), None)
        if not link:
            continue
        for device_name, direction in ((previous, "out"), (current, "in")):
            interface_name = link.get("source_if") if link.get("source") == device_name else link.get("target_if")
            interface = devices[device_name].interfaces.get(interface_name)
            acl_name = getattr(interface, f"access_group_{direction}", "") if interface else ""
            if acl_name and not _permit(devices[device_name], acl_name, source, destination, protocol):
                return False, f"ACL {acl_name} denied {protocol.upper()} on {device_name} {interface_name} {direction}bound"
    return True, ""


def acl_running_config(device: Any) -> list[str]:
    rows: list[str] = []
    for name, rules in ensure_acls(device).items():
        for rule in rules:
            src = _format_address(rule["source"])
            if rule["type"] == "standard":
                rows.append(f"access-list {name} {rule['action']} {src}")
            else:
                rows.append(f"access-list {name} {rule['action']} {rule['protocol']} {src} {_format_address(rule['destination'])}")
    return rows + (["!"] if rows else [])


def _format_address(value: dict) -> str:
    if value["address"] == "0.0.0.0" and value["wildcard"] == "255.255.255.255":
        return "any"
    if value["wildcard"] == "0.0.0.0":
        return f"host {value['address']}"
    return f"{value['address']} {value['wildcard']}"


def show_access_lists(device: Any) -> str:
    rows: list[str] = []
    for name, rules in ensure_acls(device).items():
        rows.append(f"IP {'standard' if int(name) <= 99 else 'extended'} access list {name}")
        for sequence, rule in enumerate(rules, 10):
            text = f"{sequence} {rule['action']} {rule['protocol']} {_format_address(rule['source'])}"
            if rule["type"] == "extended":
                text += f" {_format_address(rule['destination'])}"
            rows.append(f"    {text} ({rule.get('hits', 0)} matches)")
    return "\n".join(rows or ["No access lists configured."])
