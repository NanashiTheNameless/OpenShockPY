# This software is licensed under NNCL v1.2-MODIFIED-OpenShockPY see LICENSE.md for more info
# https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md
from .client import (
    ActionResponse,
    ControlType,
    Device,
    DeviceListResponse,
    DeviceResponse,
    OpenShockClient,
    OpenShockError,
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
    "OpenShockError",
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
