# Live Packet Animation

Successful Ping and Traceroute operations now animate blue packet pulses across
the exact path returned by `routing_engine.py`.

## Behavior

- Works with Ping tab, Traceroute tab, and device-console Ping.
- Animates each hop in forwarding order.
- Follows curved links and the selected member of parallel links.
- Displays an ICMP tooltip on the moving packet.
- Repeats three times so the path is easy to observe.
- Clears stale animation when routing fails.
- Does not change saved topology data or cable styling.

Run the Ping or Traceroute again to replay the animation.

