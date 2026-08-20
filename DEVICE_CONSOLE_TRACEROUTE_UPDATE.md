# Device Console Traceroute

All network-device consoles now support routed Traceroute in EXEC mode.

## Supported commands

```text
traceroute 20.10.1.1
traceroute -m 10 20.10.1.1
traceroute ttl 10 20.10.1.1
tracert 20.10.1.1
```

- Default maximum: 30 hops
- Accepted maximum: 1 through 64 hops
- Cisco-style hop timing output
- Real routing-engine path and failure reasons
- Live topology packet animation on success
- Packet Analysis and Events integration
- EXEC-mode validation

