# OpenShock Python

Unofficial, lightweight helper for the OpenShock API. Designed to be easy to use for anyone, with optional advanced controls for developers.

## What this project offers

- Simple Python client to list devices/shockers and send actions (shock, vibrate, beep).
- Optional CLI for quick checks without writing code.
- Keeps your API key in memory only; the CLI can store it securely via your system keyring.

### License TL;DR (see full [LICENSE.md](LICENSE.md) for complete terms)

- Free for non-commercial, ethical use; you may study, modify, and share it.
- You can include it in other open-source projects as a separate library component.
- You must share source code for adaptations you distribute.
- No commercial use, monetization, or commercial AI training without a separate license.
- Adaptations must keep this license (unless used as a distinct component as allowed in Section 6A).

## Quick start (Python)

1. Install the library:

   ```bash
   pip install Nanashi-OpenShockPY
   ```

2. Get your OpenShock API key from your account dashboard.
3. Create a client with a User-Agent and your API key:

   ```python
   from OpenShockPY import OpenShockClient

   client = OpenShockClient(
       api_key="YOUR_API_KEY",
       user_agent="YourAppName/1.0",
   )
   ```

4. List devices or send an action:

   ```python
   print(client.list_devices())
   client.shock("YOUR_SHOCKER_ID", intensity=50, duration=1000)
   ```

## Optional CLI (no coding needed)

Install with CLI support:

```bash
pip install Nanashi-OpenShockPY[cli]
```

Store your API key securely, then list devices:

```bash
python -m OpenShockPY.cli login --api-key YOUR_KEY
python -m OpenShockPY.cli devices
```

Send a command (use a shocker ID, not a device ID):

```bash
python -m OpenShockPY.cli shock --shocker-id YOUR_SHOCKER_ID --intensity 40 --duration 1500
```

The CLI automatically sets an appropriate User-Agent.

## Installation options

- Library only (most people): `pip install Nanashi-OpenShockPY`
- Library + CLI extras (adds keyring): `pip install Nanashi-OpenShockPY[cli]`
- Development/editable install from this repo: `pip install -e .` (or `pip install -e ".[cli]"` for CLI)

## Responsible use and licensing

- This project is for non-commercial, ethical use only. Commercial use requires a separate license.
- Respect local laws and the rights and safety of others when issuing control commands.
- Full terms: [LICENSE.md](LICENSE.md).

## Need more detail?

Advanced options, API notes, and developer tips are available in [ADVANCED.md](ADVANCED.md).
