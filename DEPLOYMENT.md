# PeerNet Network Simulator - Git & Streamlit Deployment

## Supabase isolation

The Simulator may use the same Supabase project as PeerNet AI for login.
That intentionally shares only Supabase Auth (`auth.users`) so the same
account can authenticate in both applications.

Simulator labs are stored only in:

`public.simulator_projects`

The supplied `supabase/schema.sql` does not modify PeerNet AI application
tables.

## Local environment

Create `.env` locally:

```env
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_ANON_KEY=YOUR_ANON_KEY
```

Do not commit `.env`.

Run:

```powershell
streamlit run app.py
```

## GitHub

The repository should contain:

- app.py
- auth.py
- supabase_service.py
- requirements.txt
- LICENSE.txt
- README.md
- DEPLOYMENT.md
- .env.example
- .gitignore
- assets/
- topology_component/
- terminal_component/
- supabase/schema.sql
- .streamlit/config.toml

Do not commit:

- `.env`
- `.streamlit/secrets.toml`

## Streamlit Community Cloud

Set these in App settings > Secrets:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_ANON_KEY = "YOUR_ANON_KEY"
```

Main file:

`app.py`

## Wireshark

`Open in Wireshark (Local)` works only when Streamlit is running on the
same Windows machine as Wireshark. In cloud deployment, use Download PCAP.
