# PeerNet Link Disconnect Update

## Remove a connection from the right-side panel

1. Open the **Disconnect** tab.
2. Select the exact active connection.
3. Review the source-device and destination-device interface assignments.
4. Select **Confirm removal of this cable**.
5. Click **Disconnect Link**.

Only the selected cable is removed. Both devices and their configurations are
preserved. The two endpoint interfaces become free/unassigned.

## Remove a connection from a device

1. Right-click the device in the topology.
2. Select **Disconnect Link**.
3. Select one of that device's active connections.
4. Confirm and disconnect it.

This is useful when a device has several links. The dialog lists only cables
connected to the selected device.

## Connection display

Every cable is displayed with its device-side assignment:

```text
SW1:Fa0/1 ↔ PC1:eth0
```

Free interface selectors in the **Connect** tab show only the available port
name for a cleaner workflow:

```text
Fa0/2
eth1
```

The selected source and destination device names remain visible in their own
device selectors. Device-side assignments and `unassigned` status remain
visible on the topology and in connection/interface details.

The Interfaces dialog continues to show IP assignment, administrative status,
usage state, and connected peer. After disconnection, an interface shows
`unassigned`, `FREE`, and `not connected` as applicable.

## Safety behavior

- Devices are never deleted by Disconnect Link.
- VLAN, routing, IP, description, and shutdown configuration remain unchanged.
- Both endpoint `connected_to` references are cleared together.
- Only the selected link ID is removed.
- Parallel cables between the same two devices remain connected.
- Connect and disconnect operations are written to the Events log.
- Deleting a device now uses the same centralized cleanup logic, preventing
  stale peer-interface assignments.

## Updated project files

```text
app.py
switch_cli.py
routing_cli.py
terminal_component/frontend/index.html
topology_component/frontend/index.html
```

Validate locally:

```powershell
python -m py_compile app.py switch_cli.py routing_cli.py
streamlit run app.py
```
