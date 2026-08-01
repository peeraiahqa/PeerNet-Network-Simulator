# PeerNet Solutions Network Simulator

A lightweight browser-based network simulator built with Python and Streamlit.

## Features

- Add routers, switches, PCs and interfaces
- Connect devices with virtual links
- Configure IPv4 addresses using CIDR notation
- Simulate ping reachability using active topology paths
- Run Cisco-style commands
- Load a ready-made demonstration topology
- View simulation event logs

## Run locally

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL shown by Streamlit, normally `http://localhost:8501`.

## Deploy with the PeerNet Solutions URL

1. Upload this folder to a GitHub repository.
2. Sign in to Streamlit Community Cloud.
3. Select the repository and choose `app.py`.
4. Choose the app subdomain `peernet-solutions` if it is available.
5. The resulting URL will look like:

```text
https://peernet-solutions.streamlit.app
```

A custom domain such as `https://simulator.peernetsolutions.com` requires purchasing the domain and configuring DNS through a hosting platform that supports custom domains.

## Current scope

This is a logical simulator, not a full packet-level emulator. It can be extended with VLAN, STP, ARP, static routing, OSPF, BGP, REST APIs and PyATS integration.
