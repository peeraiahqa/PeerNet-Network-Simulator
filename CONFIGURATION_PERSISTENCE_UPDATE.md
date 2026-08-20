# Cisco-Style Configuration Persistence

Network devices now maintain separate running and startup configurations.

## Commands

```text
copy running-config startup-config
copy run start
write memory
wr mem
show startup-config
reload
erase startup-config
write erase
```

## Behavior

- Copy/write commands take a deep snapshot of interface, VLAN and routing
  configuration.
- `show startup-config` displays the saved snapshot, not live running state.
- `reload` discards unsaved configuration changes and restores the snapshot.
- Physical topology cables remain connected across a device reload.
- `erase startup-config` removes the saved configuration.
- Startup configurations persist when the whole PeerNet project is saved and
  reopened.
- Commands that change persistent state require privileged EXEC mode.

