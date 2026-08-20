# PeerNet Console and Interface Update

## Multiple-command paste

Copy a full block and paste it directly into one device console. Multiline text
is submitted once and executed line-by-line in order, preserving CLI modes.

Example:

```text
enable
configure terminal
vlan 10
name USERS
exit
interface range fa0/1 - 4
switchport mode access
switchport access vlan 10
no shutdown
end
show vlan brief
show interfaces status
```

Single-line pasting still inserts text at the current cursor position without
executing it automatically.

## Interface names

Interface lookup is case-insensitive and supports common Cisco abbreviations:

| Typed value | Matched interface |
| --- | --- |
| `interface g0/1` | `Gi0/1` |
| `interface gi0/1` | `Gi0/1` |
| `interface gigabitethernet0/1` | `Gi0/1` |
| `interface f0/1` | `Fa0/1` |
| `interface fa0/1` | `Fa0/1` |
| `interface fastethernet0/1` | `Fa0/1` |
| `interface s0/0/0` | `S0/0/0` |
| `interface tunnel0` | `Tunnel0` |
| `interface vlan10` | `Vlan10` |

Tab completion also matches lowercase `g`, `gi`, `f`, `fa`, `s`, `tunnel`,
and `vlan` prefixes while returning the canonical stored interface name.

## Switch FastEthernet ports

New network switches include:

- `Gi0/1` through `Gi0/4`
- `Fa0/1` through `Fa0/24`

When an older saved switch is loaded, missing `Fa0/9` through `Fa0/24` ports
are added without replacing existing ports or changing their configuration and
links.

Lowercase interface ranges are supported:

```text
interface range fa0/1 - 24
interface range f0/1-f0/8
interface range fastethernet0/1,fa0/3,FA0/5
```

## Local installation

Copy these files to their indicated locations:

```text
PeerNet-Network-Simulator/
├── app.py
├── switch_cli.py
├── routing_cli.py
└── terminal_component/
    └── frontend/
        └── index.html
```

Validate and start:

```powershell
python -m py_compile app.py switch_cli.py routing_cli.py
streamlit run app.py
```
