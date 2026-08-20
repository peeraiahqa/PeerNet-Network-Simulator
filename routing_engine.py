"""Packet forwarding decisions for PeerNet Network Simulator.

This module has no Streamlit dependency.  It evaluates configured interfaces,
active topology links, static/default routes, and advertised IGP/BGP networks.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Any, Iterable

from acl_engine import enforce_path_acls
from nat_engine import record_source_translation, translate_destination


ROUTING_TYPES = {"Router", "Multilayer Switch", "Router/Switch Processor"}


@dataclass
class RouteDecision:
    reachable: bool
    path: list[str] = field(default_factory=list)
    reason: str = ""
    decisions: list[str] = field(default_factory=list)
    protocol: str = ""


def _interface_ipv4(interface: Any):
    value = getattr(interface, "ip_address", "")
    if not value:
        return None
    try:
        parsed = ipaddress.ip_interface(value)
    except ValueError:
        return None
    return parsed if parsed.version == 4 else None


def _active(interface: Any) -> bool:
    return str(getattr(interface, "status", "up")).lower() not in {
        "down", "administratively down", "disabled"
    }


def device_for_ip(devices: dict[str, Any], ip_value: str) -> str | None:
    try:
        target = ipaddress.ip_address(ip_value)
    except ValueError:
        return None
    for name, device in devices.items():
        for interface in getattr(device, "interfaces", {}).values():
            parsed = _interface_ipv4(interface)
            if parsed and parsed.ip == target:
                return name
    return None


def source_owns_ip(device: Any, source_ip: str) -> bool:
    try:
        source = ipaddress.ip_address(source_ip)
    except ValueError:
        return False
    return any(
        parsed and parsed.ip == source and _active(interface)
        for interface in getattr(device, "interfaces", {}).values()
        for parsed in [_interface_ipv4(interface)]
    )


def _link_endpoints(link: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(link.get("source", "")),
        str(link.get("source_if") or ""),
        str(link.get("target", "")),
        str(link.get("target_if") or ""),
    )


def active_adjacency(
    devices: dict[str, Any],
    links: Iterable[dict[str, Any]],
) -> dict[str, list[str]]:
    adjacency = {name: [] for name in devices}
    for link in links:
        if link.get("forced_down"):
            continue
        source, source_if, target, target_if = _link_endpoints(link)
        if source not in devices or target not in devices:
            continue
        source_interface = getattr(devices[source], "interfaces", {}).get(source_if)
        target_interface = getattr(devices[target], "interfaces", {}).get(target_if)
        if source_interface is not None and not _active(source_interface):
            continue
        if target_interface is not None and not _active(target_interface):
            continue
        adjacency[source].append(target)
        adjacency[target].append(source)
    return adjacency


def _shortest_path(adjacency: dict[str, list[str]], source: str, target: str) -> list[str]:
    if source == target:
        return [source]
    queue = [(source, [source])]
    visited = {source}
    while queue:
        node, path = queue.pop(0)
        for neighbor in adjacency.get(node, []):
            if neighbor in visited:
                continue
            candidate = path + [neighbor]
            if neighbor == target:
                return candidate
            visited.add(neighbor)
            queue.append((neighbor, candidate))
    return []


def _connected_routes(device: Any) -> list[ipaddress.IPv4Network]:
    routes = []
    for interface in getattr(device, "interfaces", {}).values():
        parsed = _interface_ipv4(interface)
        if parsed and _active(interface):
            routes.append(parsed.network)
    return routes


def _static_route(device: Any, destination) -> tuple[ipaddress.IPv4Network, str] | None:
    matches = []
    for prefix, next_hop in getattr(device, "routing_table", {}).items():
        try:
            network = ipaddress.ip_network(prefix, strict=False)
        except ValueError:
            continue
        if network.version == 4 and destination in network:
            distance = getattr(device, "route_distances", {}).get(prefix, 1)
            matches.append((network.prefixlen, -int(distance), network, next_hop))
    if not matches:
        return None
    _, _, network, next_hop = max(matches, key=lambda item: (item[0], item[1]))
    return network, str(next_hop)


def _protocol_networks(device: Any) -> dict[str, list[ipaddress.IPv4Network]]:
    config = getattr(device, "routing_config", {}) or {}
    result: dict[str, list[ipaddress.IPv4Network]] = {
        "rip": [], "ospf": [], "eigrp": [], "bgp": []
    }

    def add(protocol: str, value: str) -> None:
        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError:
            return
        if network.version == 4 and network not in result[protocol]:
            result[protocol].append(network)

    for value in (config.get("rip") or {}).get("networks", []):
        add("rip", value)
    for protocol in ("ospf", "eigrp", "bgp"):
        for process in (config.get(protocol) or {}).values():
            for entry in process.get("networks", []):
                value = entry if isinstance(entry, str) else entry.get("prefix", "")
                add(protocol, value)
            for statement in process.get("redistribute", []):
                if statement.split()[0].lower() == "connected":
                    for network in _connected_routes(device):
                        add(protocol, str(network))
    return result


def _enabled_protocols(device: Any) -> set[str]:
    config = getattr(device, "routing_config", {}) or {}
    enabled = set()
    if config.get("rip"):
        enabled.add("rip")
    for protocol in ("ospf", "eigrp", "bgp"):
        if config.get(protocol):
            enabled.add(protocol)
    return enabled


def _dynamic_route(
    current_name: str,
    devices: dict[str, Any],
    destination,
) -> tuple[ipaddress.IPv4Network, str, str] | None:
    current = devices[current_name]
    enabled = _enabled_protocols(current)
    matches = []
    preference = {"ospf": 110, "eigrp": 90, "rip": 120, "bgp": 20}
    for owner_name, owner in devices.items():
        if owner_name == current_name:
            continue
        advertised = _protocol_networks(owner)
        owner_enabled = _enabled_protocols(owner)
        for protocol in enabled & owner_enabled:
            for network in advertised[protocol]:
                if destination in network:
                    matches.append(
                        (network.prefixlen, -preference[protocol], network, protocol, owner_name)
                    )
    if not matches:
        return None
    _, _, network, protocol, owner = max(matches, key=lambda item: (item[0], item[1]))
    return network, protocol, owner


def _is_router(device: Any) -> bool:
    if getattr(device, "device_type", "") not in ROUTING_TYPES:
        return False
    config = getattr(device, "routing_config", {}) or {}
    if getattr(device, "device_type", "") == "Multilayer Switch":
        return bool(config.get("ip_routing", False))
    return True


def _host_can_send(device: Any, source_ip: str, destination, devices: dict[str, Any]) -> tuple[bool, str]:
    source_interface = None
    for interface in getattr(device, "interfaces", {}).values():
        parsed = _interface_ipv4(interface)
        if parsed and str(parsed.ip) == source_ip and _active(interface):
            source_interface = parsed
            break
    if source_interface is None:
        return False, "source interface is missing or down"
    if destination in source_interface.network:
        return True, "destination is on the local subnet"
    gateway = getattr(device, "default_gateway", "")
    if not gateway:
        return False, "no default gateway is configured"
    gateway_owner = device_for_ip(devices, gateway)
    if not gateway_owner:
        return False, f"default gateway {gateway} is not configured in the topology"
    return True, f"forward to default gateway {gateway}"


def evaluate_route(
    source_name: str,
    source_ip: str,
    destination_ip: str,
    devices: dict[str, Any],
    links: Iterable[dict[str, Any]],
) -> RouteDecision:
    """Evaluate an IPv4 forwarding path and explain every routing decision."""
    if source_name not in devices:
        return RouteDecision(False, reason="Source device does not exist.")
    original_destination = destination_ip
    destination_ip, nat_destination_decision = translate_destination(devices, destination_ip)
    try:
        destination = ipaddress.ip_address(destination_ip)
    except ValueError:
        return RouteDecision(False, reason=f"Invalid destination IP: {destination_ip}")
    if destination.version != 4:
        return RouteDecision(False, reason="IPv6 forwarding is not enabled in this engine phase.")
    if not source_owns_ip(devices[source_name], source_ip):
        return RouteDecision(False, reason=f"{source_name} does not own source IP {source_ip}.")

    destination_name = device_for_ip(devices, destination_ip)
    if not destination_name:
        return RouteDecision(False, reason="Destination IP is not configured on any topology device.")

    adjacency = active_adjacency(devices, links)
    path = _shortest_path(adjacency, source_name, destination_name)
    if not path:
        return RouteDecision(False, reason="No active physical path exists to the destination.")

    decisions = [nat_destination_decision] if nat_destination_decision else []
    source_device = devices[source_name]
    if not _is_router(source_device):
        allowed, detail = _host_can_send(
            source_device, source_ip, destination, devices
        )
        decisions.append(f"{source_name}: {detail}")
        if not allowed:
            return RouteDecision(False, path=path, reason=detail, decisions=decisions)

    selected_protocol = "connected"
    for hop_name in path[:-1]:
        device = devices[hop_name]
        if not _is_router(device):
            decisions.append(f"{hop_name}: Layer 2 forwarding")
            continue

        connected = [network for network in _connected_routes(device) if destination in network]
        if connected:
            best = max(connected, key=lambda network: network.prefixlen)
            decisions.append(f"{hop_name}: connected route {best}")
            selected_protocol = "connected"
            continue

        static = _static_route(device, destination)
        if static:
            network, next_hop = static
            next_hop_owner = device_for_ip(devices, next_hop)
            if not next_hop_owner:
                reason = f"static route {network} has unresolved next hop {next_hop}"
                decisions.append(f"{hop_name}: {reason}")
                return RouteDecision(False, path=path, reason=reason, decisions=decisions)
            decisions.append(f"{hop_name}: static route {network} via {next_hop}")
            selected_protocol = "static"
            continue

        dynamic = _dynamic_route(hop_name, devices, destination)
        if dynamic:
            network, protocol, owner = dynamic
            decisions.append(
                f"{hop_name}: {protocol.upper()} route {network} advertised by {owner}"
            )
            selected_protocol = protocol
            continue

        reason = f"{hop_name} has no matching route to {destination_ip}"
        decisions.append(f"{hop_name}: {reason}")
        return RouteDecision(False, path=path, reason=reason, decisions=decisions)

    decisions.append(f"{destination_name}: destination reached")
    permitted, acl_reason = enforce_path_acls(
        devices, links, path, source_ip, destination_ip, "icmp"
    )
    if not permitted:
        decisions.append(acl_reason)
        return RouteDecision(False, path=path, reason=acl_reason, decisions=decisions)
    nat_source_decision = record_source_translation(
        devices, path, source_ip, original_destination
    )
    if nat_source_decision:
        decisions.append(nat_source_decision)
    return RouteDecision(
        True,
        path=path,
        reason="Route resolved successfully.",
        decisions=decisions,
        protocol=selected_protocol,
    )
