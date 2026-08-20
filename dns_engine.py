"""Local host tables and topology-aware DNS resolution for PeerNet."""

from __future__ import annotations

import ipaddress
import re
from typing import Any, Iterable


HOSTNAME = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$")


def ensure_dns(device: Any) -> dict[str, str]:
    config = getattr(device, "routing_config", None)
    if not isinstance(config, dict):
        config = {}
        device.routing_config = config
    return config.setdefault("dns_records", {})


def configure_ip_host(device: Any, command: str) -> tuple[bool, str]:
    tokens = command.split()
    lowered = command.lower().strip()
    remove = lowered.startswith("no ip host ")
    if not (lowered.startswith("ip host ") or remove):
        return False, ""
    try:
        hostname_index = 3 if remove else 2
        hostname = tokens[hostname_index].lower()
        if not HOSTNAME.match(hostname):
            raise ValueError
        if remove:
            ensure_dns(device).pop(hostname, None)
        else:
            address = str(ipaddress.IPv4Address(tokens[hostname_index + 1]))
            ensure_dns(device)[hostname] = address
    except (IndexError, ValueError, ipaddress.AddressValueError):
        return True, "% Use: ip host <hostname> <IPv4-address>"
    return True, ""


def configure_server_record(device: Any, command: str) -> tuple[bool, str]:
    tokens = command.split()
    lowered = command.lower().strip()
    records = ensure_dns(device)
    if lowered == "dns show":
        return True, show_records(device)
    if lowered.startswith("dns add "):
        try:
            hostname = tokens[2].lower()
            address = str(ipaddress.IPv4Address(tokens[3]))
            if len(tokens) != 4 or not HOSTNAME.match(hostname):
                raise ValueError
        except (IndexError, ValueError, ipaddress.AddressValueError):
            return True, "Use: dns add <hostname> <IPv4-address>"
        records[hostname] = address
        return True, f"DNS record added: {hostname} → {address}"
    if lowered.startswith("dns remove "):
        if len(tokens) != 3:
            return True, "Use: dns remove <hostname>"
        records.pop(tokens[2].lower(), None)
        return True, f"DNS record removed: {tokens[2].lower()}"
    return False, ""


def _active_graph(devices: dict[str, Any], links: Iterable[dict]) -> dict[str, list[str]]:
    graph = {name: [] for name in devices}
    for link in links:
        if link.get("forced_down"):
            continue
        source, target = link.get("source"), link.get("target")
        if source in graph and target in graph:
            source_if = devices[source].interfaces.get(link.get("source_if"))
            target_if = devices[target].interfaces.get(link.get("target_if"))
            if source_if and getattr(source_if, "status", "up") != "up":
                continue
            if target_if and getattr(target_if, "status", "up") != "up":
                continue
            graph[source].append(target)
            graph[target].append(source)
    return graph


def _reachable(graph: dict[str, list[str]], source: str, target: str) -> bool:
    visited, queue = {source}, [source]
    while queue:
        current = queue.pop(0)
        if current == target:
            return True
        for neighbor in graph.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return False


def _owner_of_ip(devices: dict[str, Any], address: str) -> str:
    for name, device in devices.items():
        for interface in device.interfaces.values():
            try:
                if interface.ip_address and str(ipaddress.ip_interface(interface.ip_address).ip) == address:
                    return name
            except ValueError:
                pass
    return ""


def resolve_name(devices: dict[str, Any], links: Iterable[dict], source_name: str, query: str) -> tuple[bool, str, str]:
    try:
        return True, str(ipaddress.IPv4Address(query)), "literal IPv4 address"
    except ipaddress.AddressValueError:
        pass
    hostname = query.lower().rstrip(".")
    local = ensure_dns(devices[source_name]).get(hostname)
    if local:
        return True, local, "local host table"
    dns_server = getattr(devices[source_name], "dns_server", "")
    if not dns_server:
        return False, "", "DNS server is not configured."
    server_name = _owner_of_ip(devices, dns_server)
    if not server_name:
        return False, "", f"DNS server {dns_server} is not present in the topology."
    if not _reachable(_active_graph(devices, links), source_name, server_name):
        return False, "", f"DNS server {dns_server} is unreachable."
    address = ensure_dns(devices[server_name]).get(hostname)
    if not address:
        return False, "", f"DNS name does not exist: {query}"
    return True, address, server_name


def show_records(device: Any) -> str:
    records = ensure_dns(device)
    rows = ["Host                         Address"]
    rows.extend(f"{host:<28} {address}" for host, address in sorted(records.items()))
    return "\n".join(rows + ([] if records else ["No DNS records configured."]))


def dns_running_config(device: Any) -> list[str]:
    rows = [f"ip host {host} {address}" for host, address in sorted(ensure_dns(device).items())]
    return rows + (["!"] if rows else [])
