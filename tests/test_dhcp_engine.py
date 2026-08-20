from types import SimpleNamespace

from dhcp_engine import allocate_lease, configure_dhcp_global, configure_dhcp_pool, release_lease


def interface(address=""):
    return SimpleNamespace(ip_address=address, status="up", connected_to="peer")


def device(name, interfaces):
    return SimpleNamespace(name=name, interfaces=interfaces, routing_config={})


def topology():
    devices = {
        "R1": device("R1", {"Gi0/0": interface("192.168.10.1/24")}),
        "SW1": device("SW1", {"Gi0/1": interface(), "Gi0/2": interface()}),
        "PC1": device("PC1", {"eth0": interface()}),
        "PC2": device("PC2", {"eth0": interface()}),
    }
    links = [
        {"source": "R1", "source_if": "Gi0/0", "target": "SW1", "target_if": "Gi0/1"},
        {"source": "SW1", "source_if": "Gi0/2", "target": "PC1", "target_if": "eth0"},
        {"source": "SW1", "source_if": "Gi0/2", "target": "PC2", "target_if": "eth0"},
    ]
    context = {}
    assert configure_dhcp_global(devices["R1"], "ip dhcp excluded-address 192.168.10.1 192.168.10.9", context)[0]
    assert configure_dhcp_global(devices["R1"], "ip dhcp pool USERS", context)[0]
    assert configure_dhcp_pool(devices["R1"], "network 192.168.10.0 255.255.255.0", context)[0]
    assert configure_dhcp_pool(devices["R1"], "default-router 192.168.10.1", context)[0]
    assert configure_dhcp_pool(devices["R1"], "dns-server 8.8.8.8", context)[0]
    return devices, links


def test_allocates_unique_non_excluded_addresses_and_renews():
    devices, links = topology()
    ok, _, first = allocate_lease(devices, links, "PC1", "eth0")
    assert ok and first["address"] == "192.168.10.10"
    devices["PC1"].interfaces["eth0"].ip_address = "192.168.10.10/24"
    ok, _, renewed = allocate_lease(devices, links, "PC1", "eth0")
    assert ok and renewed["address"] == first["address"]
    ok, _, second = allocate_lease(devices, links, "PC2", "eth0")
    assert ok and second["address"] == "192.168.10.11"


def test_down_link_blocks_dhcp_and_release_removes_binding():
    devices, links = topology()
    links[1]["forced_down"] = True
    ok, _, _ = allocate_lease(devices, links, "PC1", "eth0")
    assert not ok
    links[1]["forced_down"] = False
    assert allocate_lease(devices, links, "PC1", "eth0")[0]
    release_lease(devices, "PC1", "eth0")
    assert not devices["R1"].routing_config["dhcp"]["leases"]
