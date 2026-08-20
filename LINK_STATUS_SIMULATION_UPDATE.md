# Link Status Simulation

PeerNet topology links now share their operational state with the routing
engine and topology display.

## Status display

- **Up:** the connector keeps its cable color/pattern and endpoint indicators
  remain green.
- **Cable failure / down:** the connection turns red.
- **Administratively down:** the connection turns amber after `shutdown` is
  entered on either endpoint interface.

Hover over a cable to view its connector type, state, and state reason.

## Controls

The **Disconnect** tab shows the selected link state and provides reversible
**Simulate Cable Failure** and **Restore Cable** actions. A simulated failure is
saved with the topology and is honored by Ping, Traceroute, and Packet Analysis.

