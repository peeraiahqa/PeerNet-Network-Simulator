"""DHCP configuration and lease allocation for PeerNet."""

from __future__ import annotations

import ipaddress
from typing import Any

from routing_engine import active_adjacency


def ensure_dhcp(device: Any) -> dict:
    config = getattr(device, "routing_config", None)
    if not isinstance(config, dict):
        config = {}
        device.routing_config = config
    dhcp = config.setdefault("dhcp", {})
    dhcp.setdefault("excluded", [])
    dhcp.setdefault("pools", {})
    dhcp.setdefault("leases", {})
    return dhcp


def configure_dhcp_global(device: Any, command: str, context: dict) -> tuple[bool, str, str]:
    lowered = command.lower().strip()
    words = command.split()
    dhcp = ensure_dhcp(device)
    if lowered.startswith("ip dhcp excluded-address "):
        try:
            start = str(ipaddress.IPv4Address(words[3]))
            end = str(ipaddress.IPv4Address(words[4])) if len(words) > 4 else start
            if int(ipaddress.IPv4Address(end)) < int(ipaddress.IPv4Address(start)):
                raise ValueError
        except (IndexError, ValueError, ipaddress.AddressValueError):
            return True, "% Use: ip dhcp excluded-address <start> [end]", ""
        entry = {"start": start, "end": end}
        if entry not in dhcp["excluded"]:
            dhcp["excluded"].append(entry)
        return True, "", ""
    if lowered.startswith("no ip dhcp excluded-address "):
        values = words[4:]
        try:
            start = str(ipaddress.IPv4Address(values[0]))
            end = str(ipaddress.IPv4Address(values[1])) if len(values) > 1 else start
        except (IndexError, ipaddress.AddressValueError):
            return True, "% Invalid excluded address range.", ""
        dhcp["excluded"] = [
            entry for entry in dhcp["excluded"]
            if not (entry["start"] == start and entry["end"] == end)
        ]
        return True, "", ""
    if lowered.startswith("ip dhcp pool "):
        pool_name = command.split(maxsplit=3)[3].strip()
        if not pool_name or " " in pool_name:
            return True, "% DHCP pool name cannot contain spaces.", ""
        pool = dhcp["pools"].setdefault(pool_name, {})
        pool.setdefault("network", "")
        pool.setdefault("default_router", "")
        pool.setdefault("dns_server", "")
        pool.setdefault("lease_days", 1)
        context.clear()
        context["pool"] = pool_name
        return True, "", "dhcp"
    if lowered.startswith("no ip dhcp pool "):
        pool_name = command.split(maxsplit=4)[4].strip()
        dhcp["pools"].pop(pool_name, None)
        return True, "", ""
    return False, "", ""


def configure_dhcp_pool(device: Any, command: str, context: dict) -> tuple[bool, str, str]:
    pool_name = context.get("pool")
    if not pool_name:
        return False, "", ""
    dhcp = ensure_dhcp(device)
    pool = dhcp["pools"].setdefault(pool_name, {})
    words = command.split()
    lowered = command.lower().strip()
    if lowered == "exit":
        context.clear()
        return True, "", "config"
    if lowered == "end":
        context.clear()
        return True, "", "privileged"
    if lowered.startswith("network "):
        try:
            if len(words) == 2 and "/" in words[1]:
                network = ipaddress.ip_network(words[1], strict=False)
            elif len(words) == 3:
                network = ipaddress.ip_network(f"{words[1]}/{words[2]}", strict=False)
            else:
                raise ValueError
            if network.version != 4:
                raise ValueError
        except ValueError:
            return True, "% Use: network <network> <mask> or <prefix/length>", ""
        pool["network"] = str(network)
        return True, "", ""
    if lowered.startswith("default-router "):
        try:
            pool["default_router"] = str(ipaddress.IPv4Address(words[1]))
        except (IndexError, ipaddress.AddressValueError):
            return True, "% Invalid default-router address.", ""
        return True, "", ""
    if lowered.startswith("dns-server "):
        try:
            pool["dns_server"] = str(ipaddress.IPv4Address(words[1]))
        except (IndexError, ipaddress.AddressValueError):
            return True, "% Invalid DNS server address.", ""
        return True, "", ""
    if lowered.startswith("lease "):
        try:
            days = int(words[1])
            if not 0 <= days <= 365:
                raise ValueError
        except (IndexError, ValueError):
            return True, "% Lease days must be between 0 and 365.", ""
        pool["lease_days"] = days
        return True, "", ""
    return False, "", ""


def _reachable(adjacency: dict[str, list[str]], source: str) -> set[str]:
    visited = {source}
    queue = [source]
    while queue:
        current = queue.pop(0)
        for neighbor in adjacency.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return visited


def allocate_lease(
    devices: dict[str, Any],
    links: list[dict],
    client_name: str,
    interface_name: str,
) -> tuple[bool, str, dict]:
    adjacency = active_adjacency(devices, links)
    reachable = _reachable(adjacency, client_name)
    used = set()
    for device in devices.values():
        for interface in device.interfaces.values():
            value = getattr(interface, "ip_address", "")
            if value:
                try:
                    used.add(ipaddress.ip_interface(value).ip)
                except ValueError:
                    pass

    for server_name in sorted(reachable):
        server = devices[server_name]
        dhcp = ensure_dhcp(server)
        for pool_name, pool in dhcp["pools"].items():
            if not pool.get("network"):
                continue
            network = ipaddress.ip_network(pool["network"], strict=False)
            gateway = pool.get("default_router", "")
            # A server/router interface must participate in the offered subnet.
            server_on_subnet = any(
                value and ipaddress.ip_interface(value).ip in network
                for value in (
                    getattr(interface, "ip_address", "")
                    for interface in server.interfaces.values()
                )
            )
            if not server_on_subnet:
                continue
            excluded = set()
            for entry in dhcp["excluded"]:
                start = int(ipaddress.IPv4Address(entry["start"]))
                end = int(ipaddress.IPv4Address(entry["end"]))
                excluded.update(ipaddress.IPv4Address(value) for value in range(start, end + 1))
            lease_key = f"{client_name}:{interface_name}"
            old = dhcp["leases"].get(lease_key)
            if old:
                candidate = ipaddress.IPv4Address(old["address"])
                conflict = any(
                    other_name != client_name
                    and any(
                        getattr(other_interface, "ip_address", "")
                        and ipaddress.ip_interface(other_interface.ip_address).ip == candidate
                        for other_interface in other_device.interfaces.values()
                    )
                    for other_name, other_device in devices.items()
                )
                if candidate in network and candidate not in excluded and not conflict:
                    return True, "DHCP lease renewed.", old
            for candidate in network.hosts():
                if candidate in used or candidate in excluded:
                    continue
                if gateway and str(candidate) == gateway:
                    continue
                lease = {
                    "address": str(candidate),
                    "prefixlen": network.prefixlen,
                    "gateway": gateway,
                    "dns": pool.get("dns_server", ""),
                    "server": server_name,
                    "pool": pool_name,
                    "days": pool.get("lease_days", 1),
                }
                dhcp["leases"][lease_key] = lease
                return True, "DHCP lease obtained.", lease
    return False, "DHCP failed: no reachable pool serves this subnet.", {}


def release_lease(devices: dict[str, Any], client_name: str, interface_name: str) -> None:
    lease_key = f"{client_name}:{interface_name}"
    for device in devices.values():
        ensure_dhcp(device)["leases"].pop(lease_key, None)


def dhcp_running_config(device: Any) -> list[str]:
    dhcp = ensure_dhcp(device)
    rows: list[str] = []
    for entry in dhcp["excluded"]:
        command = f"ip dhcp excluded-address {entry['start']}"
        if entry["end"] != entry["start"]:
            command += f" {entry['end']}"
        rows.extend([command, "!"])
    for name, pool in dhcp["pools"].items():
        rows.append(f"ip dhcp pool {name}")
        if pool.get("network"):
            network = ipaddress.ip_network(pool["network"])
            rows.append(f" network {network.network_address} {network.netmask}")
        if pool.get("default_router"):
            rows.append(f" default-router {pool['default_router']}")
        if pool.get("dns_server"):
            rows.append(f" dns-server {pool['dns_server']}")
        rows.extend([f" lease {pool.get('lease_days', 1)}", "!"])
    return rows


def show_dhcp_bindings(device: Any) -> str:
    leases = ensure_dhcp(device)["leases"]
    rows = ["IP address       Client identifier             Pool"]
    for client, lease in sorted(leases.items()):
        rows.append(f"{lease['address']:<16} {client:<29} {lease['pool']}")
    return "\n".join(rows + ([] if leases else ["No DHCP bindings."]))


def show_dhcp_pools(device: Any) -> str:
    pools = ensure_dhcp(device)["pools"]
    rows = ["Pool                 Network             Gateway          Leases"]
    for name, pool in sorted(pools.items()):
        leases = sum(1 for lease in ensure_dhcp(device)["leases"].values() if lease["pool"] == name)
        rows.append(
            f"{name:<20} {pool.get('network') or 'unconfigured':<19} "
            f"{pool.get('default_router') or 'none':<16} {leases}"
        )
    return "\n".join(rows + ([] if pools else ["No DHCP pools configured."]))
