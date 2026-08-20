# Device Console Ping Update

Network-device consoles now support simulated ICMP Ping in EXEC mode.

## Supported commands

```text
ping 20.10.1.1
ping -c 5 20.10.1.1
ping 20.10.1.1 repeat 10
```

- The default probe count is five.
- Packet counts from 1 through 100 are accepted.
- Results use Cisco-style symbols and success-rate output.
- Reachability is evaluated against configured destination IPs and topology
  connections.
- Console Ping creates an Events entry and Packet Analysis records.
- A source device must have at least one configured IP address.

