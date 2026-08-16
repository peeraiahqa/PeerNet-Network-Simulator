# PeerNet Network Simulator — Functional UI Edition

This build replaces decorative/fake controls with real Streamlit interactions.

## Fixed

- Removed the oversized empty left-panel space
- Logo aligned near the top
- Functional project create/save/open/delete
- Functional device add controls
- Functional toolbar buttons
- Functional topology drag/move/connect
- Right-click device -> Configure / Interfaces
- Functional manual CLI with Enter-to-run
- Functional bottom tabs
- Supabase login and cloud project storage preserved

## Local run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

`.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```


## Router icon update
- Router nodes now use the supplied Cisco-style router image.
- Other device icons remain unchanged.
- Router asset: `assets/router.png`.


## Easy single-console configuration
- Removed the duplicate CLI tab.
- Console is now directly editable.
- Select a device, type a Cisco-style command, and press Enter.
- Right-click Configure selects that device for the same console.
- Added quick show-interface, route, running-config, and clear controls.


## Inline terminal console
- The black console is now the actual command-entry terminal.
- Click inside the console and type directly at the device prompt.
- Press Enter to execute the command and update the selected device.
- No separate CLI command text box is shown.
- Shift+Enter can be used for a line break without execution.


## Cisco-style show help and Tab completion
- `show ?` lists supported show commands for the selected device.
- `show ip ?` lists IP show subcommands.
- Router/common commands include show interfaces, show arp, show CDP neighbors, show route, running-config, startup-config and version.
- Switches additionally support show vlan brief, show mac address-table, show interfaces status and show spanning-tree.
- Tab completes a unique command prefix or prints matching commands when several matches exist.
- Unknown show commands suggest using `show ?`.


## Prefill wrapper fix
- Fixed `inline_terminal()` to accept the `prefill` argument.
- Tab completion now passes the completed/matching command back into the terminal correctly.


## Interface, hostname and topology IP improvements
- Interface names are now case-sensitive and typos no longer create new interfaces.
- Existing physical/logical interfaces must be selected exactly, e.g. `interface Gi0/0`.
- Added Cisco-style `hostname NEWNAME` in global configuration mode.
- Renaming updates topology nodes, links, connected peer references and console state.
- Configured interface IP addresses are displayed beside the interface on the topology.
- Connected interfaces are highlighted on the topology.


## Command and interface case fix
- Cisco command keywords are now case-insensitive.
- Interface identifiers remain exact/case-sensitive.
- `interface Gi0/0` works when `Gi0/0` exists.
- `interface gi0/0` is rejected with a suggestion to use `Gi0/0`.
- `interface ?` lists available interfaces.
- `interface G<Tab>` and `interface Gi0/<Tab>` show/complete matching interfaces.


## Easy connector workflow
- Devices remain freely draggable on the topology.
- Connect tab shows only free interfaces on source and destination devices.
- Explicit interface-to-interface connections are stored in each link.
- Default network devices now include more usable ports.
- Ports tab can add GigabitEthernet, FastEthernet, Serial, Fiber, Wireless or Ethernet ports.
- Connector types include Ethernet/Copper, Fiber/Optical, Serial and Wireless.
- Topology link colors/styles differ by connector type and display source/destination interface names.
- Clicking the small connector handle on a topology device selects it for the connection workflow.


## Independent scrolling
- Browser-level whole-page scrolling is locked in the simulator view.
- Left sidebar has its own scrollbar.
- Main/topology workspace scrolls independently.
- Connector/device controls on the right scroll independently.
- Scroll chaining is contained so reaching a panel edge does not move the whole app.


## Performance and scrolling fix
- Removed the previous whole-page `overflow:hidden` locking.
- Left control panel is now sticky with its own lightweight scrollbar.
- Main workspace remains normally scrollable and no longer gets stuck.
- Device dragging no longer rebuilds the full topology on every mousemove.
- During drag, only the selected device DOM element moves; links redraw after release.
- This significantly reduces browser CPU usage and topology lag.


## Login title highlight
- PeerNet is highlighted with a blue/cyan/purple gradient.
- Network Simulator remains high-contrast and readable.
- No authentication or simulator functionality was changed.


## Dashboard scroll fix
- Removed nested forced scroll containers that caused the dashboard to stick.
- Dashboard now uses one normal browser/page scroll.
- Left controls remain sticky on desktop without their own scrollbar.
- Topology canvas keeps a fixed interactive area and does not capture page scrolling.
- Mobile/tablet automatically disables sticky behavior for smoother scrolling.


## Laptop viewport layout
- Dashboard is fitted to a single desktop/laptop viewport.
- Left controls scroll only when their content exceeds the screen height.
- Topology stays in the upper-right portion of the workspace.
- Console/Ping/Traceroute/Events stay in the lower-right portion.
- The full browser page no longer needs vertical scrolling on typical laptop screens.
- Console output scrolls internally.
- Tablet/mobile automatically falls back to normal document scrolling.


## Native sidebar stability rebuild
- Removed custom two-column sticky/viewport layout.
- Uses Streamlit's native sidebar for logo, user, projects, devices, connectors, logout and license.
- Main topology/console area uses normal Streamlit document flow.
- Removed `:has()` selectors, sticky-column hacks, forced 100vh heights and nested dashboard scroll traps.
- Sidebar uses Streamlit's own scrolling behavior.
- Topology drag performance optimization remains enabled.
- This architecture is intended to behave consistently across Windows laptops, browser zoom levels and Streamlit Cloud.


## Sidebar + smooth up/down scrolling
- Streamlit native sidebar remains visible and expanded.
- Sidebar scrolls independently when its controls exceed the laptop height.
- Main topology/console page scrolls normally from top to bottom.
- Removed forced viewport locks, sticky columns, and nested dashboard scroll traps.
- Console keeps its own scrollbar only for long command output.


## Login rollback
- Restored the login layout shown in the reference screenshot.
- Solid dark-blue PeerNet Network Simulator heading centered at the top.
- PeerNet logo restored above the login tabs on the left.
- Login/create-account/forgot-password form remains on the left.
- Simulator promotional image remains on the right.


## Stable rollback
- Restored stable freely scrolling dashboard.
- Removed permanent custom sidebar JavaScript and MutationObserver.
- Removed forced viewport locking.
- Login page remains in approved rollback style.


## Fixed topology component icon build
- Rebuilt from the stable topology frontend.
- Multilayer/L3 Switch icon updated.
- PC icon updated.
- Router icon preserved.
- Removed the malformed duplicated JavaScript introduced by the prior icon patch.
- Component still calls `Streamlit.ready()` correctly.
- JavaScript syntax validated with Node.js.


## PC console and right-click device controls
- PC/Laptop/Server console now supports `ip <address> <mask> [gateway]`.
- Added `ipconfig`, `ipconfig /all`, `gateway`, `dns`, `ping`, `tracert`, `arp -a`, `route print`, `hostname`, `help`, and `clear`.
- Right-click menu works on topology devices and includes Configure, Open Console, Interfaces, Add Interface, and Delete Device.
- PC Configure opens an IP configuration dialog with IP address, subnet mask, gateway, and DNS.
- Network-device Configure continues to select the device for the shared Cisco-style console.
- Added interface dialog can create additional GigabitEthernet, FastEthernet, Ethernet, Serial, Fiber, or Wireless ports.


## Ping / Traceroute output display
- Ping result now appears directly below the Run Ping button.
- Traceroute result now appears directly below the Run Traceroute button.
- Results stay visible until another test is run or the output is cleared.
- Traceroute uses the current topology links to show the logical hop path.


## Packet Analysis and Wireshark tabs
- Added separate Packet Analysis and Wireshark tabs.
- Ping and Traceroute record simulated hop-by-hop ICMP packet data.
- Packet Analysis shows Layer 2, Layer 3, Layer 4, TTL and forwarding decisions.
- Wireshark tab generates a standard Ethernet PCAP capture.
- Download PCAP works locally and on Streamlit Cloud.
- Open in Wireshark (Local) launches installed Wireshark when the app is running on the same Windows PC.


## Colored Clear buttons
- Ping Output has a blue Clear Ping Output button beside the title.
- Traceroute Output has a purple Clear Traceroute Output button beside the title.
- Packet Analysis has an orange Clear Packet Analysis button beside the title.
- Wireshark has a cyan Clear Capture button beside the title.
- Events has a red Clear Events button beside the title.
- Ping and Traceroute actions are recorded in the Events log.


## Main dashboard scrolling
- Main topology/dashboard area now scrolls vertically inside the browser viewport.
- Sidebar CSS/behavior was intentionally left unchanged.
- Topology component does not create a second vertical scrollbar.
- Console/results keep internal scrolling only when output becomes long.
- Added a visible, lightweight main dashboard scrollbar.


## Toolbar colors and compact test buttons
- Select is blue.
- Connect is green.
- Move is purple.
- Delete is red.
- Full is orange.
- Run Ping and Run Traceroute are now compact buttons instead of full-width controls.


## Visual Team/VLAN Zones
- Added colored topology bubbles for HR, Finance, Admin, IT or custom teams.
- Team label, VLAN ID, network, gateway, DHCP scope, DNS and color are editable.
- Team zones are saved/restored with topology projects.
- Added Teams tab and Quick Commands.
- Existing simulator functionality remains intact.


## Login-only redesign
- Centered the PeerNet Solutions logo in the authentication area.
- Added a rounded boxed Login / Create account / Forgot password area.
- Colorized `PeerNet Network Simulator` with blue/cyan branding.
- Preserved the existing side login illustration.
- Dashboard, sidebar, topology and simulator functionality were not redesigned in this build.


## Final deployment/auth structure
- Restored `auth.py` as the authentication facade.
- Authentication can share the same Supabase Auth users as PeerNet AI.
- Simulator data remains isolated in `public.simulator_projects`.
- The included SQL does not modify PeerNet AI application tables.
- `.env` and Streamlit secrets are excluded from Git.
- See `DEPLOYMENT.md` before pushing to GitHub/Streamlit Cloud.
