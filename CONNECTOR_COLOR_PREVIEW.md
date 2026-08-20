# PeerNet Connector Color Preview

The **Connect** tab now shows a live visual cable sample immediately below the
**Connector type** selector.

| Connector | Topology appearance | Meaning |
| --- | --- | --- |
| Ethernet / Copper | Solid dark line | Standard wired Ethernet |
| Fiber / Optical | Thick purple line | Optical fiber connection |
| Serial | Dashed amber line | Serial WAN connection |
| Wireless | Dotted blue line | Wireless connection |

Changing the selected connector updates the sample instantly. The preview uses
the same colors and line patterns as the actual topology renderer, so the cable
created on the canvas matches what the user selected.

This change affects only the connector preview UI. It does not change stored
links, topology compatibility, interface assignment, routing, VLANs, link
disconnect behavior, or parallel cable rendering.
