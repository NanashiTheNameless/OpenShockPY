# This software is licensed under NNCL v1.3-MODIFIED-OpenShockPY see LICENSE.md for more info
# https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md
"""Synchronous OpenShock API client (``requests``)."""

import time
from contextlib import suppress
from typing import Any, Dict, List, Optional, Sequence

import requests

from ._core import (
    AUTH_HEADER,
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    LEGACY_AUTH_HEADER,
    SESSION_COOKIE,
    SESSION_HEADER,
    ActionResponse,
    Control,
    ControlType,
    Device,
    DeviceListResponse,
    DeviceResponse,
    OpenShockAPIError,
    OpenShockAuthError,
    OpenShockConnectionError,
    OpenShockNotFoundError,
    OpenShockPYError,
    OpenShockRateLimitError,
    OpenShockServerError,
    OpenShockValidationError,
    OwnShockerListResponse,
    PermissionType,
    Shocker,
    ShockerLimits,
    ShockerListResponse,
    ShockerModel,
    ShockerPermissions,
    ShockerResponse,
    SortDirection,
    auth_headers,
    build_api_error,
    build_control,
    build_control_request,
    clean_params,
    extract_shocker_ids,
    normalize_base_url,
    parse_retry_after,
    retry_delay,
    session_headers,
    should_retry,
    should_retry_transport_error,
    validate_action_params,
)

__all__ = [
    "OpenShockClient",
    "OpenShockPYError",
    "OpenShockValidationError",
    "OpenShockConnectionError",
    "OpenShockAPIError",
    "OpenShockAuthError",
    "OpenShockNotFoundError",
    "OpenShockRateLimitError",
    "OpenShockServerError",
    "ActionResponse",
    "Control",
    "ControlType",
    "Device",
    "DeviceListResponse",
    "DeviceResponse",
    "OwnShockerListResponse",
    "PermissionType",
    "Shocker",
    "ShockerLimits",
    "ShockerListResponse",
    "ShockerModel",
    "ShockerPermissions",
    "ShockerResponse",
    "SortDirection",
]


class OpenShockClient:
    """Client for the OpenShock REST API (v1 + v2).

    Covers hubs/devices, shockers, control actions, shares, tokens, sessions
    and account/user endpoints. Administrative (``/1/admin/*``) endpoints are
    intentionally not wrapped.

    Attributes:
        base_url: Base URL for the OpenShock API.
        timeout: Request timeout in seconds.
        api_key: The API token used for authentication.
        user_agent: The User-Agent header value sent with every request.
        max_retries: How many times a retryable response is retried.
    """

    base_url: str
    timeout: float
    api_key: Optional[str]
    user_agent: str
    max_retries: int
    backoff_factor: float
    _session: Optional[requests.Session]

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        user_agent: Optional[str] = None,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
    ) -> None:
        """Initialize the OpenShock client.

        Args:
            api_key: Optional API token for authentication.
            base_url: Base URL for the OpenShock API.
            timeout: Request timeout in seconds.
            user_agent: User-Agent header value. Required before any request;
                pass it here or via `SetUA`.
            max_retries: Retries for HTTP 429/502/503/504 and transport errors.
            backoff_factor: Base for exponential backoff, in seconds.
        """
        self.base_url = normalize_base_url(base_url)
        self.timeout = timeout
        self.user_agent = ""
        self.api_key = None
        self.session_token: Optional[str] = None
        self.max_retries = max(0, int(max_retries))
        self.backoff_factor = backoff_factor
        self._session = requests.Session()

        self._session.headers.setdefault("Accept", "application/json")

        if user_agent is not None:
            self.SetUA(user_agent)
        self.SetAPIKey(api_key)

    # -- plumbing ----------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _ensure_open(self) -> requests.Session:
        if self._session is None:
            raise OpenShockPYError("Client is closed; create a new OpenShockClient")
        return self._session

    def _ensure_user_agent(self) -> None:
        if not self.user_agent:
            raise OpenShockValidationError(
                "User-Agent must be set via SetUA before using the client"
            )

    def _get_headers(self, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Per-request headers, layered on top of the session defaults.

        Args:
            api_key: Optional API token to use instead of the stored one.
                Pass an empty string to send the request unauthenticated even
                when a key is stored on the client.

        Returns:
            Headers to merge into the request. A ``None`` value tells
            ``requests`` to drop that session header for this request.
        """
        self._ensure_user_agent()
        if api_key is None:
            return dict(auth_headers(self.api_key))
        if not api_key:
            return {AUTH_HEADER: None, LEGACY_AUTH_HEADER: None}
        return dict(auth_headers(api_key))

    def _handle(self, resp: requests.Response) -> Any:
        """Turn a response into decoded JSON, or raise the matching error."""
        if 200 <= resp.status_code < 300:
            if resp.content:
                try:
                    return resp.json()
                except ValueError:
                    return None
            return None
        try:
            payload = resp.json()
        except Exception:
            payload = {"message": resp.text}
        retry_after = parse_retry_after(
            getattr(resp, "headers", {}).get("Retry-After")  # type: ignore[union-attr]
        )
        raise build_api_error(resp.status_code, payload, retry_after)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        api_key: Optional[str] = None,
    ) -> Any:
        """Send a request, retrying only where a replay is safe.

        Control requests are POSTs, so they are replayed on HTTP 429 (the
        request was rejected, never executed) but never on a timeout or 5xx,
        which could otherwise deliver a second shock.
        """
        session = self._ensure_open()
        url = self._url(path)
        headers = self._get_headers(api_key)
        attempt = 0
        while True:
            try:
                resp = session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                if attempt < self.max_retries and should_retry_transport_error(method):
                    time.sleep(retry_delay(attempt, None, self.backoff_factor))
                    attempt += 1
                    continue
                raise OpenShockConnectionError(
                    f"{method} {url} failed: {exc}"
                ) from exc

            if should_retry(resp.status_code, method) and attempt < self.max_retries:
                after = parse_retry_after(
                    getattr(resp, "headers", {}).get("Retry-After")  # type: ignore[union-attr]
                )
                time.sleep(retry_delay(attempt, after, self.backoff_factor))
                attempt += 1
                continue
            return self._handle(resp)

    # -- configuration -----------------------------------------------------

    def SetUA(self, user_agent: str) -> None:
        """Set the User-Agent header. Required before any request."""
        if not user_agent:
            raise OpenShockValidationError("user_agent must be provided to SetUA")
        self.user_agent = user_agent
        self._ensure_open().headers["User-Agent"] = user_agent

    def SetBaseURL(self, base_url: str) -> None:
        """Set the base API URL, without trailing slashes."""
        self.base_url = normalize_base_url(base_url)

    def SetAPIKey(self, api_key: Optional[str]) -> None:
        """Store the API token in memory and refresh the session headers."""
        self.api_key = api_key
        session = self._ensure_open()
        if api_key:
            session.headers.update(auth_headers(api_key))
        else:
            session.headers.pop(AUTH_HEADER, None)
            session.headers.pop(LEGACY_AUTH_HEADER, None)

    def SetSessionToken(self, session_token: Optional[str]) -> None:
        """Authenticate with a user session token instead of an API token.

        Sends it both as the ``OpenShockSession`` header and the
        ``openShockSession`` cookie, which are the two forms the API reads.
        """
        self.session_token = session_token
        session = self._ensure_open()
        if session_token:
            session.headers.update(session_headers(session_token))
            session.cookies.set(SESSION_COOKIE, session_token)
        else:
            session.headers.pop(SESSION_HEADER, None)
            session.cookies.pop(SESSION_COOKIE, None)

    # Pythonic aliases for the historical PascalCase setters.
    set_user_agent = SetUA
    set_base_url = SetBaseURL
    set_api_key = SetAPIKey
    set_session_token = SetSessionToken

    def close(self) -> None:
        """Close the underlying HTTP session. Safe to call more than once."""
        session = self._session
        self._session = None
        if session is not None:
            session.close()

    def __del__(self) -> None:
        """Best-effort cleanup; never raises during interpreter shutdown."""
        with suppress(Exception):
            self.close()

    def __enter__(self) -> "OpenShockClient":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager and close the session."""
        self.close()

    # -- hubs / devices ----------------------------------------------------

    def list_devices(self, api_key: Optional[str] = None) -> DeviceListResponse:
        """List every hub owned by the account. ``GET /1/devices``."""
        return self._request("GET", "/1/devices", api_key=api_key)

    def get_device(
        self, device_id: str, api_key: Optional[str] = None
    ) -> DeviceResponse:
        """Get a single hub. ``GET /1/devices/{deviceId}``."""
        return self._request("GET", f"/1/devices/{device_id}", api_key=api_key)

    def create_device(self, api_key: Optional[str] = None) -> str:
        """Create a hub and return its id. ``POST /1/devices``."""
        return self._request("POST", "/1/devices", api_key=api_key)

    def edit_device(
        self, device_id: str, name: str, api_key: Optional[str] = None
    ) -> Any:
        """Rename a hub. ``PATCH /1/devices/{deviceId}``."""
        return self._request(
            "PATCH",
            f"/1/devices/{device_id}",
            json_body={"name": name},
            api_key=api_key,
        )

    def delete_device(self, device_id: str, api_key: Optional[str] = None) -> Any:
        """Delete a hub. ``DELETE /1/devices/{deviceId}``."""
        return self._request("DELETE", f"/1/devices/{device_id}", api_key=api_key)

    def regenerate_device_token(
        self, device_id: str, api_key: Optional[str] = None
    ) -> Any:
        """Regenerate a hub's token. ``PUT /1/devices/{deviceId}``."""
        return self._request("PUT", f"/1/devices/{device_id}", api_key=api_key)

    def get_device_pair_code(
        self, device_id: str, api_key: Optional[str] = None
    ) -> Any:
        """Get a hub pair code. ``GET /1/devices/{deviceId}/pair``."""
        return self._request("GET", f"/1/devices/{device_id}/pair", api_key=api_key)

    def get_device_lcg(self, device_id: str, api_key: Optional[str] = None) -> Any:
        """Get the LCG node a hub is connected to. ``GET /1/devices/{deviceId}/lcg``."""
        return self._request("GET", f"/1/devices/{device_id}/lcg", api_key=api_key)

    def get_device_lcg_v2(self, device_id: str, api_key: Optional[str] = None) -> Any:
        """LCG node for a hub, v2 shape. ``GET /2/devices/{deviceId}/lcg``."""
        return self._request("GET", f"/2/devices/{device_id}/lcg", api_key=api_key)

    def get_device_ota_updates(
        self, device_id: str, api_key: Optional[str] = None
    ) -> Any:
        """List OTA update history for a hub. ``GET /1/devices/{deviceId}/ota``."""
        return self._request("GET", f"/1/devices/{device_id}/ota", api_key=api_key)

    # -- shockers ----------------------------------------------------------

    def list_shockers(
        self, device_id: Optional[str] = None, api_key: Optional[str] = None
    ) -> Any:
        """List shockers.

        Args:
            device_id: When given, lists that hub's shockers via
                ``GET /1/devices/{deviceId}/shockers`` (flat
                `ShockerListResponse`). Otherwise ``GET /1/shockers/own``,
                which returns hubs with nested shockers
                (`OwnShockerListResponse`).
            api_key: Optional API token to use instead of the stored one.
        """
        if device_id:
            return self._request(
                "GET", f"/1/devices/{device_id}/shockers", api_key=api_key
            )
        return self._request("GET", "/1/shockers/own", api_key=api_key)

    def list_own_shockers(
        self, api_key: Optional[str] = None
    ) -> OwnShockerListResponse:
        """List owned hubs with their shockers. ``GET /1/shockers/own``."""
        return self._request("GET", "/1/shockers/own", api_key=api_key)

    def list_shared_shockers(self, api_key: Optional[str] = None) -> Any:
        """List shockers shared with this account. ``GET /1/shockers/shared``."""
        return self._request("GET", "/1/shockers/shared", api_key=api_key)

    def get_shocker(
        self, shocker_id: str, api_key: Optional[str] = None
    ) -> ShockerResponse:
        """Get a single shocker. ``GET /1/shockers/{shockerId}``."""
        return self._request("GET", f"/1/shockers/{shocker_id}", api_key=api_key)

    def create_shocker(
        self,
        device_id: str,
        name: str,
        rf_id: int,
        model: ShockerModel,
        api_key: Optional[str] = None,
    ) -> Any:
        """Create a shocker on a hub. ``POST /1/shockers``."""
        return self._request(
            "POST",
            "/1/shockers",
            json_body={
                "device": device_id,
                "name": name,
                "rfId": rf_id,
                "model": model,
            },
            api_key=api_key,
        )

    def edit_shocker(
        self,
        shocker_id: str,
        device_id: str,
        name: str,
        rf_id: int,
        model: ShockerModel,
        api_key: Optional[str] = None,
    ) -> Any:
        """Update a shocker. ``PATCH /1/shockers/{shockerId}``.

        The API requires the full ``NewShocker`` body, so every field must be
        supplied even when only one is changing.
        """
        return self._request(
            "PATCH",
            f"/1/shockers/{shocker_id}",
            json_body={
                "device": device_id,
                "name": name,
                "rfId": rf_id,
                "model": model,
            },
            api_key=api_key,
        )

    def delete_shocker(self, shocker_id: str, api_key: Optional[str] = None) -> Any:
        """Delete a shocker. ``DELETE /1/shockers/{shockerId}``."""
        return self._request("DELETE", f"/1/shockers/{shocker_id}", api_key=api_key)

    def pause_shocker(
        self, shocker_id: str, paused: bool, api_key: Optional[str] = None
    ) -> Any:
        """Pause or unpause a shocker. ``POST /1/shockers/{shockerId}/pause``."""
        return self._request(
            "POST",
            f"/1/shockers/{shocker_id}/pause",
            json_body={"pause": paused},
            api_key=api_key,
        )

    def get_shocker_logs(
        self,
        shocker_id: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        api_key: Optional[str] = None,
    ) -> Any:
        """Get control logs for one shocker. ``GET /1/shockers/{shockerId}/logs``."""
        return self._request(
            "GET",
            f"/1/shockers/{shocker_id}/logs",
            params=clean_params({"offset": offset, "limit": limit}),
            api_key=api_key,
        )

    def get_logs(
        self,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        search: Optional[str] = None,
        sort: Optional[str] = None,
        sort_dir: Optional[SortDirection] = None,
        shocker_ids: Optional[Sequence[str]] = None,
        api_key: Optional[str] = None,
    ) -> Any:
        """Get paged control logs across shockers. ``GET /1/shockers/logs``."""
        return self._request(
            "GET",
            "/1/shockers/logs",
            params=clean_params(
                {
                    "page": page,
                    "pageSize": page_size,
                    "search": search,
                    "sort": sort,
                    "sortDir": sort_dir,
                    "shockerIds": list(shocker_ids) if shocker_ids else None,
                }
            ),
            api_key=api_key,
        )

    # -- control actions ---------------------------------------------------

    def control(
        self,
        controls: Sequence[Control],
        custom_name: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Send an arbitrary set of controls. ``POST /2/shockers/control``.

        Args:
            controls: ``Control`` entries, at most 128 per request. Build them
                with `OpenShockPY.build_control` for validation.
            custom_name: Name shown to the shocker owner in the logs.
            api_key: Optional API token to use instead of the stored one.

        Raises:
            OpenShockValidationError: If the control list is empty or too long.
            OpenShockAPIError: If the API returns an error status code.
        """
        for entry in controls:
            validate_action_params(
                int(entry.get("intensity", 0)), int(entry.get("duration", 0))
            )
        payload = build_control_request(controls, custom_name)
        return self._request(
            "POST", "/2/shockers/control", json_body=payload, api_key=api_key
        )

    def send_action(
        self,
        shocker_id: str,
        control_type: ControlType,
        intensity: int = 0,
        duration: int = 1000,
        exclusive: bool = False,
        api_key: Optional[str] = None,
        custom_name: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Send one action. ``POST /2/shockers/control``.

        Args:
            shocker_id: Shocker id, or ``"all"`` to target every shocker.
            control_type: 'Shock', 'Vibrate', 'Sound' or 'Stop'.
            intensity: Intensity level (0-100).
            duration: Duration in milliseconds (300-65535).
            exclusive: Whether to cancel other running commands on the shocker.
            api_key: Optional API token to use instead of the stored one.
            custom_name: Name shown to the shocker owner in the logs.

        Returns:
            The decoded response, or None when the API returns no content.

        Raises:
            OpenShockValidationError: If a parameter is out of range.
            OpenShockAPIError: If the API returns an error status code.
        """
        if isinstance(shocker_id, str) and shocker_id.lower() == "all":
            return self.send_action_all(
                control_type, intensity, duration, exclusive, api_key, custom_name
            )
        entry = build_control(
            shocker_id, control_type, intensity, duration, exclusive
        )
        return self._request(
            "POST",
            "/2/shockers/control",
            json_body=build_control_request([entry], custom_name),
            api_key=api_key,
        )

    def shock(
        self,
        shocker_id: str,
        intensity: int = 50,
        duration: int = 1000,
        api_key: Optional[str] = None,
        exclusive: bool = False,
        custom_name: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Shock a shocker, or every shocker when ``shocker_id`` is ``"all"``."""
        return self.send_action(
            shocker_id, "Shock", intensity, duration, exclusive, api_key, custom_name
        )

    def vibrate(
        self,
        shocker_id: str,
        intensity: int = 50,
        duration: int = 1000,
        api_key: Optional[str] = None,
        exclusive: bool = False,
        custom_name: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Vibrate a shocker, or every shocker when ``shocker_id`` is ``"all"``."""
        return self.send_action(
            shocker_id, "Vibrate", intensity, duration, exclusive, api_key, custom_name
        )

    def beep(
        self,
        shocker_id: str,
        duration: int = 300,
        api_key: Optional[str] = None,
        exclusive: bool = False,
        custom_name: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Beep a shocker, or every shocker when ``shocker_id`` is ``"all"``."""
        return self.send_action(
            shocker_id, "Sound", 0, duration, exclusive, api_key, custom_name
        )

    def stop(
        self,
        shocker_id: str,
        api_key: Optional[str] = None,
        custom_name: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Stop a shocker, or every shocker when ``shocker_id`` is ``"all"``."""
        return self.send_action(
            shocker_id, "Stop", 0, 300, False, api_key, custom_name
        )

    def _all_shocker_ids(self, api_key: Optional[str] = None) -> List[str]:
        ids = extract_shocker_ids(self.list_shockers(api_key=api_key))
        if not ids:
            raise OpenShockNotFoundError("No shockers found")
        return ids

    def send_action_all(
        self,
        control_type: ControlType,
        intensity: int = 0,
        duration: int = 1000,
        exclusive: bool = False,
        api_key: Optional[str] = None,
        custom_name: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Send one action to every shocker the account can control.

        Shockers are looked up via `list_shockers` and de-duplicated, then sent
        as a single control request so the action applies atomically.

        Raises:
            OpenShockValidationError: If a parameter is out of range.
            OpenShockNotFoundError: If the account has no shockers.
            OpenShockAPIError: If the API returns an error status code.
        """
        validate_action_params(intensity, duration)
        controls = [
            build_control(sid, control_type, intensity, duration, exclusive)
            for sid in self._all_shocker_ids(api_key)
        ]
        return self._request(
            "POST",
            "/2/shockers/control",
            json_body=build_control_request(controls, custom_name),
            api_key=api_key,
        )

    def shock_all(
        self,
        intensity: int = 50,
        duration: int = 1000,
        api_key: Optional[str] = None,
        exclusive: bool = False,
        custom_name: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Shock every shocker."""
        return self.send_action_all(
            "Shock", intensity, duration, exclusive, api_key, custom_name
        )

    def vibrate_all(
        self,
        intensity: int = 50,
        duration: int = 1000,
        api_key: Optional[str] = None,
        exclusive: bool = False,
        custom_name: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Vibrate every shocker."""
        return self.send_action_all(
            "Vibrate", intensity, duration, exclusive, api_key, custom_name
        )

    def beep_all(
        self,
        duration: int = 300,
        api_key: Optional[str] = None,
        exclusive: bool = False,
        custom_name: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Beep every shocker."""
        return self.send_action_all(
            "Sound", 0, duration, exclusive, api_key, custom_name
        )

    def stop_all(
        self, api_key: Optional[str] = None, custom_name: Optional[str] = None
    ) -> Optional[ActionResponse]:
        """Stop every shocker."""
        return self.send_action_all("Stop", 0, 300, False, api_key, custom_name)

    # -- shares ------------------------------------------------------------

    def list_public_shares(self, api_key: Optional[str] = None) -> Any:
        """List public share links. ``GET /1/shares/links``."""
        return self._request("GET", "/1/shares/links", api_key=api_key)

    def create_public_share(
        self,
        name: str,
        expires_on: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Any:
        """Create a public share link. ``POST /1/shares/links``.

        Args:
            name: Share name, 1-64 characters.
            expires_on: ISO-8601 timestamp, or None for no expiry.
        """
        return self._request(
            "POST",
            "/1/shares/links",
            json_body=clean_params({"name": name, "expiresOn": expires_on}),
            api_key=api_key,
        )

    def delete_public_share(
        self, public_share_id: str, api_key: Optional[str] = None
    ) -> Any:
        """Delete a public share link. ``DELETE /1/shares/links/{publicShareId}``."""
        return self._request(
            "DELETE", f"/1/shares/links/{public_share_id}", api_key=api_key
        )

    def get_public_share(
        self, public_share_id: str, api_key: Optional[str] = None
    ) -> Any:
        """Read a public share link. ``GET /1/public/shares/links/{publicShareId}``."""
        return self._request(
            "GET", f"/1/public/shares/links/{public_share_id}", api_key=api_key
        )

    def add_shocker_to_public_share(
        self,
        public_share_id: str,
        shocker_id: str,
        permissions: ShockerPermissions,
        limits: ShockerLimits,
        api_key: Optional[str] = None,
    ) -> Any:
        """Add a shocker to a public share.

        ``POST /1/shares/links/{publicShareId}/{shockerId}``.
        """
        return self._request(
            "POST",
            f"/1/shares/links/{public_share_id}/{shocker_id}",
            json_body={"permissions": permissions, "limits": limits},
            api_key=api_key,
        )

    def remove_shocker_from_public_share(
        self, public_share_id: str, shocker_id: str, api_key: Optional[str] = None
    ) -> Any:
        """Remove a shocker from a public share.

        ``DELETE /1/shares/links/{publicShareId}/{shockerId}``.
        """
        return self._request(
            "DELETE",
            f"/1/shares/links/{public_share_id}/{shocker_id}",
            api_key=api_key,
        )

    def list_shocker_shares(
        self, shocker_id: str, api_key: Optional[str] = None
    ) -> Any:
        """List users a shocker is shared with. ``GET /1/shockers/{shockerId}/shares``."""
        return self._request(
            "GET", f"/1/shockers/{shocker_id}/shares", api_key=api_key
        )

    def list_user_shares(self, api_key: Optional[str] = None) -> Any:
        """List user-to-user shares. ``GET /2/shares/user``."""
        return self._request("GET", "/2/shares/user", api_key=api_key)

    def create_share_invite(
        self,
        shockers: Sequence[Dict[str, Any]],
        user: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Any:
        """Create a share invite. ``POST /2/shares/user/invites``.

        Args:
            shockers: ``ShockerPermLimitPairWithId`` entries (max 128).
            user: Target user id, or None for an open invite link.
        """
        return self._request(
            "POST",
            "/2/shares/user/invites",
            json_body=clean_params({"shockers": list(shockers), "user": user}),
            api_key=api_key,
        )

    def list_incoming_share_invites(self, api_key: Optional[str] = None) -> Any:
        """``GET /2/shares/user/invites/incoming``."""
        return self._request(
            "GET", "/2/shares/user/invites/incoming", api_key=api_key
        )

    def list_outgoing_share_invites(self, api_key: Optional[str] = None) -> Any:
        """``GET /2/shares/user/invites/outgoing``."""
        return self._request(
            "GET", "/2/shares/user/invites/outgoing", api_key=api_key
        )

    def accept_share_invite(self, invite_id: str, api_key: Optional[str] = None) -> Any:
        """``POST /2/shares/user/invites/incoming/{inviteId}``."""
        return self._request(
            "POST", f"/2/shares/user/invites/incoming/{invite_id}", api_key=api_key
        )

    def decline_share_invite(
        self, invite_id: str, api_key: Optional[str] = None
    ) -> Any:
        """``DELETE /2/shares/user/invites/incoming/{inviteId}``."""
        return self._request(
            "DELETE", f"/2/shares/user/invites/incoming/{invite_id}", api_key=api_key
        )

    def cancel_share_invite(self, invite_id: str, api_key: Optional[str] = None) -> Any:
        """``DELETE /2/shares/user/invites/outgoing/{inviteId}``."""
        return self._request(
            "DELETE", f"/2/shares/user/invites/outgoing/{invite_id}", api_key=api_key
        )

    def update_user_shares(
        self,
        user_id: str,
        shockers: Sequence[str],
        permissions: ShockerPermissions,
        limits: ShockerLimits,
        api_key: Optional[str] = None,
    ) -> Any:
        """Bulk-update a user's shares. ``PATCH /2/shares/user/{userId}/shockers``."""
        return self._request(
            "PATCH",
            f"/2/shares/user/{user_id}/shockers",
            json_body={
                "shockers": list(shockers),
                "permissions": permissions,
                "limits": limits,
            },
            api_key=api_key,
        )

    def pause_user_shares(
        self,
        user_id: str,
        shockers: Sequence[str],
        paused: bool,
        api_key: Optional[str] = None,
    ) -> Any:
        """Pause a user's shares. ``POST /2/shares/user/{userId}/shockers/pause``."""
        return self._request(
            "POST",
            f"/2/shares/user/{user_id}/shockers/pause",
            json_body={"shockers": list(shockers), "paused": paused},
            api_key=api_key,
        )

    def remove_user_shares(
        self,
        user_id: str,
        shockers: Sequence[str],
        api_key: Optional[str] = None,
    ) -> Any:
        """Revoke a user's shares. ``DELETE /2/shares/user/{userId}/shockers``."""
        return self._request(
            "DELETE",
            f"/2/shares/user/{user_id}/shockers",
            json_body={"shockers": list(shockers)},
            api_key=api_key,
        )

    # -- tokens ------------------------------------------------------------

    def list_tokens(self, api_key: Optional[str] = None) -> Any:
        """List API tokens. ``GET /2/tokens``."""
        return self._request("GET", "/2/tokens", api_key=api_key)

    def get_token(self, token_id: str, api_key: Optional[str] = None) -> Any:
        """Get one API token. ``GET /2/tokens/{tokenId}``."""
        return self._request("GET", f"/2/tokens/{token_id}", api_key=api_key)

    def get_self_token(self, api_key: Optional[str] = None) -> Any:
        """Describe the token being used right now. ``GET /2/tokens/self``."""
        return self._request("GET", "/2/tokens/self", api_key=api_key)

    def create_token(
        self,
        name: str,
        permissions: Sequence[PermissionType],
        shocker_control: Dict[str, Any],
        valid_until: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> Any:
        """Create an API token. ``POST /2/tokens``.

        Args:
            name: Token name, 1-64 characters.
            permissions: ``PermissionType`` values.
            shocker_control: ``ShockerControlSettings`` body - requires
                ``paused``, ``intensity`` and ``duration`` keys.
            valid_until: ISO-8601 expiry, or None for no expiry.
        """
        return self._request(
            "POST",
            "/2/tokens",
            json_body=clean_params(
                {
                    "name": name,
                    "permissions": list(permissions),
                    "shockerControl": shocker_control,
                    "validUntil": valid_until,
                }
            ),
            api_key=api_key,
        )

    def edit_token(
        self,
        token_id: str,
        name: str,
        permissions: Sequence[PermissionType],
        shocker_control: Dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Any:
        """Edit an API token. ``PATCH /2/tokens/{tokenId}``."""
        return self._request(
            "PATCH",
            f"/2/tokens/{token_id}",
            json_body={
                "name": name,
                "permissions": list(permissions),
                "shockerControl": shocker_control,
            },
            api_key=api_key,
        )

    def set_token_paused(
        self, token_id: str, paused: bool, api_key: Optional[str] = None
    ) -> Any:
        """Pause or resume a token. ``PATCH /2/tokens/{tokenId}/paused``."""
        return self._request(
            "PATCH",
            f"/2/tokens/{token_id}/paused",
            json_body={"paused": paused},
            api_key=api_key,
        )

    def delete_token(self, token_id: str, api_key: Optional[str] = None) -> Any:
        """Delete a token. ``DELETE /1/tokens/{tokenId}`` (no v2 equivalent)."""
        return self._request("DELETE", f"/1/tokens/{token_id}", api_key=api_key)

    def report_tokens(
        self, secrets: Sequence[str], api_key: Optional[str] = None
    ) -> Any:
        """Report leaked tokens. ``POST /2/tokens/report``."""
        return self._request(
            "POST",
            "/2/tokens/report",
            json_body={"secrets": list(secrets)},
            api_key=api_key,
        )

    # -- account / users / sessions ---------------------------------------

    def get_self(self, api_key: Optional[str] = None) -> Any:
        """Get the authenticated user. ``GET /1/users/self``."""
        return self._request("GET", "/1/users/self", api_key=api_key)

    def get_user_by_name(self, username: str, api_key: Optional[str] = None) -> Any:
        """Look a user up by name. ``GET /1/users/by-name/{username}``."""
        return self._request("GET", f"/1/users/by-name/{username}", api_key=api_key)

    def list_sessions(self, api_key: Optional[str] = None) -> Any:
        """List login sessions. ``GET /1/sessions``."""
        return self._request("GET", "/1/sessions", api_key=api_key)

    def get_self_session(self, api_key: Optional[str] = None) -> Any:
        """Describe the current session. ``GET /1/sessions/self``."""
        return self._request("GET", "/1/sessions/self", api_key=api_key)

    def delete_session(self, session_id: str, api_key: Optional[str] = None) -> Any:
        """Revoke a session. ``DELETE /1/sessions/{sessionId}``."""
        return self._request("DELETE", f"/1/sessions/{session_id}", api_key=api_key)

    def logout(self, api_key: Optional[str] = None) -> Any:
        """Invalidate the current session cookie. ``POST /1/account/logout``."""
        return self._request("POST", "/1/account/logout", api_key=api_key)

    def get_public_stats(self, api_key: Optional[str] = None) -> Any:
        """Instance-wide public statistics. ``GET /1/public/stats``."""
        return self._request("GET", "/1/public/stats", api_key=api_key)
