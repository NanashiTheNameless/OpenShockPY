# This software is licensed under NNCL v1.3-MODIFIED-OpenShockPY see LICENSE.md for more info
# https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md
from typing import Any, Dict, List, Literal, Optional, TypedDict

import requests


class OpenShockPYError(Exception):
    """Exception raised for OpenShock API errors."""

    pass


# Type definitions for API responses
# Note: TypedDict classes use total=False to allow for API evolution and
# partial responses. This provides flexibility when the API returns varying
# fields across different endpoints or versions.


class Shocker(TypedDict, total=False):
    """Represents a shocker device.

    Fields may be omitted depending on the API endpoint used.
    """

    id: str
    name: str
    rfId: int
    model: str
    createdOn: str
    isPaused: bool
    online: bool


class Device(TypedDict, total=False):
    """Represents an OpenShock hub device.

    Fields may be omitted depending on the API endpoint used.
    """

    id: str
    name: str
    createdOn: str
    online: bool
    firmwareVersion: str
    shockers: List[Shocker]


class DeviceListResponse(TypedDict, total=False):
    """Response from listing devices.

    Typically contains 'message' and 'data' fields.
    """

    message: str
    data: List[Device]


class DeviceResponse(TypedDict, total=False):
    """Response from getting a single device.

    Typically contains 'message' and 'data' fields.
    """

    message: str
    data: Device


class ShockerListResponse(TypedDict, total=False):
    """Response from listing shockers.

    Typically contains 'message' and 'data' fields.
    """

    message: str
    data: List[Shocker]


class ShockerResponse(TypedDict, total=False):
    """Response from getting a single shocker.

    Typically contains 'message' and 'data' fields.
    """

    message: str
    data: Shocker


class ActionResponse(TypedDict, total=False):
    """Response from sending an action (shock/vibrate/beep).

    May contain a 'message' field with status information.
    """

    message: str


# Literal type for control actions
ControlType = Literal["Shock", "Vibrate", "Sound", "Stop"]


class OpenShockClient:
    """Client for interacting with the OpenShock API.

    Provides methods for managing devices, shockers, and sending control actions
    (shock, vibrate, beep) to connected shocker devices.

    Attributes:
        base_url: The base URL for the OpenShock API.
        timeout: Request timeout in seconds.
        api_key: The API key for authentication.
        user_agent: The User-Agent header value for requests.
    """

    base_url: str
    timeout: int
    api_key: Optional[str]
    user_agent: str
    _session: requests.Session

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openshock.app",
        timeout: int = 15,
        user_agent: Optional[str] = None,
    ) -> None:
        """Initialize the OpenShock client.

        Args:
            api_key: Optional API key for authentication.
            base_url: Base URL for the OpenShock API.
            timeout: Request timeout in seconds.
            user_agent: Optional User-Agent header value.
        """
        self.base_url = base_url.rstrip(" /")
        self.timeout = timeout
        self.user_agent = ""
        self._session = requests.Session()

        self._session.headers.setdefault("Content-Type", "application/json")
        self._session.headers.setdefault("Accept", "application/json")

        if user_agent is not None:
            self.SetUA(user_agent)
        self.SetAPIKey(api_key)

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _handle(self, resp: requests.Response) -> Any:
        if 200 <= resp.status_code < 300:
            if resp.content:
                return resp.json()
            return None
        try:
            payload = resp.json()
        except Exception:
            payload = {"message": resp.text}
        raise OpenShockPYError(f"HTTP {resp.status_code}: {payload}")

    def _validate_action_params(self, intensity: int, duration: int) -> None:
        if intensity < 0 or intensity > 100:
            raise OpenShockPYError(
                "Validation failed: intensity must be between 0 and 100"
            )
        if duration < 300 or duration > 65535:
            raise OpenShockPYError(
                "Validation failed: duration must be between 300 and 65535 milliseconds"
            )

    def _get_headers(self, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Get headers for API requests.

        Args:
            api_key: Optional API key to use instead of the stored one.

        Returns:
            Dictionary of headers for the request.
        """
        self._ensure_user_agent()
        headers = dict(self._session.headers)
        key = api_key if api_key is not None else self.api_key
        if key:
            headers["Open-Shock-Token"] = key
        else:
            headers.pop("Open-Shock-Token", None)
        return headers

    def SetUA(self, user_agent: str) -> None:
        """Update the User-Agent header (must be provided before requests)."""
        if not user_agent:
            raise ValueError("user_agent must be provided to SetUA")
        self.user_agent = user_agent
        self._session.headers["User-Agent"] = user_agent

    def SetBaseURL(self, base_url: str) -> None:
        """Update the base API URL without trailing slashes."""
        if not base_url:
            raise ValueError("base_url must be provided to SetBaseURL")
        self.base_url = base_url.rstrip(" /")

    def _ensure_user_agent(self) -> None:
        if not self.user_agent:
            raise OpenShockPYError(
                "User-Agent must be set via SetUA before using the client"
            )

    def SetAPIKey(self, api_key: Optional[str]) -> None:
        """Store the API key in memory and refresh the session headers."""
        self.api_key = api_key
        if api_key:
            self._session.headers["Open-Shock-Token"] = api_key
        else:
            self._session.headers.pop("Open-Shock-Token", None)

    def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session is not None:
            self._session.close()
            self._session = None  # type: ignore[assignment]

    def __del__(self) -> None:
        """Destructor to ensure session cleanup."""
        self.close()

    def __enter__(self) -> "OpenShockClient":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and close the session."""
        self.close()

    # Devices
    def list_devices(self, api_key: Optional[str] = None) -> DeviceListResponse:
        """List every device tied to the current account.

        Args:
            api_key: Optional API key to use instead of the stored one.

        Returns:
            Response containing a list of devices.
        """
        resp = self._session.get(
            self._url("/1/devices"),
            headers=self._get_headers(api_key),
            timeout=self.timeout,
        )
        return self._handle(resp)

    def get_device(
        self, device_id: str, api_key: Optional[str] = None
    ) -> DeviceResponse:
        """Retrieve details for a single device.

        Args:
            device_id: The unique identifier of the device.
            api_key: Optional API key to use instead of the stored one.

        Returns:
            Response containing device details.
        """
        resp = self._session.get(
            self._url(f"/1/devices/{device_id}"),
            headers=self._get_headers(api_key),
            timeout=self.timeout,
        )
        return self._handle(resp)

    def list_shockers(
        self, device_id: Optional[str] = None, api_key: Optional[str] = None
    ) -> ShockerListResponse:
        """List shockers (all or for a specific device).

        Args:
            device_id: Optional device ID to filter shockers.
            api_key: Optional API key to use instead of the stored one.

        Returns:
            Response containing a list of shockers.
        """
        if device_id:
            resp = self._session.get(
                self._url(f"/1/devices/{device_id}/shockers"),
                headers=self._get_headers(api_key),
                timeout=self.timeout,
            )
        else:
            resp = self._session.get(
                self._url("/1/shockers/own"),
                headers=self._get_headers(api_key),
                timeout=self.timeout,
            )
        return self._handle(resp)

    def get_shocker(
        self, shocker_id: str, api_key: Optional[str] = None
    ) -> ShockerResponse:
        """Retrieve details for a single shocker.

        Args:
            shocker_id: The unique identifier of the shocker.
            api_key: Optional API key to use instead of the stored one.

        Returns:
            Response containing shocker details.
        """
        resp = self._session.get(
            self._url(f"/1/shockers/{shocker_id}"),
            headers=self._get_headers(api_key),
            timeout=self.timeout,
        )
        return self._handle(resp)

    # Shocks / actions
    def send_action(
        self,
        shocker_id: str,
        control_type: ControlType,
        intensity: int = 0,
        duration: int = 1000,
        exclusive: bool = False,
        api_key: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Send an action command (Shock/Vibrate/Sound/Stop).

        Args:
            shocker_id: The unique identifier of the shocker.
            control_type: Type of action - 'Shock', 'Vibrate', 'Sound', or 'Stop'.
            intensity: Intensity level (0-100).
            duration: Duration in milliseconds (300-65535).
            exclusive: Whether to run exclusively.
            api_key: Optional API key to use instead of the stored one.

        Returns:
            ActionResponse if the API returns JSON content, None if the
            response has no content (HTTP 204 No Content).

        Raises:
            OpenShockPYError: If the API returns an error status code.
        """
        self._validate_action_params(intensity, duration)
        payload = {
            "shocks": [
                {
                    "id": shocker_id,
                    "type": control_type,
                    "intensity": intensity,
                    "duration": duration,
                    "exclusive": exclusive,
                }
            ],
            "customName": None,
        }
        resp = self._session.post(
            self._url("/2/shockers/control"),
            json=payload,
            headers=self._get_headers(api_key),
            timeout=self.timeout,
        )
        return self._handle(resp)

    def shock(
        self,
        shocker_id: str,
        intensity: int = 50,
        duration: int = 1000,
        api_key: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Trigger a shock action.

        Args:
            shocker_id: The unique identifier of the shocker, or "all" to shock all shockers.
            intensity: Intensity level (0-100, default 50).
            duration: Duration in milliseconds (300-65535, default 1000).
            api_key: Optional API key to use instead of the stored one.

        Returns:
            ActionResponse if the API returns JSON content, None if the
            response has no content (HTTP 204 No Content).

        Raises:
            OpenShockPYError: If the API returns an error status code.
        """
        if shocker_id.lower() == "all":
            return self.shock_all(intensity, duration, api_key)
        return self.send_action(
            shocker_id, "Shock", intensity, duration, False, api_key
        )

    def vibrate(
        self,
        shocker_id: str,
        intensity: int = 50,
        duration: int = 1000,
        api_key: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Trigger a vibrate action.

        Args:
            shocker_id: The unique identifier of the shocker, or "all" to vibrate all shockers.
            intensity: Intensity level (0-100, default 50).
            duration: Duration in milliseconds (300-65535, default 1000).
            api_key: Optional API key to use instead of the stored one.

        Returns:
            ActionResponse if the API returns JSON content, None if the
            response has no content (HTTP 204 No Content).

        Raises:
            OpenShockPYError: If the API returns an error status code.
        """
        if shocker_id.lower() == "all":
            return self.vibrate_all(intensity, duration, api_key)
        return self.send_action(
            shocker_id, "Vibrate", intensity, duration, False, api_key
        )

    def beep(
        self, shocker_id: str, duration: int = 300, api_key: Optional[str] = None
    ) -> Optional[ActionResponse]:
        """Trigger a beep/sound action.

        Args:
            shocker_id: The unique identifier of the shocker, or "all" to beep all shockers.
            duration: Duration in milliseconds (300-65535, default 300).
            api_key: Optional API key to use instead of the stored one.

        Returns:
            ActionResponse if the API returns JSON content, None if the
            response has no content (HTTP 204 No Content).

        Raises:
            OpenShockPYError: If the API returns an error status code.
        """
        if shocker_id.lower() == "all":
            return self.beep_all(duration, api_key)
        return self.send_action(shocker_id, "Sound", 0, duration, False, api_key)

    def stop(
        self, shocker_id: str, api_key: Optional[str] = None
    ) -> Optional[ActionResponse]:
        """Stop all actions on the shocker.

        Args:
            shocker_id: The unique identifier of the shocker, or "all" to stop all shockers.
            api_key: Optional API key to use instead of the stored one.

        Returns:
            ActionResponse if the API returns JSON content, None if the
            response has no content (HTTP 204 No Content).

        Raises:
            OpenShockPYError: If the API returns an error status code.
        """
        if shocker_id.lower() == "all":
            return self.stop_all(api_key)
        return self.send_action(shocker_id, "Stop", 0, 300, False, api_key)

    def send_action_all(
        self,
        control_type: ControlType,
        intensity: int = 0,
        duration: int = 1000,
        exclusive: bool = False,
        api_key: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Send an action command to all shockers.

        Args:
            control_type: Type of action - 'Shock', 'Vibrate', 'Sound', or 'Stop'.
            intensity: Intensity level (0-100).
            duration: Duration in milliseconds (300-65535).
            exclusive: Whether to run exclusively.
            api_key: Optional API key to use instead of the stored one.

        Returns:
            ActionResponse if the API returns JSON content, None if the
            response has no content (HTTP 204 No Content).

        Raises:
            OpenShockPYError: If the API returns an error status code.
        """
        self._validate_action_params(intensity, duration)
        # Get all shockers
        shockers_response = self.list_shockers(api_key=api_key)
        all_shockers: List[Dict[str, Any]] = []
        data = shockers_response.get("data", [])
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and "shockers" in entry:
                    all_shockers.extend(entry.get("shockers", []))
                else:
                    all_shockers.append(entry)

        shockers = shockers_response.get("shockers", [])
        if isinstance(shockers, list):
            all_shockers.extend(shockers)

        if not all_shockers:
            raise OpenShockPYError("No shockers found")

        shocks_list = [
            {
                "id": shocker["id"],
                "type": control_type,
                "intensity": intensity,
                "duration": duration,
                "exclusive": exclusive,
            }
            for shocker in all_shockers
        ]

        payload = {
            "shocks": shocks_list,
            "customName": None,
        }

        resp = self._session.post(
            self._url("/2/shockers/control"),
            json=payload,
            headers=self._get_headers(api_key),
            timeout=self.timeout,
        )
        return self._handle(resp)

    def shock_all(
        self,
        intensity: int = 50,
        duration: int = 1000,
        api_key: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Trigger a shock action on all shockers.

        Args:
            intensity: Intensity level (0-100, default 50).
            duration: Duration in milliseconds (300-65535, default 1000).
            api_key: Optional API key to use instead of the stored one.

        Returns:
            ActionResponse if the API returns JSON content, None if the
            response has no content (HTTP 204 No Content).

        Raises:
            OpenShockPYError: If the API returns an error status code.
        """
        return self.send_action_all("Shock", intensity, duration, False, api_key)

    def vibrate_all(
        self,
        intensity: int = 50,
        duration: int = 1000,
        api_key: Optional[str] = None,
    ) -> Optional[ActionResponse]:
        """Trigger a vibrate action on all shockers.

        Args:
            intensity: Intensity level (0-100, default 50).
            duration: Duration in milliseconds (300-65535, default 1000).
            api_key: Optional API key to use instead of the stored one.

        Returns:
            ActionResponse if the API returns JSON content, None if the
            response has no content (HTTP 204 No Content).

        Raises:
            OpenShockPYError: If the API returns an error status code.
        """
        return self.send_action_all("Vibrate", intensity, duration, False, api_key)

    def beep_all(
        self, duration: int = 300, api_key: Optional[str] = None
    ) -> Optional[ActionResponse]:
        """Trigger a beep/sound action on all shockers.

        Args:
            duration: Duration in milliseconds (300-65535, default 300).
            api_key: Optional API key to use instead of the stored one.

        Returns:
            ActionResponse if the API returns JSON content, None if the
            response has no content (HTTP 204 No Content).

        Raises:
            OpenShockPYError: If the API returns an error status code.
        """
        return self.send_action_all("Sound", 0, duration, False, api_key)

    def stop_all(self, api_key: Optional[str] = None) -> Optional[ActionResponse]:
        """Stop all actions on all shockers.

        Args:
            api_key: Optional API key to use instead of the stored one.

        Returns:
            ActionResponse if the API returns JSON content, None if the
            response has no content (HTTP 204 No Content).

        Raises:
            OpenShockPYError: If the API returns an error status code.
        """
        return self.send_action_all("Stop", 0, 300, False, api_key)
