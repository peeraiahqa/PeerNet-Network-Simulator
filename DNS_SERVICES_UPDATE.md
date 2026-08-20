# DNS Services Update

PeerNet now supports topology-aware DNS servers, local router host tables, `nslookup`, and hostname-based Ping and Traceroute. A DNS address learned through DHCP works directly with this feature.

## Configure a DNS server

Add a **Server** device, configure its IPv4 address, and use its device console:

```text
dns add web.peernet.local 192.168.10.100
dns add router.peernet.local 192.168.10.1
dns show
dns remove web.peernet.local
```

## Configure a client

Set the DNS server manually:

```text
PC1> dns 192.168.10.53
PC1> nslookup web.peernet.local
PC1> ping web.peernet.local
PC1> tracert web.peernet.local
```

Alternatively, configure `dns-server 192.168.10.53` inside the router DHCP pool and run `ipconfig /renew` on the PC.

## Router local host table

```text
R1(config)# ip host branch.local 10.20.30.1
R1(config)# end
R1# show hosts
R1# ping branch.local
```

## Failure behavior

Resolution fails with a clear explanation when the client has no DNS server, the configured DNS address is not assigned to a topology device, the server is unreachable because of a down link/interface, or the requested record does not exist.

DNS records are included in project persistence, running configuration, and startup configuration.
