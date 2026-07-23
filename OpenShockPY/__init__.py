# This software is licensed under NNCL v1.3-MODIFIED-OpenShockPY see LICENSE.md for more info
# https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md
"""UNOFFICIAL lightweight Python client for the OpenShock API (v1 + v2)."""

from typing import Any

from ._core import (
    AUTH_HEADER,
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    HUB_AUTH_HEADER,
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
    build_control,
    validate_action_params,
)
from .client import OpenShockClient

try:  # pragma: no cover - trivial
    from importlib.metadata import version

    __version__ = version("Nanashi-OpenShockPY")
except Exception:  # pragma: no cover - source checkout without metadata
    __version__ = "0.0.0+unknown"

__all__ = [
    "__version__",
    # Clients
    "OpenShockClient",
    "AsyncOpenShockClient",
    # Errors
    "OpenShockPYError",
    "OpenShockValidationError",
    "OpenShockConnectionError",
    "OpenShockAPIError",
    "OpenShockAuthError",
    "OpenShockNotFoundError",
    "OpenShockRateLimitError",
    "OpenShockServerError",
    # Types for IDE autocompletion
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
    # Helpers and constants
    "build_control",
    "validate_action_params",
    "AUTH_HEADER",
    "LEGACY_AUTH_HEADER",
    "HUB_AUTH_HEADER",
    "SESSION_HEADER",
    "SESSION_COOKIE",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
]


def __getattr__(name: str) -> Any:
    """Import `AsyncOpenShockClient` lazily so ``httpx`` stays optional.

    Importing it without httpx installed raises an ImportError that says how
    to fix it, rather than the old behaviour of silently binding the name
    to None.
    """
    if name == "AsyncOpenShockClient":
        try:
            from .async_client import AsyncOpenShockClient
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ImportError(
                "AsyncOpenShockClient requires httpx. Install it with: "
                "pip install Nanashi-OpenShockPY[async]"
            ) from exc
        globals()[name] = AsyncOpenShockClient
        return AsyncOpenShockClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
