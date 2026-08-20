from types import SimpleNamespace

from dns_engine import configure_ip_host, configure_server_record, resolve_name


def interface(address=""):
    return SimpleNamespace(ip_address=address, status="up")


def device(name, kind, address, dns_server=""):
    return SimpleNamespace(
        name=name,
        device_type=kind,
        interfaces={"eth0": interface(address)},
        dns_server=dns_server,
        routing_config={},
    )


def test_reachable_dns_server_resolves_record():
    devices = {
        "PC1": device("PC1", "PC", "192.168.1.10/24", "192.168.1.53"),
        "DNS1": device("DNS1", "Server", "192.168.1.53/24"),
    }
    links = [{"source": "PC1", "source_if": "eth0", "target": "DNS1", "target_if": "eth0"}]
    handled, output = configure_server_record(devices["DNS1"], "dns add web.peernet.local 192.168.1.100")
    assert handled and "added" in output
    ok, address, server = resolve_name(devices, links, "PC1", "web.peernet.local")
    assert ok and address == "192.168.1.100" and server == "DNS1"


def test_down_link_makes_dns_unreachable():
    devices = {
        "PC1": device("PC1", "PC", "192.168.1.10/24", "192.168.1.53"),
        "DNS1": device("DNS1", "Server", "192.168.1.53/24"),
    }
    configure_server_record(devices["DNS1"], "dns add router.local 192.168.1.1")
    links = [{"source": "PC1", "source_if": "eth0", "target": "DNS1", "target_if": "eth0", "forced_down": True}]
    ok, _, detail = resolve_name(devices, links, "PC1", "router.local")
    assert not ok and "unreachable" in detail


def test_router_local_ip_host_needs_no_dns_server():
    router = device("R1", "Router", "10.0.0.1/24")
    handled, error = configure_ip_host(router, "ip host branch.local 10.0.0.2")
    assert handled and not error
    ok, address, detail = resolve_name({"R1": router}, [], "R1", "branch.local")
    assert ok and address == "10.0.0.2" and detail == "local host table"
