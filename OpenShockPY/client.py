# This software is licensed under NNCL v1.2-MODIFIED-OpenShockPY see LICENSE.md for more info
# https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md
from typing import Any, Optional

import requests


class OpenShockError(Exception):
    pass

class OpenShockClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openshock.app",
        timeout: int = 15,
        user_agent: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip(" /")
        self.timeout = timeout
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
        raise OpenShockError(f"HTTP {resp.status_code}: {payload}")

    def _get_headers(self, api_key: Optional[str] = None) -> dict:
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
            raise OpenShockError("User-Agent must be set via SetUA before using the client")

    def SetAPIKey(self, api_key: Optional[str]) -> None:
        """Store the API key in memory and refresh the session headers."""
        self.api_key = api_key
        if api_key:
            self._session.headers["Open-Shock-Token"] = api_key
        else:
            self._session.headers.pop("Open-Shock-Token", None)

    # Devices
    def list_devices(self, api_key: Optional[str] = None) -> Any:
        """List every device tied to the current account."""
        resp = self._session.get(
            self._url("/1/devices"),
            headers=self._get_headers(api_key),
            timeout=self.timeout,
        )
        return self._handle(resp)

    def get_device(self, device_id: str, api_key: Optional[str] = None) -> Any:
        """Retrieve details for a single device."""
        resp = self._session.get(
            self._url(f"/1/devices/{device_id}"),
            headers=self._get_headers(api_key),
            timeout=self.timeout,
        )
        return self._handle(resp)

    def list_shockers(
        self, device_id: Optional[str] = None, api_key: Optional[str] = None
    ) -> Any:
        """List shockers (all or for a specific device)."""
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

    def get_shocker(self, shocker_id: str, api_key: Optional[str] = None) -> Any:
        """Retrieve details for a single shocker."""
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
        control_type: str,
        intensity: int = 0,
        duration: int = 1000,
        exclusive: bool = False,
        api_key: Optional[str] = None,
    ) -> Any:
        """Send an action command (Shock/Vibrate/Sound/Stop)."""
        duration = max(300, min(65535, duration))
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
    ) -> Any:
        """Trigger a shock action."""
        return self.send_action(
            shocker_id, "Shock", intensity, duration, False, api_key
        )

    def vibrate(
        self,
        shocker_id: str,
        intensity: int = 50,
        duration: int = 1000,
        api_key: Optional[str] = None,
    ) -> Any:
        """Trigger a vibrate action."""
        return self.send_action(
            shocker_id, "Vibrate", intensity, duration, False, api_key
        )

    def beep(
        self, shocker_id: str, duration: int = 300, api_key: Optional[str] = None
    ) -> Any:
        """Trigger a beep/sound action."""
        return self.send_action(shocker_id, "Sound", 0, duration, False, api_key)
