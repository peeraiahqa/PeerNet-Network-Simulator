# PeerNet Switch VLAN Configuration

Replace `app.py` in the project root and add `switch_cli.py` beside it.

## 1. VLAN creation and naming

```text
SW1> enable
SW1# configure terminal
SW1(config)# vlan 10
SW1(config-vlan)# name USERS
SW1(config-vlan)# exit
SW1(config)# vlan 20
SW1(config-vlan)# name VOICE
SW1(config-vlan)# end
```

## 2. Access port configuration

```text
SW1# configure terminal
SW1(config)# interface Fa0/1
SW1(config-if-Fa0/1)# description USER-PC
SW1(config-if-Fa0/1)# switchport mode access
SW1(config-if-Fa0/1)# switchport access vlan 10
SW1(config-if-Fa0/1)# no shutdown
SW1(config-if-Fa0/1)# end
```

## 3. Trunk port configuration

```text
SW1# configure terminal
SW1(config)# interface Gi0/1
SW1(config-if-Gi0/1)# description TRUNK-TO-SW2
SW1(config-if-Gi0/1)# switchport mode trunk
SW1(config-if-Gi0/1)# switchport trunk native vlan 1
SW1(config-if-Gi0/1)# switchport trunk allowed vlan 10,20
SW1(config-if-Gi0/1)# no shutdown
SW1(config-if-Gi0/1)# end
```

Allowed-VLAN changes also support:

```text
switchport trunk allowed vlan 10,20,30-40
switchport trunk allowed vlan add 50
switchport trunk allowed vlan remove 20
switchport trunk allowed vlan except 99
switchport trunk allowed vlan all
switchport trunk allowed vlan none
```

## 4. Configure multiple ports

```text
SW1# configure terminal
SW1(config)# interface range Fa0/1 - 4
SW1(config-if-range)# switchport mode access
SW1(config-if-range)# switchport access vlan 10
SW1(config-if-range)# no shutdown
SW1(config-if-range)# end
```

These forms are supported:

```text
interface range Fa0/1 - 4
interface range Fa0/1-Fa0/4
interface range Fa0/1,Fa0/3,Fa0/5
```

## 5. Verification and troubleshooting from `Switch#`

```text
show vlan brief
show interfaces status
show interfaces trunk
show interfaces Fa0/1 switchport
show running-config
show mac address-table
show spanning-tree
show cdp neighbors
```

Useful corrections:

```text
configure terminal
interface Fa0/1
no switchport access vlan
no description
exit
no vlan 10
end
```

Deleting a VLAN returns access ports using that VLAN to VLAN 1, removes that
VLAN from explicit trunk allowed lists, and resets a matching native VLAN to 1.

## Installation

Place both files as follows:

```text
PeerNet-Network-Simulator/
├── app.py
├── switch_cli.py
└── ...
```

Then validate and upload:

```powershell
python -m py_compile app.py switch_cli.py
git add app.py switch_cli.py
git commit -m "Add switch VLAN and trunk configuration"
git push origin main
```
