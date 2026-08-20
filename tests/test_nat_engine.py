from types import SimpleNamespace

from acl_engine import configure_access_list
from nat_engine import (
    configure_nat_global,
    configure_nat_interface,
    show_translations,
)
from routing_engine import evaluate_route


def interface(address=""):
    return SimpleNamespace(
        name="",
        ip_address=address,
        status="up",
        connected_to="peer",
        access_group_in="",
        access_group_out="",
        nat_inside=False,
        nat_outside=False,
    )


def device(name, kind, interfaces, gateway=""):
    for interface_name, value in interfaces.items():
        value.name = interface_name
    return SimpleNamespace(
        name=name,
        device_type=kind,
        interfaces=interfaces,
        default_gateway=gateway,
        routing_table={},
        route_distances={},
        routing_config={},
    )


def topology():
    devices = {
        "INSIDE": device("INSIDE", "PC", {"eth0": interface("192.168.1.10/24")}, "192.168.1.1"),
        "R1": device("R1", "Router", {"Gi0/0": interface("192.168.1.1/24"), "Gi0/1": interface("203.0.113.1/24")}),
        "OUTSIDE": device("OUTSIDE", "PC", {"eth0": interface("203.0.113.20/24")}, "203.0.113.1"),
    }
    links = [
        {"source": "INSIDE", "source_if": "eth0", "target": "R1", "target_if": "Gi0/0"},
        {"source": "R1", "source_if": "Gi0/1", "target": "OUTSIDE", "target_if": "eth0"},
    ]
    configure_nat_interface([devices["R1"].interfaces["Gi0/0"]], "ip nat inside")
    configure_nat_interface([devices["R1"].interfaces["Gi0/1"]], "ip nat outside")
    return devices, links


def test_static_nat_public_address_reaches_inside_host():
    devices, links = topology()
    handled, error = configure_nat_global(devices["R1"], "ip nat inside source static 192.168.1.10 203.0.113.10")
    assert handled and not error
    decision = evaluate_route("OUTSIDE", "203.0.113.20", "203.0.113.10", devices, links)
    assert decision.reachable
    assert any("static NAT" in item for item in decision.decisions)


def test_pat_creates_translation_using_outside_interface():
    devices, links = topology()
    configure_access_list(devices["R1"], "access-list 10 permit 192.168.1.0 0.0.0.255")
    handled, error = configure_nat_global(devices["R1"], "ip nat inside source list 10 interface Gi0/1 overload")
    assert handled and not error
    decision = evaluate_route("INSIDE", "192.168.1.10", "203.0.113.20", devices, links)
    assert decision.reachable
    assert any("PAT" in item for item in decision.decisions)
    output = show_translations(devices["R1"])
    assert "203.0.113.1" in output and "192.168.1.10" in output
