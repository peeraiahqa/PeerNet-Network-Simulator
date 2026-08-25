from types import SimpleNamespace

from routing_engine import evaluate_bidirectional_route, evaluate_route


def interface(ip_address="", status="up"):
    return SimpleNamespace(ip_address=ip_address, status=status)


def device(name, interfaces, *, kind="Router", routes=None, protocols=None, gateway=""):
    return SimpleNamespace(
        name=name,
        device_type=kind,
        interfaces=interfaces,
        routing_table=routes or {},
        route_distances={},
        routing_config=protocols or {"ip_routing": True},
        default_gateway=gateway,
    )


def two_router_lab(*, route=True, link_status="up"):
    r1 = device(
        "R1",
        {"Gi0/0": interface("10.0.0.1/30", link_status)},
        routes={"20.10.1.1/32": "10.0.0.2"} if route else {},
    )
    r2 = device(
        "R2",
        {
            "Gi0/0": interface("10.0.0.2/30"),
            "Lo0": interface("20.10.1.1/32"),
        },
    )
    links = [{
        "source": "R1", "source_if": "Gi0/0",
        "target": "R2", "target_if": "Gi0/0",
    }]
    return {"R1": r1, "R2": r2}, links


def test_static_route_reaches_remote_loopback():
    devices, links = two_router_lab()
    result = evaluate_route("R1", "10.0.0.1", "20.10.1.1", devices, links)
    assert result.reachable
    assert result.path == ["R1", "R2"]
    assert result.protocol == "static"


def test_missing_route_fails_with_reason():
    devices, links = two_router_lab(route=False)
    result = evaluate_route("R1", "10.0.0.1", "20.10.1.1", devices, links)
    assert not result.reachable
    assert "no matching route" in result.reason


def test_down_interface_breaks_physical_path():
    devices, links = two_router_lab(link_status="down")
    result = evaluate_route("R1", "10.0.0.1", "20.10.1.1", devices, links)
    assert not result.reachable
    assert "does not own source IP" in result.reason or "No active physical path" in result.reason


def test_default_route_is_longest_prefix_static_candidate():
    devices, links = two_router_lab(route=False)
    devices["R1"].routing_table = {"0.0.0.0/0": "10.0.0.2"}
    result = evaluate_route("R1", "10.0.0.1", "20.10.1.1", devices, links)
    assert result.reachable
    assert result.protocol == "static"


def test_ospf_advertisement_supplies_route():
    devices, links = two_router_lab(route=False)
    devices["R1"].routing_config = {
        "ip_routing": True,
        "ospf": {"1": {"networks": [{"prefix": "10.0.0.0/30"}]}},
    }
    devices["R2"].routing_config = {
        "ip_routing": True,
        "ospf": {"1": {"networks": [{"prefix": "20.10.1.1/32"}]}},
    }
    result = evaluate_route("R1", "10.0.0.1", "20.10.1.1", devices, links)
    assert result.reachable
    assert result.protocol == "ospf"


def test_simulated_cable_failure_removes_link():
    devices, links = two_router_lab()
    links[0]["forced_down"] = True
    result = evaluate_route("R1", "10.0.0.1", "20.10.1.1", devices, links)
    assert not result.reachable
    assert "No active physical path" in result.reason


def pc_to_pc_routed_lab(*, forward_route=False, return_route=False, gateways=True):
    devices = {
        "PC1": device(
            "PC1",
            {"eth0": interface("10.0.0.2/24")},
            kind="PC",
            gateway="10.0.0.1" if gateways else "",
        ),
        "SW1": device("SW1", {}, kind="Switch"),
        "R1": device(
            "R1",
            {
                "Gi0/0": interface("10.0.0.1/24"),
                "S0/0/0": interface("20.0.0.1/24"),
            },
            routes={"30.0.0.0/24": "20.0.0.2"} if forward_route else {},
        ),
        "R2": device(
            "R2",
            {
                "S0/0/0": interface("20.0.0.2/24"),
                "Gi0/0": interface("30.0.0.1/24"),
            },
            routes={"10.0.0.0/24": "20.0.0.1"} if return_route else {},
        ),
        "SW2": device("SW2", {}, kind="Switch"),
        "PC2": device(
            "PC2",
            {"eth0": interface("30.0.0.2/24")},
            kind="PC",
            gateway="30.0.0.1" if gateways else "",
        ),
    }
    links = [
        {"source": "PC1", "source_if": "eth0", "target": "SW1", "target_if": "Gi0/2"},
        {"source": "SW1", "source_if": "Gi0/1", "target": "R1", "target_if": "Gi0/0"},
        {"source": "R1", "source_if": "S0/0/0", "target": "R2", "target_if": "S0/0/0"},
        {"source": "R2", "source_if": "Gi0/0", "target": "SW2", "target_if": "Gi0/1"},
        {"source": "SW2", "source_if": "Gi0/2", "target": "PC2", "target_if": "eth0"},
    ]
    return devices, links


def test_pc_ping_does_not_use_physical_path_as_a_route():
    devices, links = pc_to_pc_routed_lab()
    result = evaluate_bidirectional_route(
        "PC1", "10.0.0.2", "30.0.0.2", devices, links
    )
    assert not result.reachable
    assert result.reason == "R1 has no matching route to 30.0.0.2"


def test_pc_ping_requires_a_return_route():
    devices, links = pc_to_pc_routed_lab(forward_route=True)
    result = evaluate_bidirectional_route(
        "PC1", "10.0.0.2", "30.0.0.2", devices, links
    )
    assert not result.reachable
    assert "Return path failed" in result.reason
    assert "R2 has no matching route to 10.0.0.2" in result.reason


def test_pc_ping_succeeds_with_gateways_and_routes_in_both_directions():
    devices, links = pc_to_pc_routed_lab(
        forward_route=True, return_route=True
    )
    result = evaluate_bidirectional_route(
        "PC1", "10.0.0.2", "30.0.0.2", devices, links
    )
    assert result.reachable
    assert result.path == ["PC1", "SW1", "R1", "R2", "SW2", "PC2"]
    assert any(item.startswith("Return path:") for item in result.decisions)


def test_pc_ping_requires_a_default_gateway_for_remote_subnet():
    devices, links = pc_to_pc_routed_lab(
        forward_route=True, return_route=True, gateways=False
    )
    result = evaluate_bidirectional_route(
        "PC1", "10.0.0.2", "30.0.0.2", devices, links
    )
    assert not result.reachable
    assert result.reason == "no default gateway is configured"
