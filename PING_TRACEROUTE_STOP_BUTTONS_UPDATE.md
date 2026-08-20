# Ping and Traceroute Stop Controls

The Ping and Traceroute tabs now include dedicated colored animation controls.

- **Run Ping:** blue
- **Stop Ping:** red
- **Run Traceroute:** purple
- **Stop Traceroute:** orange

Stopping clears the active packet animation immediately and records an Events
entry. Animations also expire automatically after their final pass, preventing
an old animation from restarting when a topology device is selected or moved.

