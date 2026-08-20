# NAT and PAT Update

PeerNet now supports interface NAT roles, static one-to-one mappings, and ACL-based Port Address Translation. Successful routed Ping and Traceroute operations create translations that can be verified from privileged EXEC mode.

## PAT overload example

```text
R1> enable
R1# configure terminal
R1(config)# access-list 10 permit 192.168.1.0 0.0.0.255
R1(config)# interface Gi0/0
R1(config-if-Gi0/0)# ip nat inside
R1(config-if-Gi0/0)# exit
R1(config)# interface Gi0/1
R1(config-if-Gi0/1)# ip nat outside
R1(config-if-Gi0/1)# exit
R1(config)# ip nat inside source list 10 interface Gi0/1 overload
R1(config)# end
R1# show ip nat statistics
R1# show ip nat translations
```

The overload interface must have an IPv4 address. The referenced standard ACL selects inside source addresses; it does not have to be applied with `ip access-group`.

## Static NAT example

```text
R1(config)# ip nat inside source static 192.168.1.10 203.0.113.10
```

Traffic addressed to `203.0.113.10` is routed to the topology device using `192.168.1.10`.

## Verification and clearing

```text
R1# show ip nat translations
R1# show ip nat statistics
R1# clear ip nat translation *
```

NAT interface roles and rules are included in the running configuration, saved projects, and startup configuration.
