# PeerNet Routing CLI Update

Add `routing_cli.py` beside `app.py`. Keep `switch_cli.py` beside both files.

## Static and default routing

```text
R1> enable
R1# configure terminal
R1(config)# ip route 10.20.0.0 255.255.0.0 192.0.2.2
R1(config)# ip route 0.0.0.0 0.0.0.0 192.0.2.1
R1(config)# end
R1# show ip route
R1# show ip route static
```

CIDR syntax and administrative distance are also supported:

```text
ip route 10.30.0.0/16 192.0.2.2
ip route 0.0.0.0/0 192.0.2.1 10
no ip route 10.30.0.0/16 192.0.2.2
```

## Router-on-a-stick

```text
R1# configure terminal
R1(config)# interface Gi0/0.10
R1(config-if-Gi0/0.10)# encapsulation dot1Q 10
R1(config-if-Gi0/0.10)# ip address 192.168.10.1 255.255.255.0
R1(config-if-Gi0/0.10)# no shutdown
R1(config-if-Gi0/0.10)# exit
R1(config)# interface Gi0/0.20
R1(config-if-Gi0/0.20)# encapsulation dot1Q 20
R1(config-if-Gi0/0.20)# ip address 192.168.20.1 255.255.255.0
R1(config-if-Gi0/0.20)# no shutdown
R1(config-if-Gi0/0.20)# end
R1# show ip interface brief
R1# show running-config
```

## Multilayer-switch inter-VLAN routing

Create VLANs first, then configure SVIs:

```text
MLS1# configure terminal
MLS1(config)# vlan 10
MLS1(config-vlan)# name USERS
MLS1(config-vlan)# exit
MLS1(config)# vlan 20
MLS1(config-vlan)# name VOICE
MLS1(config-vlan)# exit
MLS1(config)# ip routing
MLS1(config)# interface Vlan10
MLS1(config-if-Vlan10)# ip address 192.168.10.1 255.255.255.0
MLS1(config-if-Vlan10)# no shutdown
MLS1(config-if-Vlan10)# exit
MLS1(config)# interface Vlan20
MLS1(config-if-Vlan20)# ip address 192.168.20.1 255.255.255.0
MLS1(config-if-Vlan20)# no shutdown
MLS1(config-if-Vlan20)# end
MLS1# show ip interface brief
MLS1# show ip route
```

## RIP v1 and v2

```text
R1(config)# router rip
R1(config-router)# version 1
R1(config-router)# network 10.0.0.0
R1(config-router)# version 2
R1(config-router)# no auto-summary
R1(config-router)# passive-interface Gi0/1
R1(config-router)# end
R1# show ip protocols
```

## OSPFv2

```text
R1(config)# router ospf 1
R1(config-router)# router-id 1.1.1.1
R1(config-router)# network 10.0.0.0 0.255.255.255 area 0
R1(config-router)# passive-interface Gi0/1
R1(config-router)# end
R1# show ip protocols
R1# show ip ospf neighbor
```

## OSPFv3

```text
R1(config)# ipv6 unicast-routing
R1(config)# router ospf v3 10
R1(config-router)# router-id 1.1.1.1
R1(config-router)# exit
R1(config)# interface Gi0/0
R1(config-if-Gi0/0)# ipv6 address 2001:db8:10::1/64
R1(config-if-Gi0/0)# ipv6 ospf 10 area 0
R1(config-if-Gi0/0)# end
R1# show ipv6 ospf neighbor
```

## EIGRP

```text
R1(config)# router eigrp 100
R1(config-router)# network 172.16.0.0 0.0.255.255
R1(config-router)# no auto-summary
R1(config-router)# passive-interface Gi0/1
R1(config-router)# end
R1# show ip eigrp neighbors
```

## BGP: eBGP and iBGP

The simulator labels a neighbor as iBGP when the remote AS equals the local AS;
otherwise it labels the session as eBGP.

```text
R1(config)# router bgp 65001
R1(config-router)# router-id 1.1.1.1
R1(config-router)# neighbor 203.0.113.2 remote-as 65002
R1(config-router)# neighbor 10.0.0.2 remote-as 65001
R1(config-router)# network 10.20.0.0 mask 255.255.0.0
R1(config-router)# end
R1# show ip bgp summary
```

## Redistribution and policy

```text
R1(config)# ip prefix-list INTERNAL seq 10 permit 10.0.0.0/8
R1(config)# route-map OSPF-TO-BGP permit 10
R1(config-route-map)# match ip address prefix-list INTERNAL
R1(config-route-map)# set metric 100
R1(config-route-map)# exit
R1(config)# router bgp 65001
R1(config-router)# redistribute ospf 1 route-map OSPF-TO-BGP
R1(config-router)# neighbor 203.0.113.2 route-map OSPF-TO-BGP out
R1(config-router)# end
R1# show route-map
R1# show running-config
```

Redistribution sources supported: `connected`, `static`, `rip`, `ospf`,
`eigrp`, and `bgp`. Optional metric and route-map text is preserved.

## GRE and protected tunnels

```text
R1(config)# interface Tunnel0
R1(config-if-Tunnel0)# ip address 172.31.0.1 255.255.255.252
R1(config-if-Tunnel0)# tunnel source Gi0/0
R1(config-if-Tunnel0)# tunnel destination 198.51.100.2
R1(config-if-Tunnel0)# tunnel mode gre ip
R1(config-if-Tunnel0)# no shutdown
R1(config-if-Tunnel0)# end
```

IPsec-style tunnel configuration:

```text
tunnel mode ipsec ipv4
tunnel protection ipsec profile PEERNET-IPSEC
```

## Verification

```text
show ip route
show ip route static
show ip protocols
show ip ospf neighbor
show ipv6 ospf neighbor
show ip eigrp neighbors
show ip bgp summary
show route-map
show ip interface brief
show running-config
```

## Local installation

Back up the current project, then copy these files into the project root:

```text
app.py
switch_cli.py
routing_cli.py
```

Validate and run:

```powershell
python -m py_compile app.py switch_cli.py routing_cli.py
streamlit run app.py
```

This update preserves the existing topology, authentication, Supabase, console,
packet, VLAN, and UI code. New routing fields are serialized with projects, and
older saved projects receive compatible defaults when loaded.
