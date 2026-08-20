"""Routing configuration engine for PeerNet Network Simulator.

The module is intentionally independent from Streamlit so routing commands can
be extended and tested without changing the simulator UI.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Any, Iterable


ROUTING_DEVICE_TYPES = {"Router", "Multilayer Switch", "Router/Switch Processor"}


@dataclass
class RoutingResult:
    handled: bool
    mode: str | None = None
    output: str | None = None


def is_routing_device(device) -> bool:
    return device.device_type in ROUTING_DEVICE_TYPES


def ensure_routing_defaults(device) -> dict[str, Any]:
    if not hasattr(device, "route_distances") or not isinstance(device.route_distances, dict):
        device.route_distances = {}
    config = getattr(device, "routing_config", None)
    if not isinstance(config, dict):
        config = {}
        device.routing_config = config
    config.setdefault("ip_routing", device.device_type != "Switch")
    config.setdefault("ipv6_unicast_routing", False)
    config.setdefault("rip", {})
    config.setdefault("ospf", {})
    config.setdefault("ospfv3", {})
    config.setdefault("eigrp", {})
    config.setdefault("bgp", {})
    config.setdefault("prefix_lists", {})
    config.setdefault("route_maps", {})
    return config


def _network(prefix: str, mask: str | None = None) -> str:
    if mask is None:
        return str(ipaddress.ip_network(prefix, strict=False))
    return str(ipaddress.ip_network(f"{prefix}/{mask}", strict=False))


def _address(value: str) -> str:
    return str(ipaddress.ip_address(value))


def _wildcard_network(address: str, wildcard: str) -> str:
    ip_value = int(ipaddress.IPv4Address(address))
    wildcard_value = int(ipaddress.IPv4Address(wildcard))
    mask_value = wildcard_value ^ 0xFFFFFFFF
    mask = str(ipaddress.IPv4Address(mask_value))
    return _network(address, mask)


def configure_static_route(device, command: str) -> RoutingResult:
    lowered = command.lower()
    removing = lowered.startswith("no ip route ")
    if not (lowered.startswith("ip route ") or removing):
        return RoutingResult(False)
    if not is_routing_device(device):
        return RoutingResult(True, output="% IP routing is not supported on this device type.")
    ensure_routing_defaults(device)

    words = command.split()[3:] if removing else command.split()[2:]
    try:
        if len(words) >= 2 and "/" in words[0]:
            network = _network(words[0])
            next_hop = _address(words[1])
            distance = int(words[2]) if len(words) > 2 else 1
        elif len(words) >= 3:
            network = _network(words[0], words[1])
            next_hop = _address(words[2])
            distance = int(words[3]) if len(words) > 3 else 1
        else:
            raise ValueError
        if not 1 <= distance <= 255:
            raise ValueError
    except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError):
        return RoutingResult(
            True,
            output="% Use: ip route <network> <mask> <next-hop> [distance] or ip route <prefix/length> <next-hop> [distance]",
        )

    if removing:
        device.routing_table.pop(network, None)
        getattr(device, "route_distances", {}).pop(network, None)
    else:
        device.routing_table[network] = next_hop
        device.route_distances[network] = distance
    return RoutingResult(True)


def enter_router_mode(device, command: str, context: dict) -> RoutingResult:
    words = command.lower().split()
    if not words or words[0] != "router":
        return RoutingResult(False)
    if not is_routing_device(device):
        return RoutingResult(True, output="% Dynamic routing is supported on routers and multilayer switches.")
    config = ensure_routing_defaults(device)

    if len(words) == 2 and words[1] == "rip":
        config["rip"].setdefault("version", 2)
        config["rip"].setdefault("networks", [])
        config["rip"].setdefault("passive_interfaces", [])
        config["rip"].setdefault("auto_summary", False)
        config["rip"].setdefault("redistribute", [])
        context.clear()
        context.update({"protocol": "rip", "process": "rip"})
        return RoutingResult(True, mode="router")

    if len(words) == 3 and words[1] in {"ospf", "eigrp", "bgp"}:
        protocol, process = words[1], words[2]
        try:
            process_number = int(process)
            if process_number <= 0:
                raise ValueError
        except ValueError:
            return RoutingResult(True, output=f"% Invalid {protocol.upper()} process/AS number.")
        process = str(process_number)
        config[protocol].setdefault(process, {})
        process_config = config[protocol][process]
        process_config.setdefault("networks", [])
        process_config.setdefault("passive_interfaces", [])
        process_config.setdefault("redistribute", [])
        process_config.setdefault("router_id", "")
        if protocol == "eigrp":
            process_config.setdefault("auto_summary", False)
        if protocol == "bgp":
            process_config.setdefault("neighbors", {})
        context.clear()
        context.update({"protocol": protocol, "process": process})
        return RoutingResult(True, mode="router")

    if len(words) == 4 and words[1:3] == ["ospf", "v3"]:
        process = words[3]
        if not process.isdigit() or int(process) <= 0:
            return RoutingResult(True, output="% Invalid OSPFv3 process number.")
        config["ospfv3"].setdefault(process, {
            "router_id": "", "networks": [], "passive_interfaces": [], "redistribute": []
        })
        context.clear()
        context.update({"protocol": "ospfv3", "process": process})
        return RoutingResult(True, mode="router")

    return RoutingResult(True, output="% Use: router rip | router ospf <id> | router ospf v3 <id> | router eigrp <asn> | router bgp <asn>")


def _process_config(device, context: dict) -> dict:
    config = ensure_routing_defaults(device)
    protocol = context["protocol"]
    if protocol == "rip":
        return config["rip"]
    return config[protocol][context["process"]]


def configure_router_mode(device, command: str, context: dict) -> RoutingResult:
    if not context.get("protocol"):
        return RoutingResult(False)
    lowered = command.lower().strip()
    words = command.split()
    protocol = context["protocol"]
    process_config = _process_config(device, context)

    if lowered == "exit":
        context.clear()
        return RoutingResult(True, mode="config")
    if lowered == "end":
        context.clear()
        return RoutingResult(True, mode="privileged")
    if lowered.startswith("router-id "):
        try:
            process_config["router_id"] = str(ipaddress.IPv4Address(words[1]))
        except (IndexError, ipaddress.AddressValueError):
            return RoutingResult(True, output="% Invalid router ID.")
        return RoutingResult(True)
    if protocol == "rip" and lowered.startswith("version "):
        if len(words) != 2 or words[1] not in {"1", "2"}:
            return RoutingResult(True, output="% RIP version must be 1 or 2.")
        process_config["version"] = int(words[1])
        return RoutingResult(True)
    if lowered == "no auto-summary":
        process_config["auto_summary"] = False
        return RoutingResult(True)
    if lowered == "auto-summary":
        process_config["auto_summary"] = True
        return RoutingResult(True)
    if lowered.startswith("passive-interface "):
        interface = command.split(maxsplit=1)[1].strip()
        if interface not in process_config["passive_interfaces"]:
            process_config["passive_interfaces"].append(interface)
        return RoutingResult(True)
    if lowered.startswith("no passive-interface "):
        interface = command.split(maxsplit=2)[2].strip()
        if interface in process_config["passive_interfaces"]:
            process_config["passive_interfaces"].remove(interface)
        return RoutingResult(True)
    if lowered.startswith("redistribute "):
        statement = command.split(maxsplit=1)[1].strip()
        source = statement.split()[0].lower()
        if source not in {"connected", "static", "rip", "ospf", "eigrp", "bgp"}:
            return RoutingResult(True, output="% Unsupported redistribution source.")
        if statement not in process_config["redistribute"]:
            process_config["redistribute"].append(statement)
        return RoutingResult(True)
    if lowered.startswith("no redistribute "):
        statement = command.split(maxsplit=2)[2].strip()
        process_config["redistribute"] = [
            item for item in process_config["redistribute"] if item != statement
        ]
        return RoutingResult(True)

    if protocol == "rip" and lowered.startswith("network "):
        try:
            network = _network(words[1] if "/" in words[1] else f"{words[1]}/8")
        except (IndexError, ValueError):
            return RoutingResult(True, output="% Invalid RIP network.")
        if network not in process_config["networks"]:
            process_config["networks"].append(network)
        return RoutingResult(True)

    if protocol in {"ospf", "eigrp"} and lowered.startswith("network "):
        try:
            if protocol == "ospf":
                if len(words) != 5 or words[3].lower() != "area":
                    raise ValueError
                entry = {
                    "prefix": _wildcard_network(words[1], words[2]),
                    "wildcard": words[2],
                    "area": words[4],
                }
            else:
                if len(words) == 2:
                    entry = {"prefix": _network(words[1])}
                elif len(words) == 3:
                    entry = {"prefix": _wildcard_network(words[1], words[2]), "wildcard": words[2]}
                else:
                    raise ValueError
        except (ValueError, ipaddress.AddressValueError):
            usage = "network <ip> <wildcard> area <area>" if protocol == "ospf" else "network <prefix> [wildcard]"
            return RoutingResult(True, output=f"% Use: {usage}")
        if entry not in process_config["networks"]:
            process_config["networks"].append(entry)
        return RoutingResult(True)

    if protocol == "ospfv3" and lowered.startswith("address-family ipv6"):
        return RoutingResult(True, mode="router")

    if protocol == "bgp":
        if lowered.startswith("neighbor "):
            if len(words) >= 4 and words[2].lower() == "remote-as":
                try:
                    neighbor = _address(words[1])
                    remote_as = int(words[3])
                    if remote_as <= 0:
                        raise ValueError
                except (ValueError, ipaddress.AddressValueError):
                    return RoutingResult(True, output="% Invalid BGP neighbor or remote AS.")
                entry = process_config["neighbors"].setdefault(neighbor, {})
                entry["remote_as"] = remote_as
                entry.setdefault("description", "")
                entry.setdefault("route_maps", {})
                return RoutingResult(True)
            if len(words) >= 4 and words[2].lower() == "description":
                neighbor = words[1]
                if neighbor not in process_config["neighbors"]:
                    return RoutingResult(True, output="% Configure neighbor remote-as first.")
                process_config["neighbors"][neighbor]["description"] = " ".join(words[3:])
                return RoutingResult(True)
            if len(words) == 5 and words[2].lower() == "route-map" and words[4].lower() in {"in", "out"}:
                neighbor = words[1]
                if neighbor not in process_config["neighbors"]:
                    return RoutingResult(True, output="% Configure neighbor remote-as first.")
                process_config["neighbors"][neighbor]["route_maps"][words[4].lower()] = words[3]
                return RoutingResult(True)
        if lowered.startswith("network "):
            try:
                if len(words) == 2:
                    prefix = _network(words[1])
                elif len(words) == 4 and words[2].lower() == "mask":
                    prefix = _network(words[1], words[3])
                else:
                    raise ValueError
            except ValueError:
                return RoutingResult(True, output="% Use: network <prefix/length> or network <network> mask <mask>")
            if prefix not in process_config["networks"]:
                process_config["networks"].append(prefix)
            return RoutingResult(True)

    return RoutingResult(False)


def configure_policy(device, command: str, context: dict) -> RoutingResult:
    lowered = command.lower().strip()
    config = ensure_routing_defaults(device)
    if lowered.startswith("ip prefix-list "):
        words = command.split()
        try:
            name = words[2]
            index = 3
            sequence = None
            if words[index].lower() == "seq":
                sequence = int(words[index + 1])
                index += 2
            action = words[index].lower()
            prefix = _network(words[index + 1])
            if action not in {"permit", "deny"}:
                raise ValueError
            entry = {"seq": sequence or 10, "action": action, "prefix": prefix}
        except (IndexError, ValueError):
            return RoutingResult(True, output="% Use: ip prefix-list <name> [seq <n>] permit|deny <prefix>")
        entries = config["prefix_lists"].setdefault(name, [])
        entries[:] = [item for item in entries if item["seq"] != entry["seq"]]
        entries.append(entry)
        entries.sort(key=lambda item: item["seq"])
        return RoutingResult(True)

    if lowered.startswith("route-map "):
        words = command.split()
        try:
            name = words[1]
            action = words[2].lower() if len(words) > 2 else "permit"
            sequence = int(words[3]) if len(words) > 3 else 10
            if action not in {"permit", "deny"}:
                raise ValueError
        except (IndexError, ValueError):
            return RoutingResult(True, output="% Use: route-map <name> permit|deny <sequence>")
        entries = config["route_maps"].setdefault(name, [])
        entry = next((item for item in entries if item["sequence"] == sequence), None)
        if entry is None:
            entry = {"sequence": sequence, "action": action, "match": [], "set": []}
            entries.append(entry)
            entries.sort(key=lambda item: item["sequence"])
        context.clear()
        context.update({"route_map": name, "sequence": sequence})
        return RoutingResult(True, mode="route_map")

    return RoutingResult(False)


def configure_route_map_mode(device, command: str, context: dict) -> RoutingResult:
    if not context.get("route_map"):
        return RoutingResult(False)
    lowered = command.lower().strip()
    if lowered == "exit":
        context.clear()
        return RoutingResult(True, mode="config")
    if lowered == "end":
        context.clear()
        return RoutingResult(True, mode="privileged")
    config = ensure_routing_defaults(device)
    entry = next(
        item for item in config["route_maps"][context["route_map"]]
        if item["sequence"] == context["sequence"]
    )
    if lowered.startswith("match "):
        statement = command.split(maxsplit=1)[1]
        if statement not in entry["match"]:
            entry["match"].append(statement)
        return RoutingResult(True)
    if lowered.startswith("set "):
        statement = command.split(maxsplit=1)[1]
        if statement not in entry["set"]:
            entry["set"].append(statement)
        return RoutingResult(True)
    return RoutingResult(False)


def configure_interface_routing(device, interfaces: Iterable[Any], command: str) -> RoutingResult:
    if not is_routing_device(device):
        return RoutingResult(False)
    lowered = command.lower().strip()
    selected = list(interfaces)
    if not selected:
        return RoutingResult(False)

    if lowered.startswith("encapsulation dot1q "):
        words = command.split()
        try:
            vlan = int(words[2])
            if not 1 <= vlan <= 4094:
                raise ValueError
            native = len(words) > 3 and words[3].lower() == "native"
        except (IndexError, ValueError):
            return RoutingResult(True, output="% Use: encapsulation dot1Q <vlan> [native]")
        for interface in selected:
            interface.encapsulation_dot1q = vlan
            interface.encapsulation_native = native
        return RoutingResult(True)
    if lowered.startswith("ipv6 address "):
        try:
            value = str(ipaddress.ip_interface(command.split(maxsplit=2)[2]))
            if ipaddress.ip_interface(value).version != 6:
                raise ValueError
        except (ValueError, IndexError):
            return RoutingResult(True, output="% Use: ipv6 address <IPv6-prefix/length>")
        for interface in selected:
            interface.ipv6_address = value
        return RoutingResult(True)
    if lowered.startswith("ipv6 ospf "):
        words = command.split()
        if len(words) != 5 or words[3].lower() != "area" or not words[2].isdigit():
            return RoutingResult(True, output="% Use: ipv6 ospf <process-id> area <area>")
        for interface in selected:
            interface.ospfv3_process = words[2]
            interface.ospfv3_area = words[4]
        return RoutingResult(True)
    if lowered.startswith("tunnel source "):
        value = command.split(maxsplit=2)[2]
        for interface in selected:
            interface.tunnel_source = value
        return RoutingResult(True)
    if lowered.startswith("tunnel destination "):
        try:
            value = _address(command.split(maxsplit=2)[2])
        except (IndexError, ipaddress.AddressValueError):
            return RoutingResult(True, output="% Invalid tunnel destination.")
        for interface in selected:
            interface.tunnel_destination = value
        return RoutingResult(True)
    if lowered.startswith("tunnel mode "):
        value = command.split(maxsplit=2)[2].lower()
        if value not in {"gre ip", "ipsec ipv4", "ipv6ip"}:
            return RoutingResult(True, output="% Supported tunnel modes: gre ip, ipsec ipv4, ipv6ip")
        for interface in selected:
            interface.tunnel_mode = value
        return RoutingResult(True)
    if lowered.startswith("tunnel protection ipsec profile "):
        value = command.split(maxsplit=4)[4]
        for interface in selected:
            interface.ipsec_profile = value
        return RoutingResult(True)
    return RoutingResult(False)


def show_ip_protocols(device) -> str:
    config = ensure_routing_defaults(device)
    lines: list[str] = []
    if config["rip"]:
        rip = config["rip"]
        lines.extend([
            f'Routing Protocol is "rip" (version {rip.get("version", 2)})',
            "  Routing for Networks: " + (", ".join(rip.get("networks", [])) or "none"),
        ])
    for protocol, label in (("ospf", "ospf"), ("ospfv3", "ospfv3"), ("eigrp", "eigrp"), ("bgp", "bgp")):
        for process, process_config in config[protocol].items():
            lines.extend([
                f'Routing Protocol is "{label} {process}"',
                "  Router ID " + (process_config.get("router_id") or "not configured"),
                "  Routing for Networks: " + (", ".join(
                    item if isinstance(item, str) else item.get("prefix", "")
                    for item in process_config.get("networks", [])
                ) or "none"),
            ])
    return "\n".join(lines) if lines else "No dynamic routing protocols configured."


def show_bgp_summary(device) -> str:
    config = ensure_routing_defaults(device)
    if not config["bgp"]:
        return "% BGP is not configured."
    lines = ["Neighbor        V    AS       MsgRcvd MsgSent Up/Down  State/PfxRcd"]
    for local_as, process_config in config["bgp"].items():
        for neighbor, entry in process_config.get("neighbors", {}).items():
            session = "iBGP" if int(local_as) == entry["remote_as"] else "eBGP"
            lines.append(
                f"{neighbor:<15} 4 {entry['remote_as']:<8} 0       0       never    Idle ({session})"
            )
    return "\n".join(lines)


def show_routing_summary(device, command: str) -> RoutingResult:
    lowered = command.lower().strip()
    if lowered == "show ip protocols":
        return RoutingResult(True, output=show_ip_protocols(device))
    if lowered in {"show ip bgp summary", "show bgp ipv4 unicast summary"}:
        return RoutingResult(True, output=show_bgp_summary(device))
    if lowered == "show ip ospf neighbor":
        return RoutingResult(True, output="Neighbor ID     Pri State           Dead Time Address         Interface\nNo OSPF neighbors discovered on active simulator links.")
    if lowered == "show ipv6 ospf neighbor":
        return RoutingResult(True, output="Neighbor ID     Pri State           Dead Time Interface ID Interface\nNo OSPFv3 neighbors discovered on active simulator links.")
    if lowered == "show ip eigrp neighbors":
        return RoutingResult(True, output="EIGRP-IPv4 Neighbors\nH   Address          Interface       Hold Uptime SRTT RTO Q Seq\nNo EIGRP neighbors discovered on active simulator links.")
    if lowered == "show ip route static":
        lines = []
        for network, next_hop in device.routing_table.items():
            distance = getattr(device, "route_distances", {}).get(network, 1)
            lines.append(f"S    {network} [{distance}/0] via {next_hop}")
        return RoutingResult(True, output="\n".join(lines) or "No static routes configured.")
    if lowered == "show route-map":
        config = ensure_routing_defaults(device)
        lines = []
        for name, entries in config["route_maps"].items():
            for entry in entries:
                lines.append(f"route-map {name}, {entry['action']}, sequence {entry['sequence']}")
                lines.extend(f"  Match clauses: {item}" for item in entry["match"])
                lines.extend(f"  Set clauses: {item}" for item in entry["set"])
        return RoutingResult(True, output="\n".join(lines) or "No route maps configured.")
    return RoutingResult(False)


def routing_running_config(device) -> list[str]:
    config = ensure_routing_defaults(device)
    lines: list[str] = []
    if config["ip_routing"] and device.device_type == "Multilayer Switch":
        lines.extend(["ip routing", "!"])
    if config["ipv6_unicast_routing"]:
        lines.extend(["ipv6 unicast-routing", "!"])
    for name, entries in config["prefix_lists"].items():
        for entry in entries:
            lines.append(f"ip prefix-list {name} seq {entry['seq']} {entry['action']} {entry['prefix']}")
    for name, entries in config["route_maps"].items():
        for entry in entries:
            lines.append(f"route-map {name} {entry['action']} {entry['sequence']}")
            lines.extend(f" match {item}" for item in entry["match"])
            lines.extend(f" set {item}" for item in entry["set"])
            lines.append("!")
    rip = config["rip"]
    if rip:
        lines.extend(["router rip", f" version {rip.get('version', 2)}"])
        lines.extend(f" network {network}" for network in rip.get("networks", []))
        if not rip.get("auto_summary", False):
            lines.append(" no auto-summary")
        lines.extend(f" passive-interface {item}" for item in rip.get("passive_interfaces", []))
        lines.extend(f" redistribute {item}" for item in rip.get("redistribute", []))
        lines.append("!")
    for protocol, heading in (("ospf", "router ospf"), ("ospfv3", "router ospf v3"), ("eigrp", "router eigrp"), ("bgp", "router bgp")):
        for process, process_config in config[protocol].items():
            lines.append(f"{heading} {process}")
            if process_config.get("router_id"):
                lines.append(f" router-id {process_config['router_id']}")
            for network in process_config.get("networks", []):
                if isinstance(network, str):
                    lines.append(f" network {network}")
                elif protocol == "ospf":
                    prefix = ipaddress.ip_network(network["prefix"])
                    lines.append(f" network {prefix.network_address} {network['wildcard']} area {network['area']}")
                else:
                    lines.append(f" network {network['prefix']}" + (f" {network['wildcard']}" if network.get("wildcard") else ""))
            if protocol == "bgp":
                for neighbor, entry in process_config.get("neighbors", {}).items():
                    lines.append(f" neighbor {neighbor} remote-as {entry['remote_as']}")
                    if entry.get("description"):
                        lines.append(f" neighbor {neighbor} description {entry['description']}")
                    for direction, route_map in entry.get("route_maps", {}).items():
                        lines.append(f" neighbor {neighbor} route-map {route_map} {direction}")
            lines.extend(f" passive-interface {item}" for item in process_config.get("passive_interfaces", []))
            lines.extend(f" redistribute {item}" for item in process_config.get("redistribute", []))
            lines.append("!")
    return lines
