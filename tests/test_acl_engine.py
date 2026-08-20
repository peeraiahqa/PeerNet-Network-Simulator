from types import SimpleNamespace

from acl_engine import configure_access_group, configure_access_list, show_access_lists
from routing_engine import evaluate_route


def interface(address=""):
    return SimpleNamespace(
        ip_address=address,
        status="up",
        connected_to="peer",
        access_group_in="",
        access_group_out="",
    )


def device(name, kind, interfaces, gateway=""):
    return SimpleNamespace(
        name=name,
        device_type=kind,
        interfaces=interfaces,
        default_gateway=gateway,
        routing_table={},
        route_distances={},
        routing_config={},
    )


def acl_topology():
    devices = {
        "PC1": device("PC1", "PC", {"eth0": interface("192.168.1.10/24")}, "192.168.1.1"),
        "R1": device("R1", "Router", {"Gi0/0": interface("192.168.1.1/24"), "Gi0/1": interface("10.0.0.1/24")}),
        "PC2": device("PC2", "PC", {"eth0": interface("10.0.0.10/24")}, "10.0.0.1"),
    }
    links = [
        {"source": "PC1", "source_if": "eth0", "target": "R1", "target_if": "Gi0/0"},
        {"source": "R1", "source_if": "Gi0/1", "target": "PC2", "target_if": "eth0"},
    ]
    return devices, links


def test_extended_acl_denies_ping_and_counts_match():
    devices, links = acl_topology()
    handled, error = configure_access_list(devices["R1"], "access-list 100 deny icmp host 192.168.1.10 host 10.0.0.10")
    assert handled and not error
    configure_access_list(devices["R1"], "access-list 100 permit ip any any")
    configure_access_group([devices["R1"].interfaces["Gi0/0"]], "ip access-group 100 in")
    decision = evaluate_route("PC1", "192.168.1.10", "10.0.0.10", devices, links)
    assert not decision.reachable and "ACL 100 denied" in decision.reason
    assert "1 matches" in show_access_lists(devices["R1"])


def test_standard_acl_permits_matching_source():
    devices, links = acl_topology()
    configure_access_list(devices["R1"], "access-list 10 permit 192.168.1.0 0.0.0.255")
    configure_access_group([devices["R1"].interfaces["Gi0/0"]], "ip access-group 10 in")
    decision = evaluate_route("PC1", "192.168.1.10", "10.0.0.10", devices, links)
    assert decision.reachable
