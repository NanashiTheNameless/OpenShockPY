# This software is licensed under NNCL v1.3-MODIFIED-OpenShockPY see LICENSE.md for more info
# https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md
from .client import (
    ActionResponse,
    ControlType,
    Device,
    DeviceListResponse,
    DeviceResponse,
    OpenShockClient,
    OpenShockPYError,
    Shocker,
    ShockerListResponse,
    ShockerResponse,
)

try:
    from .async_client import AsyncOpenShockClient
except Exception:
    # Optional dependency (httpx) may not be available.
    AsyncOpenShockClient = None  # type: ignore

__all__ = [
    "OpenShockClient",
    # Async client may not be available if optional deps aren't installed
    "AsyncOpenShockClient",
    "OpenShockPYError",
    # Type definitions for IDE autocompletion
    "Device",
    "DeviceListResponse",
    "DeviceResponse",
    "Shocker",
    "ShockerListResponse",
    "ShockerResponse",
    "ActionResponse",
    "ControlType",
]
