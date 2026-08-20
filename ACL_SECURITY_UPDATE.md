# IPv4 ACL Security Update

PeerNet now supports numbered standard and extended IPv4 access lists. ACLs can be applied inbound or outbound on router and multilayer-switch interfaces. Ping, Traceroute, packet animation, and routing diagnostics use the same filtering decision.

## Extended ACL example

```text
R1> enable
R1# configure terminal
R1(config)# access-list 100 deny icmp host 192.168.1.10 host 10.0.0.10
R1(config)# access-list 100 permit ip any any
R1(config)# interface Gi0/0
R1(config-if-Gi0/0)# ip access-group 100 in
R1(config-if-Gi0/0)# end
R1# show access-lists
```

## Standard ACL example

```text
R1(config)# access-list 10 permit 192.168.1.0 0.0.0.255
R1(config)# interface Gi0/0
R1(config-if-Gi0/0)# ip access-group 10 in
```

An ACL has an implicit deny when no rule matches. Add a final `permit ip any any` to an extended ACL when only selected traffic should be blocked.

## Removal

```text
R1(config-if-Gi0/0)# no ip access-group 100 in
R1(config)# no access-list 100
```

ACL definitions, interface bindings, and match counters appear in `show access-lists`; definitions and bindings are included in saved project and startup configurations.
