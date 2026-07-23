# AGENTS.md — Working on OpenShockPY

Instructions for AI agents making, maintaining or updating code in this repository. Read this before touching anything. For user-facing docs see [README.md](README.md); for the full API surface see [ADVANCED.md](ADVANCED.md).

## What this project is

An **unofficial** Python client for the [OpenShock](https://openshock.org) API, wrapping API **v1** and **v2**. It ships a synchronous client, a mirrored asynchronous client, and an optional CLI.

**This library sends commands to hardware that delivers electric shocks to people.** That single fact drives most of the rules below. A bug here is not a wrong pixel — it is an unwanted shock on a real person. When in doubt, fail loudly rather than act.

## Repository layout

| Path | Role |
| --- | --- |
| `OpenShockPY/_core.py` | Shared, transport-agnostic logic: errors, types, validation, payload building, retry policy. **No I/O.** |
| `OpenShockPY/client.py` | Synchronous client (`requests`). |
| `OpenShockPY/async_client.py` | Asynchronous client (`httpx`). Mirrors `client.py` method for method. |
| `OpenShockPY/cli.py` | Optional CLI. Entry point `openshock`, also `python -m OpenShockPY.cli`. |
| `OpenShockPY/__init__.py` | Public exports, `__version__`, lazy async import. |
| `tests/test_core.py` | Pure-logic tests, no HTTP. |
| `tests/test_client_http.py` | Sync client tests that assert on the actual HTTP calls. |
| `tests/test_async_client_http.py` | Async equivalents, plus the sync/async parity test. |
| `tests/test_client.py`, `tests/test_async_client.py` | Original pre-refactor tests. **Keep them passing unmodified** — they are the backwards-compatibility canary. |

The `_core` / `client` / `async_client` split exists so the two clients cannot drift. **Any logic that is not I/O belongs in `_core`**, called identically from both clients.

## Non-negotiable rules

### 1. Never invent an API constraint

Every limit, enum, field name and required-ness must come from the live OpenAPI schema. Do not infer one from a neighbouring schema, from another endpoint, or from what seems sensible.

```bash
curl -s https://api.openshock.app/swagger/1/swagger.json -o /tmp/v1.json
curl -s https://api.openshock.app/swagger/2/swagger.json -o /tmp/v2.json
```

Note the paths: `/openapi/v1.json` and `/swagger/v1/swagger.json` return empty or 404 documents. The Scalar viewer at `https://api.openshock.app/scalar/viewer/` sources `swagger/1/swagger.json` and `swagger/2/swagger.json` — use exactly those.

> This rule exists because it was violated. A `maxItems: 128` was read off `CreateShareRequest.shockers` and applied to `ControlRequest.shocks`, which declares no cap. The result: `control()` rejected valid requests, and `stop_all()` was silently split into several non-atomic requests, so a partial failure could leave shockers running. Check the schema. Quote it in the docstring.

When the server's behaviour and the schema disagree, the server source is authoritative: <https://github.com/OpenShock/API>.

### 2. Never replay a control request

`POST /2/shockers/control` is **not idempotent**. A 5xx or a timeout is ambiguous — the shock may have been delivered and only the response lost. Replaying it delivers a second shock.

The policy lives in `_core.should_retry()` and `_core.should_retry_transport_error()`:

- HTTP **429** is always safe to retry: the request was rejected before it did anything.
- HTTP **502/503/504** and transport failures retry **only for idempotent methods** (`GET`, `HEAD`, `OPTIONS`, `PUT`, `DELETE`).
- `POST` therefore fails fast on anything except 429.

If you add a retry path, route it through those two functions. Do not add a bare `while attempt < retries` anywhere.

### 3. Validation happens before the request

`intensity` (0-100) and `duration` (300-65535 ms) are validated client-side against the `Control` schema, raising `OpenShockValidationError` before any network call. Never relax this to "let the server decide" — a typo'd intensity should never reach the hardware.

### 4. The two clients stay in lockstep

Every public method on `OpenShockClient` must exist on `AsyncOpenShockClient` with the same name and signature. This is enforced by `test_sync_and_async_expose_the_same_surface` in `tests/test_async_client_http.py`; only `close` / `aclose` may differ. If that test fails, you forgot one — add it, do not weaken the test.

### 5. Do not break the documented surface

ADVANCED.md is the compatibility contract. Specifically:

- The PascalCase setters (`SetUA`, `SetBaseURL`, `SetAPIKey`, `SetSessionToken`) are public API. Snake_case aliases exist alongside them; keep both.
- Every error must subclass `OpenShockPYError`, so a single `except OpenShockPYError` keeps working.
- `OpenShockValidationError` also subclasses `ValueError`, because `SetUA` / `SetBaseURL` historically raised `ValueError`. Do not remove that base.
- Add new parameters **at the end** of existing signatures, never in the middle.
- `tests/test_client.py` and `tests/test_async_client.py` must keep passing without edits.

## Implementation guide: adding an endpoint

Worked example — adding `GET /1/shockers/{shockerId}/shareCodes`.

**Step 1 — Read the schema.** Confirm the path, method, parameters, request body and response shape:

```bash
python3 -c "
import json; d=json.load(open('/tmp/v1.json'))
print(json.dumps(d['paths']['/1/shockers/{shockerId}/shareCodes'], indent=1))
"
```

**Step 2 — Add types to `_core.py` if the response needs them.** `TypedDict` with `total=False` (the API omits fields per endpoint and adds new ones over time). Mirror the schema's field names exactly, including camelCase — do not rename `rfId` to `rf_id` in a response type.

**Step 3 — Add the sync method** in the matching section of `client.py`, as a one-liner over `self._request`:

```python
def list_shocker_share_codes(
    self, shocker_id: str, api_key: Optional[str] = None
) -> Any:
    """List share codes for a shocker. ``GET /1/shockers/{shockerId}/shareCodes``."""
    return self._request(
        "GET", f"/1/shockers/{shocker_id}/shareCodes", api_key=api_key
    )
```

Conventions: snake_case name; `api_key: Optional[str] = None` **last**; docstring naming the exact endpoint; `clean_params({...})` for optional query parameters so `None` is dropped; `json_body=` for bodies.

**Step 4 — Add the async twin** in the same section of `async_client.py`, identical but `async def` / `await self._request(...)`.

**Step 5 — Test both.** Assert the URL and payload actually sent, not just that it returned:

```python
def test_list_shocker_share_codes(record):
    recorder = record(FakeResponse(200, {"data": []}))
    make_client().list_shocker_share_codes("s1")
    assert recorder.calls[0]["url"].endswith("/1/shockers/s1/shareCodes")
```

**Step 6 — Document it** in the right ADVANCED.md table, with its endpoint in the second column.

**Step 7 — Run every gate** (below). The parity test will fail if you forgot the async twin.

### Endpoint conventions

- Prefer **v2** where both versions exist (control, tokens, user shares); use v1 where v2 has no equivalent — e.g. `delete_token` uses `DELETE /1/tokens/{tokenId}` because v2 has no delete.
- Administrative endpoints (`/1/admin/*`) are **deliberately not wrapped**. Do not add them without being asked.
- Every endpoint method takes `api_key=` for a per-call override. An empty string means "send unauthenticated".

## Verification gates

Run all of these before reporting work complete. CI runs the tests on Python **3.10–3.13** via `pip install -e .[dev]`.

```bash
pytest -q                        # 92 tests
flake8 OpenShockPY tests         # .flake8, max-line-length 140
mypy OpenShockPY                 # must be clean
bandit -c .bandit -r OpenShockPY # must be clean
typos --config typos.toml        # must be clean
```

Python 3.10 is the floor. The dev environment may be newer, so check syntax explicitly rather than assuming:

```bash
python3 -c "
import ast, pathlib
for p in pathlib.Path('OpenShockPY').glob('*.py'):
    ast.parse(p.read_text(), feature_version=(3,10))
print('3.10 OK')"
```

Verify packaging when `pyproject.toml` changes — CI installs the package, so a broken build table fails everything:

```bash
python3 -m venv /tmp/fresh && /tmp/fresh/bin/pip install -e ".[dev]"
/tmp/fresh/bin/openshock --version   # entry point must resolve
```

### Linter notes

MegaLinter disables pylint, pyright, mypy, jscpd, cspell, KICS, yamllint, lychee, zizmor and osv-scanner (see `.mega-linter.yml`). **jscpd being off is intentional** — the sync and async clients are near-identical by design; do not "fix" that duplication.

Bandit **is** enabled and excludes only `tests/`. It flags `try/except: pass` as B110 — use `contextlib.suppress()` instead.

Spelling is checked separately by `typos` (`typos.toml`) and cspell (`.cspell.json`). New domain words go in `.cspell.json`'s `words` array.

## Testing patterns

**Assert on the wire, not the return value.** A test that only checks the return value will not catch a wrong URL, a wrong header or a malformed body.

**Sync tests** monkeypatch `OpenShockPY.client.requests.Session.request` with a **callable instance**, not a function:

```python
class Recorder:
    def __call__(self, method, url, **kwargs): ...
```

This matters. A plain function assigned to a class attribute gets bound as a method and receives `self` as its first argument, so its signature silently shifts by one. A callable instance is not a descriptor, so it receives `(method, url, **kwargs)` as written.

**Async tests** use `respx`. Patch sleeps to keep retry tests fast:

```python
monkeypatch.setattr("OpenShockPY.async_client.asyncio.sleep", fake_sleep)
# sync equivalent:
monkeypatch.setattr("OpenShockPY.client.time.sleep", lambda _: None)
```

Tests are marked `@pytest.mark.asyncio` (`asyncio_mode = "strict"` in `pyproject.toml`).

Any change to retry, batching or fan-out behaviour **must** come with a test asserting the exact number of requests issued. That is the class of bug that silently double-shocks someone.

## Docs maintenance

When the public surface changes, update ADVANCED.md in the same change. Verify mechanically rather than by eye:

```bash
python3 - <<'PY'
import re, pathlib, inspect
from OpenShockPY.client import OpenShockClient
import OpenShockPY as pkg
doc = pathlib.Path("ADVANCED.md").read_text()
public = {n for n in dir(OpenShockClient) if not n.startswith("_")}
print("undocumented:", sorted(n for n in public
      if callable(getattr(OpenShockClient, n)) and n not in doc))
named = set(re.findall(r"`([a-zA-Z_]\w*)\(", doc))
helpers = {n for n in dir(pkg) if not n.startswith("_")}
print("named in docs but nonexistent:",
      sorted(n for n in named if n not in public and n not in helpers))
PY
```

Both lists should be empty. `_handle` and `aclose` are expected exceptions in the second list.

Breaking changes go in ADVANCED.md's "Migrating from" section with the migration spelled out.

## Versioning and release

`version` in `pyproject.toml` is the single source of truth. `__version__` reads it from installed package metadata via `importlib.metadata`, and the CLI derives its User-Agent from that. **Never hardcode a version string** — that drifted before and required a manual fix every release.

The scheme is `0.0.X.Y`, Alpha, so semver stability guarantees do not formally apply — but see the compatibility rules above and prefer additive change.

## Known rough edges

Pre-existing; do not fold unrelated fixes into a feature change, but be aware:

- `.mega-linter.yml` sets `MARKDOWN_MARKDOWNLINT_CONFIG_FILE: .markdown lint.json` — note the space. The real file is `.markdownlint.json`, so its `MD013: false` is not being applied.
- README.md has a double blank line near the top that trips MD012.

## Working style

- The requested scope is the deliverable. Do not silently widen it — administrative endpoints, new dependencies and reformatting passes are not implied by "add an endpoint".
- Do not add dependencies. `requests` is the only hard requirement; `httpx` and `keyring` are optional extras and must stay optional — `cli.py` imports `keyring` in a `try` / `except ImportError`, and `AsyncOpenShockClient` is imported lazily in `__init__.py`.
- Report honestly. If a gate fails, say so and quote the output. If you skipped a step, say which.
- Never commit or push unless asked.

## License

NNCL v1.3-MODIFIED-OpenShockPY. Non-commercial, ethical use only. Every source file carries the two-line license header — keep it on new files:

```python
# This software is licensed under NNCL v1.3-MODIFIED-OpenShockPY see LICENSE.md for more info
# https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md
```
