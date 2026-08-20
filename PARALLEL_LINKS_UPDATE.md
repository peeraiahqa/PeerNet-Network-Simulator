# PeerNet Parallel Link Rendering

Multiple connections between the same two devices are now displayed as
separate cables instead of overlapping as one line.

For three connections between `SW1` and `SW2`, the topology renders:

- one curved cable on the first side;
- one center cable;
- one curved cable on the opposite side.

Additional links receive progressively larger offsets. Each path retains its
own link ID, connector color/style, and device-interface label, for example:

```text
SW1:Fa0/1 ↔ SW2:Fa0/1
SW1:Fa0/2 ↔ SW2:Fa0/2
SW1:Gi0/1 ↔ SW2:Gi0/1
```

Moving either device recalculates every curve automatically. Disconnecting a
selected link removes only that cable; the remaining paths are re-centered.

The implementation supports Ethernet, fiber, serial, and wireless connector
styles and does not change saved link data or existing project compatibility.
