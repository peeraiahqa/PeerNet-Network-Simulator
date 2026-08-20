from types import SimpleNamespace

from network_validation import (
    audit_topology,
    validate_gateway,
    validate_interface_address,
)


def iface(ip="", **values):
    defaults = {
        "ip_address": ip,
        "switchport_mode": "access",
        "access_vlan": 1,
        "native_vlan": 1,
        "trunk_allowed_vlans": [],
        "encapsulation_dot1q": None,
    }
    defaults.update(values)
    return SimpleNamespace(**defaults)


def device(name, interfaces, kind="Router", gateway="", vlans=None):
    return SimpleNamespace(
        name=name,
        interfaces=interfaces,
        device_type=kind,
        default_gateway=gateway,
        vlans=vlans or {},
    )


def test_duplicate_ip_is_rejected():
    devices = {
        "R1": device("R1", {"Gi0/0": iface("10.0.0.1/24")}),
        "R2": device("R2", {"Gi0/0": iface()}),
    }
    ok, message = validate_interface_address(
        devices, "R2", "Gi0/0", "10.0.0.1/24"
    )
    assert not ok and "Duplicate IP" in message


def test_gateway_must_be_local():
    pc = device("PC1", {"eth0": iface("192.168.1.10/24")}, kind="PC")
    ok, message = validate_gateway(pc, "10.0.0.1")
    assert not ok and "outside" in message


def test_missing_access_vlan_is_reported():
    sw = device(
        "SW1",
        {"Gi0/1": iface(access_vlan=20)},
        kind="Switch",
        vlans={1: "default"},
    )
    issues = audit_topology({"SW1": sw})
    assert any("Access VLAN 20" in issue.message for issue in issues)


def test_subinterface_requires_dot1q():
    router = device("R1", {"Gi0/0.10": iface("192.168.10.1/24")})
    issues = audit_topology({"R1": router})
    assert any("no encapsulation dot1Q" in issue.message for issue in issues)

