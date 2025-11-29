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

__all__ = [
    "OpenShockClient",
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
