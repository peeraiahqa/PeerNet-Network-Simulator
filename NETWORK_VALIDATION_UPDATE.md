# IP, Subnet, VLAN, and Gateway Validation

PeerNet now validates addressing during configuration and provides a dedicated
**Validation** tab for topology-wide auditing.

## Blocked during configuration

- Duplicate IPv4 addresses
- Invalid addresses and subnet masks
- Network/broadcast addresses assigned to ordinary prefixes
- Default gateways outside every configured local subnet

## Validation tab audits

- Duplicate addresses
- Network/broadcast address misuse
- Off-subnet gateways
- Overlapping but non-identical connected prefixes
- Access ports referencing VLANs that do not exist
- Trunks referencing missing native or allowed VLANs
- Router subinterfaces missing `encapsulation dot1Q`
- Duplicate dot1Q VLAN IDs on the same parent interface

Errors and warnings identify the exact device and interface that needs repair.

