# OpenShock Python — Advanced Guide

Technical details for engineers and power users. For a simpler overview, see `README.md`.

## Client fundamentals

- **User-Agent is required**: `OpenShockClient` will raise `OpenShockError` if you call the API without setting a User-Agent (set via constructor or `SetUA`).
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
  
- Duration is clamped to **300–65535 ms**. Intensity is passed through; the API expects 0–100.
- `exclusive` defaults to `False`; set to `True` when you need exclusive control.

## Error handling

- Non-2xx responses raise `OpenShockError` with the HTTP status and any parsed JSON body (falls back to raw text).
- Empty 2xx responses return `None`; otherwise JSON is returned as parsed Python data.

## CLI details

- Entry point: `python -m OpenShockPY.cli <command>`.
- Commands: `devices`, `shockers`, `shock`, `vibrate`, `beep`, `login`, `logout`.
- Authentication precedence: `--api-key` > `OPENSHOCK_API_KEY` env var > key stored in system keyring.
- The CLI sets `User-Agent` to `OpenShockPY-CLI/0.0.0.2` automatically.
- Base URL override: `--base-url https://api.openshock.dev`.
- Key storage: `python -m OpenShockPY.cli login` writes to your system keyring under the service name `openshock`.

## Development and testing

- Editable install with all extras: `pip install -e ".[all]"`.
- Run tests: `pytest`.
- Modules of interest:
  - `OpenShockPY/client.py`: HTTP client and error handling.
  - `OpenShockPY/cli.py`: CLI argument parsing and command dispatch.

## License reminder

The project is licensed under **NNCL v1.2-MODIFIED-OpenShockPY**. It allows non-commercial, ethical use, requires source availability for adaptations, and forbids commercial exploitation without a separate license. See `LICENSE.md` for the full terms.
