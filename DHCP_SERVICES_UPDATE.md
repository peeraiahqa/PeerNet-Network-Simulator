# DHCP Services Update

PeerNet routers and multilayer switches now provide Cisco-style DHCP pools. PCs can obtain and release addresses through their own console. Allocation follows active topology links, avoids configured exclusions and existing addresses, and persists DHCP configuration in running/startup configuration.

## Configure a DHCP router

```text
R1> enable
R1# configure terminal
R1(config)# ip dhcp excluded-address 192.168.10.1 192.168.10.9
R1(config)# ip dhcp pool USERS
R1(dhcp-config)# network 192.168.10.0 255.255.255.0
R1(dhcp-config)# default-router 192.168.10.1
R1(dhcp-config)# dns-server 8.8.8.8
R1(dhcp-config)# lease 1
R1(dhcp-config)# end
R1# show ip dhcp pool
R1# show ip dhcp binding
R1# copy running-config startup-config
```

The router must have an active interface in the pool's subnet, such as `192.168.10.1/24`.

## PC commands

```text
PC1> ipconfig /renew
PC1> ipconfig /all
PC1> ipconfig /release
```

If the PC cannot reach a configured DHCP device through active links, renewal reports that no reachable pool is available.
