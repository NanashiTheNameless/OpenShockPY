# OpenShock Python — Advanced Guide

Technical details for engineers and power users. For a simpler overview, see [README.md](<https://github.com/NanashiTheNameless/OpenShockPY/blob/main/README.md>).

## Definitions and Usage

This section lists all public definitions in the library and how to use them.

### Module overview

- `OpenShockPY.__init__`: re-exports the clients, the error hierarchy, the response types, and `__version__`. `AsyncOpenShockClient` is imported lazily, so `httpx` stays optional.
- `OpenShockPY._core`: shared, transport-agnostic pieces — errors, response types, validation, payload building and the retry policy. Both clients use it, so they cannot drift apart. Internal; import from the package root instead.
- `OpenShockPY.client`: synchronous HTTP client built on `requests`.
- `OpenShockPY.async_client`: optional async HTTP client built on `httpx` (requires the `async` extras).
- `OpenShockPY.cli`: optional command-line interface (not needed when using the library directly).

### Errors

All errors derive from `OpenShockPYError`, so `except OpenShockPYError` catches everything the library raises.

| Class | Raised when |
| --- | --- |
| `OpenShockPYError` | Base class. Carries `.message`, `.status_code`, `.payload`. |
| `OpenShockValidationError` | Client-side validation failed, before any request was sent. Also subclasses `ValueError`. |
| `OpenShockConnectionError` | The request could not be completed (DNS, TLS, timeout). |
| `OpenShockAPIError` | Non-2xx response with no more specific subclass. |
| `OpenShockAuthError` | HTTP 401 / 403. |
| `OpenShockNotFoundError` | HTTP 404. Also raised locally when an `*_all` call finds no shockers. |
| `OpenShockRateLimitError` | HTTP 429. Adds `.retry_after` in seconds when the server sends it. |
| `OpenShockServerError` | HTTP 5xx. |

```python
from OpenShockPY import OpenShockRateLimitError, OpenShockPYError

try:
    client.shock("shocker-uuid", intensity=40)
except OpenShockRateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
except OpenShockPYError as e:
    print(f"Failed with HTTP {e.status_code}: {e.payload}")
```

### Types

Exported for IDE autocompletion and type checking. Every `TypedDict` uses `total=False`, so a partial response is not a type error.

- `ControlType`: `"Stop" | "Shock" | "Vibrate" | "Sound"`
- `ShockerModel`: `"CaiXianlin" | "PetTrainer" | "Petrainer998DR" | "WellturnT330"`
- `PermissionType`: `"shockers.use" | "shockers.edit" | "shockers.pause" | "devices.edit" | "devices.auth"`
- `SortDirection`: `"Ascending" | "Descending"`
- `Control`: one entry of the `shocks` array
- `Shocker`, `Device`, `ShockerPermissions`, `ShockerLimits`
- `DeviceListResponse`, `DeviceResponse`, `ShockerListResponse`, `ShockerResponse`, `OwnShockerListResponse`, `ActionResponse`

### Public API (library)

- `class OpenShockClient(api_key: Optional[str] = None, base_url: str = "https://api.openshock.app", timeout: float = 15.0, user_agent: Optional[str] = None, max_retries: int = 2, backoff_factor: float = 0.5)`
  - Creates a reusable client with a shared `requests.Session`.
  - A User-Agent is required; set via constructor (`user_agent=`) or `SetUA()` before any request.

`AsyncOpenShockClient` takes the same constructor arguments and exposes the same methods, with `async def` in place of `def` and `aclose()` in place of `close()`. This parity is enforced by a test.

#### Configuration

| Method | Description |
| --- | --- |
| `SetUA(user_agent)` | Set the `User-Agent` header. Required before any API call. |
| `SetBaseURL(base_url)` | Change the API base URL (whitespace and trailing slashes trimmed). Now available on the async client too. |
| `SetAPIKey(api_key)` | Set or clear the API token. |
| `SetSessionToken(session_token)` | Authenticate with a user session token instead of an API token. |
| `close()` / `await aclose()` | Close the underlying transport. Idempotent. |

Each has a snake_case alias: `set_user_agent`, `set_base_url`, `set_api_key`, `set_session_token`.

```python
client.SetUA("YourAppName/YourAppVersion")
client.SetBaseURL("https://api.openshock.dev")
client.SetAPIKey("YOUR_API_KEY")
```

#### Control actions

- `send_action(shocker_id, control_type, intensity=0, duration=1000, exclusive=False, api_key=None, custom_name=None)`
  - Low-level single control. `control_type` is one of `"Shock"`, `"Vibrate"`, `"Sound"`, `"Stop"`.
  - Validates `intensity` (0-100) and `duration` (300-65535 ms), raising `OpenShockValidationError` if out of range.
  - Pass `"all"` as `shocker_id` to route to `send_action_all()`. **This now works on the async client too**; previously the async client sent a literal id of `"all"`.

- `shock(shocker_id, intensity=50, duration=1000, api_key=None, exclusive=False, custom_name=None)`
- `vibrate(shocker_id, intensity=50, duration=1000, api_key=None, exclusive=False, custom_name=None)`
- `beep(shocker_id, duration=300, api_key=None, exclusive=False, custom_name=None)`
- `stop(shocker_id, api_key=None, custom_name=None)`
  - Convenience wrappers. Each accepts `"all"` as the shocker id.

- `send_action_all(control_type, intensity=0, duration=1000, exclusive=False, api_key=None, custom_name=None)`
- `shock_all(...)`, `vibrate_all(...)`, `beep_all(duration=300, ...)`, `stop_all(api_key=None, custom_name=None)`
  - Look shockers up via `list_shockers()`, **de-duplicate by id**, and send one control each, as a single request so the action applies atomically.
  - Raises `OpenShockNotFoundError` if the account has no shockers.

- `control(controls, custom_name=None, api_key=None)`
  - Send an arbitrary, heterogeneous batch in one request — different types, intensities and durations per shocker.

  ```python
  from OpenShockPY import build_control

  client.control([
      build_control("shocker-a", "Vibrate", 30, 1000),
      build_control("shocker-b", "Sound", 0, 500),
  ], custom_name="alarm")
  ```

- `custom_name` sets the label the shocker's owner sees in their control log. `exclusive=True` cancels other running commands on that shocker.

#### Hubs and devices

| Method | Endpoint |
| --- | --- |
| `list_devices()` | `GET /1/devices` |
| `get_device(device_id)` | `GET /1/devices/{deviceId}` |
| `create_device()` | `POST /1/devices` |
| `edit_device(device_id, name)` | `PATCH /1/devices/{deviceId}` |
| `delete_device(device_id)` | `DELETE /1/devices/{deviceId}` |
| `regenerate_device_token(device_id)` | `PUT /1/devices/{deviceId}` |
| `get_device_pair_code(device_id)` | `GET /1/devices/{deviceId}/pair` |
| `get_device_lcg(device_id)` | `GET /1/devices/{deviceId}/lcg` |
| `get_device_lcg_v2(device_id)` | `GET /2/devices/{deviceId}/lcg` |
| `get_device_ota_updates(device_id)` | `GET /1/devices/{deviceId}/ota` |

#### Shockers

| Method | Endpoint |
| --- | --- |
| `list_shockers(device_id=None)` | `GET /1/devices/{deviceId}/shockers`, else `GET /1/shockers/own` |
| `list_own_shockers()` | `GET /1/shockers/own` |
| `list_shared_shockers()` | `GET /1/shockers/shared` |
| `get_shocker(shocker_id)` | `GET /1/shockers/{shockerId}` |
| `create_shocker(device_id, name, rf_id, model)` | `POST /1/shockers` |
| `edit_shocker(shocker_id, device_id, name, rf_id, model)` | `PATCH /1/shockers/{shockerId}` |
| `delete_shocker(shocker_id)` | `DELETE /1/shockers/{shockerId}` |
| `pause_shocker(shocker_id, paused)` | `POST /1/shockers/{shockerId}/pause` |
| `get_shocker_logs(shocker_id, offset=None, limit=None)` | `GET /1/shockers/{shockerId}/logs` |
| `get_logs(page=None, page_size=None, search=None, sort=None, sort_dir=None, shocker_ids=None)` | `GET /1/shockers/logs` |

`edit_shocker` requires the full record — the API's `NewShocker` body has no partial form, so every field must be supplied even when only one is changing.

**Two different response shapes.** `list_shockers()` with no argument returns hubs with their shockers *nested* (`OwnShockerListResponse`). With a `device_id` it returns a *flat* shocker array (`ShockerListResponse`). Use `list_own_shockers()` when you want the nested form explicitly.

#### Shares

| Method | Endpoint |
| --- | --- |
| `list_public_shares()` | `GET /1/shares/links` |
| `create_public_share(name, expires_on=None)` | `POST /1/shares/links` |
| `delete_public_share(public_share_id)` | `DELETE /1/shares/links/{publicShareId}` |
| `get_public_share(public_share_id)` | `GET /1/public/shares/links/{publicShareId}` |
| `add_shocker_to_public_share(public_share_id, shocker_id, permissions, limits)` | `POST /1/shares/links/{publicShareId}/{shockerId}` |
| `remove_shocker_from_public_share(public_share_id, shocker_id)` | `DELETE /1/shares/links/{publicShareId}/{shockerId}` |
| `list_shocker_shares(shocker_id)` | `GET /1/shockers/{shockerId}/shares` |
| `list_user_shares()` | `GET /2/shares/user` |
| `create_share_invite(shockers, user=None)` | `POST /2/shares/user/invites` |
| `list_incoming_share_invites()` | `GET /2/shares/user/invites/incoming` |
| `list_outgoing_share_invites()` | `GET /2/shares/user/invites/outgoing` |
| `accept_share_invite(invite_id)` | `POST /2/shares/user/invites/incoming/{inviteId}` |
| `decline_share_invite(invite_id)` | `DELETE /2/shares/user/invites/incoming/{inviteId}` |
| `cancel_share_invite(invite_id)` | `DELETE /2/shares/user/invites/outgoing/{inviteId}` |
| `update_user_shares(user_id, shockers, permissions, limits)` | `PATCH /2/shares/user/{userId}/shockers` |
| `pause_user_shares(user_id, shockers, paused)` | `POST /2/shares/user/{userId}/shockers/pause` |
| `remove_user_shares(user_id, shockers)` | `DELETE /2/shares/user/{userId}/shockers` |

#### Tokens

| Method | Endpoint |
| --- | --- |
| `list_tokens()` | `GET /2/tokens` |
| `get_token(token_id)` | `GET /2/tokens/{tokenId}` |
| `get_self_token()` | `GET /2/tokens/self` |
| `create_token(name, permissions, shocker_control, valid_until=None)` | `POST /2/tokens` |
| `edit_token(token_id, name, permissions, shocker_control)` | `PATCH /2/tokens/{tokenId}` |
| `set_token_paused(token_id, paused)` | `PATCH /2/tokens/{tokenId}/paused` |
| `delete_token(token_id)` | `DELETE /1/tokens/{tokenId}` — v1, as v2 has no delete |
| `report_tokens(secrets)` | `POST /2/tokens/report` |

#### Account, users and sessions

| Method | Endpoint |
| --- | --- |
| `get_self()` | `GET /1/users/self` |
| `get_user_by_name(username)` | `GET /1/users/by-name/{username}` |
| `list_sessions()` | `GET /1/sessions` |
| `get_self_session()` | `GET /1/sessions/self` |
| `delete_session(session_id)` | `DELETE /1/sessions/{sessionId}` |
| `logout()` | `POST /1/account/logout` |
| `get_public_stats()` | `GET /1/public/stats` |

Administrative endpoints (`/1/admin/*`) are deliberately not wrapped.

#### Per-call API key

Every endpoint method accepts `api_key=` to override the stored token for that one call. Passing an empty string sends the request unauthenticated even when a key is stored on the client.

```python
client.list_devices(api_key="temporary_key")
client.get_public_stats(api_key="")  # no auth header
```

### Typical usage pattern

```python
from OpenShockPY import OpenShockClient, OpenShockPYError

with OpenShockClient(api_key="YOUR_API_KEY", user_agent="YourAppName/YourAppVersion") as client:
    # Enumerate
    devices = client.list_devices()
    shockers = client.list_shockers()

    # Act on a single shocker
    client.vibrate("shocker-uuid", intensity=25, duration=1500)
    client.stop("shocker-uuid")

    # Act on all shockers at once
    client.vibrate_all(intensity=25, duration=1500)
    client.stop_all()
```

### CLI (optional)

Installed as an `openshock` entry point, and also runnable as `python -m OpenShockPY.cli <command>`.

- `devices`: list hubs
- `shockers [--device-id <id>]`: list shockers (optionally filtered)
- `shock --shocker-id <id|all> [--intensity 0-100] [--duration ms]`
- `vibrate --shocker-id <id|all> [--intensity 0-100] [--duration ms]`
- `beep --shocker-id <id|all> [--duration ms]`
- `stop --shocker-id <id|all>`
- `pause --shocker-id <id>` / `unpause --shocker-id <id>`
- `logs [--shocker-id <id>]`: control logs, for one shocker or across the account
- `whoami`: the authenticated user
- `tokens`: list API tokens
- `login [--api-key <key>]`: store key in system keyring
- `logout`: remove key from system keyring

Shared flags: `--api-key`, `--base-url`, `--timeout`, `--user-agent`, `--exclusive`, `--custom-name`, `--version`.

```bash
openshock login --api-key YOUR_API_KEY
openshock devices
openshock shock --shocker-id <id> --intensity 40 --duration 1200
openshock shock --shocker-id all --intensity 40 --duration 1200  # All shockers
openshock vibrate --shocker-id <id> --exclusive --custom-name "my script"
```

### Async client (optional)

`AsyncOpenShockClient` mirrors `OpenShockClient` method for method. Install the optional dependencies:

```bash
pip install Nanashi-OpenShockPY[async]
```

Differences from the sync client:

- Every endpoint method is `async` and must be awaited.
- `await aclose()` instead of `close()`; supports `async with`.
- `asyncio.gather` can be used to fan several calls out concurrently over the one shared connection pool.

```python
import asyncio
from OpenShockPY import AsyncOpenShockClient

async def main():
    async with AsyncOpenShockClient(api_key="KEY", user_agent="YourAppName/YourAppVersion") as client:
        devices = await client.list_devices()
        shockers = await client.list_shockers()

        await client.vibrate("shocker-uuid", intensity=25, duration=1500)
        await client.stop("shocker-uuid")

        await client.shock_all(intensity=50, duration=1000)
        await client.stop_all()

asyncio.run(main())
```

If `httpx` is not installed, importing `AsyncOpenShockClient` raises an `ImportError` naming the extra to install:

```python
try:
    from OpenShockPY import AsyncOpenShockClient
except ImportError:
    AsyncOpenShockClient = None
```

⚠️ **Experimental / Unsupported**: The `AsyncOpenShockClient` is provided as an optional, experimental API. It is not considered stable or officially supported and may change or be removed in future releases. The async client uses `httpx` and requires the `async` extras. Use at your own risk and test thoroughly before using it in production.

## Client fundamentals

- **User-Agent is required**: both clients raise `OpenShockValidationError` if you call the API without setting a User-Agent (set via constructor or `SetUA`).
- **Base URL**: defaults to `https://api.openshock.app`; change it with `SetBaseURL("https://api.openshock.dev")` or via the constructor. An empty base URL raises rather than producing broken request URLs.
- **Timeout**: default request timeout is 15 seconds.
- **Connection reuse**: a single `requests.Session` / `httpx.AsyncClient` shares connection pooling and headers across calls.
- **Closing**: `close()` / `aclose()` are idempotent. Using a closed client raises `OpenShockPYError` rather than an `AttributeError`.

## Authentication and headers

- The API token is sent in the `OpenShockToken` header — the name the API documents and the server's own `AuthConstants.ApiTokenHeaderName`. The legacy `Open-Shock-Token` header is sent alongside it, because the server still accepts that spelling and older self-hosted deployments may only understand it.
- Session authentication is supported via `SetSessionToken()`, which sends both the `OpenShockSession` header and the `openShockSession` cookie — the two forms the API reads.
- Per-call override: pass `api_key=` to any method. An empty string forces an unauthenticated request.
- If no credentials are set, calls proceed without an auth header (the API will reject most protected endpoints).

## Endpoints and versions

- Hubs, shockers, shares, logs, sessions and users use OpenShock API **v1**.
- Control commands, tokens and user-to-user shares use API **v2**.
- Reference: [v1](https://api.openshock.app/scalar/viewer/#version-1) and [v2](https://api.openshock.app/scalar/viewer/#version-2). Raw schemas: `https://api.openshock.app/swagger/1/swagger.json` and `.../swagger/2/swagger.json`.

## Actions and validation

- Convenience methods `shock`, `vibrate`, `beep` and `stop` all route through `send_action`.
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

- Both clients validate `intensity` (0-100) and `duration` (300-65535 ms) against the API's `Control` schema, raising `OpenShockValidationError` if out of range or not an integer.
- `exclusive` defaults to `False`; set to `True` when you need exclusive control.
- `ControlRequest.shocks` declares no `maxItems` in either API version, so the library imposes no client-side cap; an oversized batch is the server's call to reject.

## Error handling

- Non-2xx responses raise the matching `OpenShockPYError` subclass, carrying `.status_code` and the parsed `.payload` (falling back to raw text). Messages prefer the API's `detail` or `title` field.
- Empty 2xx responses return `None`; otherwise JSON is returned as parsed Python data.

## Retries and rate limiting

Both clients retry up to `max_retries` times (default 2) with exponential backoff from `backoff_factor` (default 0.5s), honouring `Retry-After` when the server sends it.

**Retries are scoped for safety.** A control request is a `POST`, and a 5xx or a timeout is ambiguous — the shock may already have been delivered and only the response lost. So:

- HTTP 429 is always retried; the request was rejected before it did anything.
- HTTP 502/503/504 and transport failures are retried **only for idempotent methods** (`GET`, `HEAD`, `OPTIONS`, `PUT`, `DELETE`).
- A control `POST` is therefore never replayed after a timeout or server error. It fails fast instead of risking a second shock.

Set `max_retries=0` to disable retries entirely.

## CLI details

- Entry points: `openshock <command>` or `python -m OpenShockPY.cli <command>`.
- Authentication precedence: `--api-key` > `OPENSHOCK_API_KEY` env var > key stored in system keyring.
- The base URL may also be set with the `OPENSHOCK_BASE_URL` env var.
- The CLI sets `User-Agent` to `OpenShockPY-CLI/<version>`, read from the installed package metadata so it cannot drift from the release.
- Key storage: `openshock login` writes to your system keyring under the service name `openshock`. Requires the `cli` extra; without it, the CLI reports how to install it instead of failing on import.
- "all" option: for `shock`, `vibrate`, `beep` and `stop`, use `--shocker-id all` to target every shocker.
- Exit codes: `0` success, `1` error, `130` interrupted.

## Migrating from 0.0.2.x

The documented API is unchanged — existing calls keep working, and every error still subclasses `OpenShockPYError`. Four things did change:

- **Async `shock("all")` now fans out.** It previously sent a literal shocker id of `"all"`, which the API rejected. Async code that passed `"all"` and relied on it failing will now act on every shocker.
- **`AsyncOpenShockClient` is no longer set to `None`** when `httpx` is missing; importing it raises `ImportError`. Replace `if AsyncOpenShockClient is None:` with a `try` / `except ImportError` around the import.
- **`client._validate_action_params()` was removed** in favour of the shared `validate_action_params()`. It was private; the async client's `_handle()` is also no longer a coroutine.
- **Error message text changed** — messages now prefer the API's `detail` field. Match on the exception class or `.status_code` rather than on message strings.

Duplicate shockers are also now de-duplicated before an `*_all` call, so a shocker reachable through two hubs is no longer sent two controls in the same request.

## Development and testing

- Editable install with all extras: `pip install -e ".[all]"`.
- Run tests: `pytest`.
- Lint and type-check: `flake8 OpenShockPY tests` and `mypy OpenShockPY`.
- Modules of interest:
  - `OpenShockPY/_core.py`: shared types, validation, payload building and retry policy.
  - `OpenShockPY/client.py`: synchronous HTTP client.
  - `OpenShockPY/async_client.py`: asynchronous HTTP client.
  - `OpenShockPY/cli.py`: CLI argument parsing and command dispatch.

## License reminder

The project is licensed under **NNCL v1.3-MODIFIED-OpenShockPY**. It allows non-commercial, ethical use, requires source availability for adaptations, and forbids commercial exploitation without a separate license. See [LICENSE.md](<https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md>) for the full terms.
