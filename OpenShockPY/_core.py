# This software is licensed under NNCL v1.3-MODIFIED-OpenShockPY see LICENSE.md for more info
# https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md
"""Shared, transport-agnostic pieces used by both the sync and async clients.

Nothing in here performs I/O, so the sync client (``requests``) and the async
client (``httpx``) can share exactly the same validation, payload building,
response parsing and error mapping.
"""

from typing import Any, Dict, List, Literal, Optional, Sequence, TypedDict

DEFAULT_BASE_URL = "https://api.openshock.app"
DEFAULT_TIMEOUT = 15.0

#: Canonical header name for API tokens (``AuthConstants.ApiTokenHeaderName``
#: server side, ``ApiToken`` security scheme in the OpenAPI document).
AUTH_HEADER = "OpenShockToken"
#: Legacy alias the server still accepts (``HttpContextExtensions
#: .TryGetApiTokenFromHeader``). Sent alongside the canonical header so older
#: self-hosted deployments keep working.
LEGACY_AUTH_HEADER = "Open-Shock-Token"
#: Header name for hub/device tokens (``HubToken`` security scheme).
HUB_AUTH_HEADER = "DeviceToken"
#: Header carrying a user session token (``AuthConstants.UserSessionHeaderName``).
SESSION_HEADER = "OpenShockSession"
#: Cookie carrying a user session token (``AuthConstants.UserSessionCookieName``).
SESSION_COOKIE = "openShockSession"

#: Statuses that are worth retrying with backoff.
RETRY_STATUSES = frozenset({429, 502, 503, 504})

#: A 429 means the request was rejected before it did anything, so replaying it
#: is always safe. The 5xx statuses and transport failures are ambiguous: the
#: request may well have been executed and only the response lost.
ALWAYS_SAFE_RETRY_STATUSES = frozenset({429})

#: HTTP methods that can be replayed without changing the outcome. ``POST`` is
#: absent on purpose - ``POST /2/shockers/control`` delivers a shock, and
#: retrying a timed-out control request would deliver it a second time.
IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})

INTENSITY_MIN = 0
INTENSITY_MAX = 100
DURATION_MIN = 300
DURATION_MAX = 65535


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class OpenShockPYError(Exception):
    """Base exception for every error raised by this library.

    Attributes:
        message: Human readable description.
        status_code: HTTP status code, when the error came from a response.
        payload: Decoded response body (usually an ``OpenShockProblem``),
            when one was available.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        payload: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload


class OpenShockValidationError(OpenShockPYError, ValueError):
    """Raised for client-side validation failures, before any request is sent.

    Also subclasses ValueError so that code written against the older
    ``SetUA`` / ``SetBaseURL`` behaviour, which raised a plain ValueError,
    keeps catching it.
    """


class OpenShockConnectionError(OpenShockPYError):
    """Raised when the request could not be completed (DNS, TLS, timeout, ...)."""


class OpenShockAPIError(OpenShockPYError):
    """Raised for a non-2xx response that has no more specific subclass."""


class OpenShockAuthError(OpenShockAPIError):
    """Raised on HTTP 401/403 - missing, invalid or insufficient credentials."""


class OpenShockNotFoundError(OpenShockAPIError):
    """Raised on HTTP 404."""


class OpenShockRateLimitError(OpenShockAPIError):
    """Raised on HTTP 429.

    Attributes:
        retry_after: Parsed ``Retry-After`` value in seconds, if the server
            sent one.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        payload: Optional[Any] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message, status_code, payload)
        self.retry_after = retry_after


class OpenShockServerError(OpenShockAPIError):
    """Raised on HTTP 5xx."""


def _problem_message(status_code: int, payload: Any) -> str:
    """Build a readable message out of an ``OpenShockProblem`` style body."""
    if isinstance(payload, dict):
        for key in ("detail", "title", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return f"HTTP {status_code}: {value}"
    return f"HTTP {status_code}: {payload}"


def build_api_error(
    status_code: int,
    payload: Any,
    retry_after: Optional[float] = None,
) -> OpenShockAPIError:
    """Map an HTTP status code onto the matching exception class."""
    message = _problem_message(status_code, payload)
    if status_code in (401, 403):
        return OpenShockAuthError(message, status_code, payload)
    if status_code == 404:
        return OpenShockNotFoundError(message, status_code, payload)
    if status_code == 429:
        return OpenShockRateLimitError(message, status_code, payload, retry_after)
    if status_code >= 500:
        return OpenShockServerError(message, status_code, payload)
    return OpenShockAPIError(message, status_code, payload)


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Parse a ``Retry-After`` header expressed in seconds.

    HTTP-date form is intentionally ignored; OpenShock sends deltas.
    """
    if not value:
        return None
    try:
        seconds = float(value.strip())
    except (TypeError, ValueError):
        return None
    return seconds if seconds >= 0 else None


def should_retry(status_code: int, method: str = "GET") -> bool:
    """Return True when a failed response may safely be retried.

    A 429 is always safe to replay. Everything else in `RETRY_STATUSES` is
    only replayed for idempotent methods, so a control request that timed out
    server-side is never sent twice.
    """
    if status_code in ALWAYS_SAFE_RETRY_STATUSES:
        return True
    if status_code not in RETRY_STATUSES:
        return False
    return method.upper() in IDEMPOTENT_METHODS


def should_retry_transport_error(method: str) -> bool:
    """Return True when a connection/timeout failure may safely be retried.

    The request may have reached the server and been executed, so only
    idempotent methods are replayed.
    """
    return method.upper() in IDEMPOTENT_METHODS


def retry_delay(
    attempt: int,
    retry_after: Optional[float] = None,
    backoff_factor: float = 0.5,
    max_delay: float = 30.0,
) -> float:
    """Seconds to wait before retry number ``attempt`` (0-based).

    A server supplied ``Retry-After`` always wins over the exponential backoff.
    """
    if retry_after is not None:
        return min(retry_after, max_delay)
    return min(backoff_factor * (2**attempt), max_delay)


# ---------------------------------------------------------------------------
# Types mirroring the OpenAPI schemas
# ---------------------------------------------------------------------------

#: ``ControlType`` enum (v1 and v2 control endpoints).
ControlType = Literal["Stop", "Shock", "Vibrate", "Sound"]

#: ``ShockerModelType`` enum.
ShockerModel = Literal["CaiXianlin", "PetTrainer", "Petrainer998DR", "WellturnT330"]

#: ``PermissionType`` enum, used when creating or editing API tokens.
PermissionType = Literal[
    "shockers.use",
    "shockers.edit",
    "shockers.pause",
    "devices.edit",
    "devices.auth",
]

#: ``SortDirection`` enum used by the log endpoints.
SortDirection = Literal["Ascending", "Descending"]

# TypedDicts use total=False: the API omits fields per endpoint and adds new
# ones over time, and a partial response should not be a type error.


class Shocker(TypedDict, total=False):
    """``ShockerResponse`` / ``ShockerWithDevice``.

    ``device`` is only present on ``GET /1/shockers/{shockerId}``.
    """

    id: str
    name: str
    rfId: int
    model: ShockerModel
    isPaused: bool
    createdOn: str
    device: str


class Device(TypedDict, total=False):
    """``DeviceResponse`` / ``DeviceWithShockersResponse``.

    ``shockers`` is only present on ``GET /1/shockers/own``.
    """

    id: str
    name: str
    createdOn: str
    shockers: List[Shocker]


class DeviceListResponse(TypedDict, total=False):
    """``DeviceResponseArrayLegacyDataResponse``."""

    message: str
    data: List[Device]


class DeviceResponse(TypedDict, total=False):
    """``DeviceWithTokenResponseLegacyDataResponse``."""

    message: str
    data: Device


class ShockerListResponse(TypedDict, total=False):
    """``ShockerResponseArrayLegacyDataResponse``."""

    message: str
    data: List[Shocker]


class OwnShockerListResponse(TypedDict, total=False):
    """``DeviceWithShockersResponseArrayLegacyDataResponse``.

    Returned by ``GET /1/shockers/own``: hubs, each with their shockers nested.
    """

    message: str
    data: List[Device]


class ShockerResponse(TypedDict, total=False):
    """``ShockerWithDeviceLegacyDataResponse``."""

    message: str
    data: Shocker


class ActionResponse(TypedDict, total=False):
    """``LegacyEmptyResponse``."""

    message: str
    data: Any


class Control(TypedDict, total=False):
    """A single entry of the ``shocks`` array in ``ControlRequest``."""

    id: str
    type: ControlType
    intensity: int
    duration: int
    exclusive: bool


class ShockerPermissions(TypedDict, total=False):
    """``ShockerPermissions``."""

    shock: bool
    vibrate: bool
    sound: bool
    live: bool


class ShockerLimits(TypedDict, total=False):
    """``ShockerLimits``."""

    intensity: Optional[int]
    duration: Optional[int]


# ---------------------------------------------------------------------------
# Validation and payload helpers
# ---------------------------------------------------------------------------


def normalize_base_url(base_url: str) -> str:
    """Strip trailing whitespace and slashes from a base URL."""
    if not base_url or not base_url.strip():
        raise OpenShockValidationError("base_url must be a non-empty string")
    return base_url.strip().rstrip("/")


def validate_action_params(intensity: int, duration: int) -> None:
    """Validate an action against the ``Control`` schema bounds.

    Raises:
        OpenShockValidationError: If a value is out of range or not an integer.
    """
    if isinstance(intensity, bool) or not isinstance(intensity, int):
        raise OpenShockValidationError("Validation failed: intensity must be an integer")
    if isinstance(duration, bool) or not isinstance(duration, int):
        raise OpenShockValidationError("Validation failed: duration must be an integer")
    if intensity < INTENSITY_MIN or intensity > INTENSITY_MAX:
        raise OpenShockValidationError(
            f"Validation failed: intensity must be between "
            f"{INTENSITY_MIN} and {INTENSITY_MAX}"
        )
    if duration < DURATION_MIN or duration > DURATION_MAX:
        raise OpenShockValidationError(
            f"Validation failed: duration must be between "
            f"{DURATION_MIN} and {DURATION_MAX} milliseconds"
        )


def validate_control_type(control_type: str) -> ControlType:
    """Validate a control type against the ``ControlType`` enum."""
    allowed = ("Stop", "Shock", "Vibrate", "Sound")
    if control_type not in allowed:
        raise OpenShockValidationError(
            f"Validation failed: control_type must be one of {', '.join(allowed)}"
        )
    return control_type  # type: ignore[return-value]


def build_control(
    shocker_id: str,
    control_type: ControlType,
    intensity: int,
    duration: int,
    exclusive: bool = False,
) -> Control:
    """Build one ``Control`` entry, validating it first."""
    if not shocker_id or not isinstance(shocker_id, str):
        raise OpenShockValidationError(
            "Validation failed: shocker_id must be a non-empty string"
        )
    validate_control_type(control_type)
    validate_action_params(intensity, duration)
    return {
        "id": shocker_id,
        "type": control_type,
        "intensity": intensity,
        "duration": duration,
        "exclusive": exclusive,
    }


def build_control_request(
    controls: Sequence[Control], custom_name: Optional[str] = None
) -> Dict[str, Any]:
    """Build a ``ControlRequest`` body.

    ``ControlRequest.shocks`` declares no ``maxItems`` in either API version,
    so no client-side cap is imposed; an oversized batch is the server's call
    to reject.
    """
    controls = list(controls)
    if not controls:
        raise OpenShockValidationError(
            "Validation failed: at least one control is required"
        )
    return {"shocks": controls, "customName": custom_name}


def extract_shocker_ids(response: Any) -> List[str]:
    """Collect shocker ids from any of the shocker listing response shapes.

    Handles ``GET /1/shockers/own`` (hubs with nested ``shockers``),
    ``GET /1/devices/{id}/shockers`` (a flat shocker array) and the
    legacy top-level ``shockers`` key, de-duplicating while keeping order.
    """
    if not isinstance(response, dict):
        return []

    candidates: List[Any] = []
    data = response.get("data")
    if isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                continue
            nested = entry.get("shockers")
            if isinstance(nested, list):
                candidates.extend(nested)
            elif "id" in entry:
                candidates.append(entry)

    top_level = response.get("shockers")
    if isinstance(top_level, list):
        candidates.extend(top_level)

    ids: List[str] = []
    seen = set()
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        shocker_id = entry.get("id")
        if isinstance(shocker_id, str) and shocker_id not in seen:
            seen.add(shocker_id)
            ids.append(shocker_id)
    return ids


def clean_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Drop ``None`` values so they are not serialized as query parameters."""
    return {k: v for k, v in params.items() if v is not None}


def auth_headers(api_key: Optional[str]) -> Dict[str, str]:
    """Headers carrying an API token, under the canonical and legacy names."""
    if not api_key:
        return {}
    return {AUTH_HEADER: api_key, LEGACY_AUTH_HEADER: api_key}


def session_headers(session_token: Optional[str]) -> Dict[str, str]:
    """Headers carrying a user session token."""
    if not session_token:
        return {}
    return {SESSION_HEADER: session_token}
