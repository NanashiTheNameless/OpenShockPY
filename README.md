# OpenShock Python [![Ask DeepWiki](<https://deepwiki.com/badge.svg>)](<https://deepwiki.com/NanashiTheNameless/OpenShockPY>)

Unofficial, lightweight helper for the OpenShock API. Designed to be easy to use for anyone, with optional advanced controls for developers.

## What this project offers

- Simple Python client to list devices/shockers and send actions (shock, vibrate, beep).
- Optional CLI for quick checks without writing code.
- Keeps your API key in memory only; the CLI can store it securely via your system keyring.

### License TL;DR (see full [LICENSE.md](<https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md>) for complete terms)

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
   from OpenShockPY import OpenShockClient, OpenShockPYError

   client = OpenShockClient(
       api_key="YOUR_API_KEY",
       user_agent="YourAppName/YourAppVersion",
   )
   ```

4. List devices or send an action:

   ```python
   print(client.list_devices())
   client.shock("YOUR_SHOCKER_ID", intensity=50, duration=1000)
   
   # Or send to all shockers at once using "all" as the shocker ID
   client.shock("all", intensity=50, duration=1000)
   # Alternatively, use the explicit *_all methods
   client.shock_all(intensity=50, duration=1000)
   ```

5. (Optional) Use as a context manager for automatic cleanup:

   ```python
   with OpenShockClient(api_key="YOUR_API_KEY", user_agent="YourAppName/YourAppVersion") as client:
       client.list_devices()
   # Session is automatically closed when the block exits
   ```

   > Note: The client also cleans up automatically when garbage collected, so the context manager is optional.

## Optional CLI (no coding needed)

Install with CLI support:

```bash
pip install "Nanashi-OpenShockPY[cli]"
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

Or send a command to all shockers at once:

```bash
python -m OpenShockPY.cli shock --shocker-id all --intensity 40 --duration 1500
```

The CLI automatically sets an appropriate User-Agent.

## Async client (opt-in)

If you prefer non-blocking operation, there is an experimental asynchronous client available: `AsyncOpenShockClient`.
Install the optional dependencies:

```bash
pip install Nanashi-OpenShockPY[async]
```

Usage:

```python
import asyncio
from OpenShockPY import AsyncOpenShockClient

async def main():
    async with AsyncOpenShockClient(api_key="YOUR_API_KEY", user_agent="YourAppName/YourAppVersion") as client:
        devices = await client.list_devices()
        await client.shock_all(intensity=50, duration=1000)

asyncio.run(main())
```

⚠️ **Experimental / Unsupported**: The `AsyncOpenShockClient` is an opt-in, experimental client provided for convenience. It is not officially supported or fully tested in production scenarios. Use at your own risk — APIs, behavior, or method signatures may change without notice. If stability and long-term support are required, prefer the synchronous `OpenShockClient`.

## Installation options

- Library only (most people): `pip install Nanashi-OpenShockPY`
- Library + CLI extras (adds keyring): `pip install "Nanashi-OpenShockPY[cli]"`
- Library + Async extras (adds httpx, pytest-asyncio, respx): `pip install "Nanashi-OpenShockPY[async]"`
- Library + all extras: `pip install "Nanashi-OpenShockPY[all]"`
- Development/editable install from this repo: `pip install -e .` (or `pip install -e ".[cli]"` for CLI, `pip install -e ".[all]"` for all extras)

## Responsible use and licensing

- This project is for non-commercial, ethical use only. Commercial use requires a separate license.
- Respect local laws and the rights and safety of others when issuing control commands.
- Full terms: [LICENSE.md](<https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md>).

## Need more detail?

Advanced options, API notes, and developer tips are available in [ADVANCED.md](<https://github.com/NanashiTheNameless/OpenShockPY/blob/main/ADVANCED.md>).
