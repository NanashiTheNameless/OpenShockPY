# OpenShock Python — Advanced Guide

Technical details for engineers and power users. For a simpler overview, see [README.md](<https://github.com/NanashiTheNameless/OpenShockPY/blob/main/README.md>).

## Definitions and Usage

This section lists all public definitions in the library and how to use them.

### Module overview

- `OpenShockPY.__init__`: re-exports `OpenShockClient`, `OpenShockPYError`, and optionally `AsyncOpenShockClient` (if httpx is installed).
- `OpenShockPY.client`: core HTTP client and error handling using `requests`.
- `OpenShockPY.async_client`: optional async HTTP client using `httpx` (requires `async` extras).
- `OpenShockPY.cli`: optional command-line interface (not needed when using the library directly).

### Public API (library)

- `class OpenShockPYError(Exception)`: raised for non-2xx HTTP responses or client precondition errors.

- `class OpenShockClient(api_key: Optional[str] = None, base_url: str = "https://api.openshock.app", timeout: int = 15, user_agent: Optional[str] = None)`
  - Creates a reusable client with a shared `requests.Session`.
  - A User-Agent is required; set via constructor (`user_agent=`) or `SetUA()` before any request.

  - `SetUA(user_agent: str) -> None`
    - Set/update the `User-Agent` header. Required before any API call.
    - Example:

      ```python
      client.SetUA("YourApp/1.0")
      ```

  - `SetBaseURL(base_url: str) -> None`
    - Change the API base URL (trailing slashes trimmed).
    - Example:

      ```python
      client.SetBaseURL("https://api.openshock.dev")
      ```

  - `SetAPIKey(api_key: Optional[str]) -> None`
    - Set or clear the API key used for authenticated requests.
    - Example:

      ```python
      client.SetAPIKey("YOUR_API_KEY")
      ```

  - `list_devices(api_key: Optional[str] = None) -> Any`
    - List all devices for the authenticated account.
    - Optional per-call `api_key` overrides the client’s stored key.
    - Example:

      ```python
      devices = client.list_devices()
      ```

  - `get_device(device_id: str, api_key: Optional[str] = None) -> Any`
    - Get details for a single device by ID.
    - Example:

      ```python
      device = client.get_device("device-uuid")
      ```

  - `list_shockers(device_id: Optional[str] = None, api_key: Optional[str] = None) -> Any`
    - List shockers you own, or only those attached to a given device if `device_id` is provided.
    - Example:

      ```python
      shockers = client.list_shockers()              # all owned
      shockers = client.list_shockers(device_id="d1")  # for one device
      ```

  - `get_shocker(shocker_id: str, api_key: Optional[str] = None) -> Any`
    - Get details for a single shocker by ID.
    - Example:

      ```python
      shocker = client.get_shocker("shocker-uuid")
      ```

  - `send_action(shocker_id: str, control_type: str, intensity: int = 0, duration: int = 1000, exclusive: bool = False, api_key: Optional[str] = None) -> Any`
    - Low-level method to send a control command. `control_type` is one of `"Shock"`, `"Vibrate"`, `"Sound"`, `"Stop"`.
    - Validates `intensity` (0-100) and `duration` (300-65535 ms), raising `OpenShockPYError` if out of range.
    - Example (send Stop):

      ```python
      client.send_action("shocker-uuid", "Stop")
      ```

  - `shock(shocker_id: str, intensity: int = 50, duration: int = 1000, api_key: Optional[str] = None) -> Any`
    - Convenience wrapper for `send_action(..., control_type="Shock")`.
    - Example:

      ```python
      client.shock("shocker-uuid", intensity=40, duration=1200)
      ```

  - `vibrate(shocker_id: str, intensity: int = 50, duration: int = 1000, api_key: Optional[str] = None) -> Any`
    - Convenience wrapper for `send_action(..., control_type="Vibrate")`.
    - Example:

      ```python
      client.vibrate("shocker-uuid", intensity=30, duration=800)
      ```

  - `beep(shocker_id: str, duration: int = 300, api_key: Optional[str] = None) -> Any`
    - Convenience wrapper for `send_action(..., control_type="Sound", intensity=0)`.
    - Example:

      ```python
      client.beep("shocker-uuid", duration=500)
      ```

  - `stop(shocker_id: str, api_key: Optional[str] = None) -> Any`
    - Convenience wrapper for `send_action(..., control_type="Stop")`. Stops all actions on the shocker.
    - Example:

      ```python
      client.stop("shocker-uuid")
      ```

  - `send_action_all(control_type: str, intensity: int = 0, duration: int = 1000, exclusive: bool = False, api_key: Optional[str] = None) -> Any`
    - Send an action command to all shockers. Automatically fetches all shockers and sends the command to each one.
    - Example:

      ```python
      client.send_action_all("Vibrate", intensity=30, duration=2000)
      ```

  - `shock_all(intensity: int = 50, duration: int = 1000, api_key: Optional[str] = None) -> Any`
    - Convenience wrapper to shock all shockers at once.
    - Example:

      ```python
      client.shock_all(intensity=40, duration=1200)
      ```

  - `vibrate_all(intensity: int = 50, duration: int = 1000, api_key: Optional[str] = None) -> Any`
    - Convenience wrapper to vibrate all shockers at once.
    - Example:

      ```python
      client.vibrate_all(intensity=30, duration=800)
      ```

  - `beep_all(duration: int = 300, api_key: Optional[str] = None) -> Any`
    - Convenience wrapper to beep all shockers at once.
    - Example:

      ```python
      client.beep_all(duration=500)
      ```

  - `stop_all(api_key: Optional[str] = None) -> Any`
    - Convenience wrapper to stop all actions on all shockers.
    - Example:

      ```python
      client.stop_all()
      ```

### Typical usage pattern

```python
from OpenShockPY import OpenShockClient, OpenShockPYError

client = OpenShockClient(api_key="YOUR_API_KEY", user_agent="YourApp/1.0")

# Enumerate
devices = client.list_devices()
shockers = client.list_shockers()

# Act on a single shocker
client.vibrate("shocker-uuid", intensity=25, duration=1500)
client.stop("shocker-uuid")  # Stop all actions

# Act on all shockers at once
client.vibrate_all(intensity=25, duration=1500)
client.stop_all()  # Stop all shockers
```

### CLI (optional)

Run without coding using `python -m OpenShockPY.cli <command>`.

- `devices`: list devices
- `shockers [--device-id <id>]`: list shockers (optionally filtered)
- `shock --shocker-id <id|all> [--intensity 0-100] [--duration ms]`: use "all" to shock all shockers
- `vibrate --shocker-id <id|all> [--intensity 0-100] [--duration ms]`: use "all" to vibrate all shockers
- `beep --shocker-id <id|all> [--duration ms]`: use "all" to beep all shockers
- `login [--api-key <key>]`: store key in system keyring
- `logout`: remove key from system keyring

Examples:

```bash
python -m OpenShockPY.cli login --api-key YOUR_API_KEY
python -m OpenShockPY.cli devices
python -m OpenShockPY.cli shock --shocker-id <id> --intensity 40 --duration 1200
python -m OpenShockPY.cli shock --shocker-id all --intensity 40 --duration 1200  # All shockers
```

### Async client (optional)

The `AsyncOpenShockClient` mirrors the synchronous `OpenShockClient` API but provides `async` methods. Install optional dependencies to use it:

```bash
pip install Nanashi-OpenShockPY[async]
```

#### AsyncOpenShockClient API

- `class AsyncOpenShockClient(api_key: Optional[str] = None, base_url: str = "https://api.openshock.app", timeout: int = 15, user_agent: Optional[str] = None)`
  - Creates an asynchronous client using `httpx.AsyncClient` for non-blocking HTTP requests.
  - A User-Agent is required; set via constructor (`user_agent=`) or `SetUA()` before any request.
  - Supports async context manager protocol (`async with`) for automatic resource cleanup.
  - **Note**: Unlike `OpenShockClient`, there is no `SetBaseURL()` method; set the URL via the constructor only.

  - `SetUA(user_agent: str) -> None`
    - Set/update the `User-Agent` header. Required before any API call.

  - `SetAPIKey(api_key: Optional[str]) -> None`
    - Set or clear the API key used for authenticated requests.

  - `async aclose() -> None`
    - Close the underlying `httpx.AsyncClient`. Called automatically when using context manager.

  - `async list_devices(api_key: Optional[str] = None) -> Dict[str, Any]`
    - List all devices for the authenticated account.

  - `async get_device(device_id: str, api_key: Optional[str] = None) -> Dict[str, Any]`
    - Get details for a single device by ID.

  - `async list_shockers(device_id: Optional[str] = None, api_key: Optional[str] = None) -> Dict[str, Any]`
    - List shockers you own, or only those attached to a given device if `device_id` is provided.

  - `async get_shocker(shocker_id: str, api_key: Optional[str] = None) -> Dict[str, Any]`
    - Get details for a single shocker by ID.

  - `async send_action(shocker_id: str, control_type: str, intensity: int = 0, duration: int = 1000, exclusive: bool = False, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]`
    - Low-level method to send a control command. `control_type` is one of `"Shock"`, `"Vibrate"`, `"Sound"`, `"Stop"`.
    - Validates `intensity` (0-100) and `duration` (300-65535 ms).

  - `async shock(shocker_id: str, intensity: int = 50, duration: int = 1000, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]`
    - Convenience wrapper for `send_action(..., control_type="Shock")`.

  - `async vibrate(shocker_id: str, intensity: int = 50, duration: int = 1000, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]`
    - Convenience wrapper for `send_action(..., control_type="Vibrate")`.

  - `async beep(shocker_id: str, duration: int = 300, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]`
    - Convenience wrapper for `send_action(..., control_type="Sound", intensity=0)`.

  - `async stop(shocker_id: str, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]`
    - Convenience wrapper for `send_action(..., control_type="Stop")`. Stops all actions on the shocker.

  - `async send_action_all(control_type: str, intensity: int = 0, duration: int = 1000, exclusive: bool = False, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]`
    - Send an action command to all shockers. Automatically fetches all shockers and sends the command to each one.
    - Validates parameters and raises `OpenShockPYError` if no shockers are found.

  - `async shock_all(intensity: int = 50, duration: int = 1000, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]`
    - Convenience wrapper to shock all shockers at once.

  - `async vibrate_all(intensity: int = 50, duration: int = 1000, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]`
    - Convenience wrapper to vibrate all shockers at once.

  - `async beep_all(duration: int = 300, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]`
    - Convenience wrapper to beep all shockers at once.

  - `async stop_all(api_key: Optional[str] = None) -> Optional[Dict[str, Any]]`
    - Convenience wrapper to stop all actions on all shockers.

Example:

```python
import asyncio
from OpenShockPY import AsyncOpenShockClient

async def main():
    # Using context manager (recommended)
    async with AsyncOpenShockClient(api_key="KEY", user_agent="YourApp/1.0") as client:
        # List devices and shockers
        devices = await client.list_devices()
        shockers = await client.list_shockers()
        
        # Act on a single shocker
        await client.vibrate("shocker-uuid", intensity=25, duration=1500)
        await client.stop("shocker-uuid")
        
        # Act on all shockers at once
        await client.shock_all(intensity=50, duration=1000)
        await client.stop_all()
    # Client is automatically closed when exiting the context manager

    # Or manage lifecycle manually
    client = AsyncOpenShockClient(api_key="KEY", user_agent="YourApp/1.0")
    try:
        await client.shock_all(intensity=50, duration=1000)
    finally:
        await client.aclose()

asyncio.run(main())
```

⚠️ **Experimental / Unsupported**: The `AsyncOpenShockClient` is provided as an optional, experimental API. It is not considered stable or officially supported and may change or be removed in future releases. The async client uses `httpx` and requires the `async` extras; it may not receive the same QA coverage as the synchronous client. Use at your own risk and test thoroughly before using it in production.

## Client fundamentals

- **User-Agent is required**: `OpenShockClient` will raise `OpenShockPYError` if you call the API without setting a User-Agent (set via constructor or `SetUA`).
- **Base URL**: defaults to `https://api.openshock.app`; you can change it with `SetBaseURL("https://api.openshock.dev")` or via the constructor.
- **Timeout**: default request timeout is 15 seconds.
- **Session reuse**: a single `requests.Session` is used to share connection pooling and headers across calls.

## Authentication and headers

- The API key is sent in the `Open-Shock-Token` header. Set it at construction or later with `SetAPIKey`.
- Per-call override: pass `api_key=` to any method (e.g., `client.shock(..., api_key="temporary_key")`).
- If no key is set, calls proceed without the header (the API will reject most protected endpoints).

## Endpoints and versions

- Device and shocker listing use OpenShock API **v1** (`/1/devices`, `/1/shockers/own`, `/1/devices/{device_id}/shockers`).
- Control commands use API **v2** (`/2/shockers/control`).

## Actions and validation

- Convenience methods: `shock`, `vibrate`, and `beep` all call `send_action`.
- `send_action` payload:

  ```json
  {
    "shocks": [{
      "id": "<shocker_uuid>",
      "type": "<Shock|Vibrate|Sound|Stop>",
      "intensity": <int>,
      "duration": <int_ms>,
      "exclusive": <bool>
    }],
    "customName": null
  }
  ```
  
- Both sync and async clients validate `intensity` (0-100) and `duration` (300-65535 ms), raising `OpenShockPYError` if values are out of range.
- `exclusive` defaults to `False`; set to `True` when you need exclusive control.

## Error handling

- Non-2xx responses raise `OpenShockPYError` with the HTTP status and any parsed JSON body (falls back to raw text).
- Empty 2xx responses return `None`; otherwise JSON is returned as parsed Python data.

## CLI details

- Entry point: `python -m OpenShockPY.cli <command>`.
- Commands: `devices`, `shockers`, `shock`, `vibrate`, `beep`, `login`, `logout`.
- Authentication precedence: `--api-key` > `OPENSHOCK_API_KEY` env var > key stored in system keyring.
- The CLI sets `User-Agent` to `OpenShockPY-CLI/0.0.0.11` automatically.
- Base URL override: `--base-url https://api.openshock.dev`.
- Key storage: `python -m OpenShockPY.cli login` writes to your system keyring under the service name `openshock`.
- "all" option: For `shock`, `vibrate`, and `beep` commands, use `--shocker-id all` to send the command to all shockers at once.

## Development and testing

- Editable install with all extras: `pip install -e ".[all]"`.
- Run tests: `pytest`.
- Modules of interest:
  - `OpenShockPY/client.py`: HTTP client and error handling.
  - `OpenShockPY/cli.py`: CLI argument parsing and command dispatch.

## License reminder

The project is licensed under **NNCL v1.2-MODIFIED-OpenShockPY**. It allows non-commercial, ethical use, requires source availability for adaptations, and forbids commercial exploitation without a separate license. See [LICENSE.md](<https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md>) for the full terms.
