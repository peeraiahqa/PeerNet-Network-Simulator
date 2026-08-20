# PeerNet Real Routing Decision Engine

`routing_engine.py` is a Streamlit-independent forwarding engine shared by
Console Ping, the Ping tab, Traceroute, and Packet Analysis.

## Routing decisions supported

- Active physical links and interface operational state
- Source-IP ownership and source-interface state
- Connected IPv4 networks
- Static routes
- Default routes (`0.0.0.0/0`)
- Longest-prefix selection and administrative distance for static candidates
- RIP, OSPF, EIGRP, and BGP configured network advertisements
- End-device local-subnet and default-gateway validation
- Layer 2 transit through switches
- Clear hop-by-hop success or failure explanations

## Validation

`tests/test_routing_engine.py` covers connected topology behavior, remote
loopbacks through static/default routing, missing-route failures, down links,
and OSPF-advertised reachability.

