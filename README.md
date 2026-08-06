# PeerNet Network Simulator — Supabase Cloud Edition

A Streamlit-based logical network simulator with shared Supabase authentication and isolated per-user cloud topology storage.

## Features

- Gmail/email-password authentication using the same Supabase Auth project as PeerNet AI
- Separate `simulator_projects` table; PeerNet AI conversations and messages remain untouched
- Row Level Security so users can only access their own simulator projects
- Save, update, open, and delete cloud topologies
- Local JSON download and import
- PeerNet Solutions branding, favicon, and login artwork
- Interactive Cisco-style CLI; type a command and press Enter
- Device boot sequence, interfaces, IP addresses, static routes, ping, traceroute, and failures

## Supabase setup

1. Open the existing Supabase project used by PeerNet AI.
2. Open **SQL Editor**.
3. Run the complete file:

```text
supabase/schema.sql
```

The SQL creates only:

```text
public.simulator_projects
public.set_simulator_project_updated_at()
```

It does not alter PeerNet AI tables such as `conversations`, `messages`, `favorites`, `usage_events`, or `message_feedback`.

## Local configuration

Copy `.env.example` to `.env`:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

Do not add `SUPABASE_SERVICE_ROLE_KEY` to this simulator.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud secrets

```toml
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key"
```

## Project structure

```text
PeerNet_Network_Simulator_Supabase_Cloud/
├── app.py
├── supabase_service.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── .streamlit/
│   └── config.toml
├── assets/
│   ├── favicon.png
│   ├── login-illustration.jpg
│   └── peernet-solutions-logo.png
└── supabase/
    └── schema.sql
```


## Next-Generation upgrade in this release

This release removes the duplicate visual login form and uses a dedicated network-lab illustration.

It also adds an **Advanced Labs** foundation for:

- VLAN
- OSPF
- BGP
- ACL
- NAT overload
- DHCP
- SD-WAN identity and TLOC colors

These configurations are stored with the topology locally and in Supabase cloud projects.

> Important: PeerNet Network Simulator remains a logical learning simulator. It does not run Cisco IOS images or emulate packets at the fidelity of CML/EVE-NG yet. The included Advanced Labs form the software foundation for that roadmap.


## Colorful login edition

The login page now includes:

- Multi-color PeerNet gradient branding
- Glass-effect login and illustration cards
- Color-coded feature badges
- Improved responsive layout for phones and tablets
- The same Supabase authentication and simulator functionality


## Clean login update

- Removed the feature text below the login image
- Kept the colorful PeerNet login design
- Preserved local `.env` loading with `load_dotenv()`
