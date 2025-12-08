# This software is licensed under NNCL v1.3-MODIFIED-OpenShockPY see LICENSE.md for more info
# https://github.com/NanashiTheNameless/OpenShockPY/blob/main/LICENSE.md
from typing import Any, Dict, List, Optional

import httpx  # type: ignore

from .client import (
    ControlType,
    OpenShockPYError,
)


class AsyncOpenShockClient:
    """Asynchronous client for interacting with the OpenShock API.

    This mirrors the functionality of the synchronous `OpenShockClient` but
    uses `httpx.AsyncClient` for non-blocking HTTP calls.

    Usage:

    ```python
    import asyncio
    from OpenShockPY import AsyncOpenShockClient

    async def main():
        async with AsyncOpenShockClient(api_key="KEY", user_agent="MyApp/1.0") as client:
            devices = await client.list_devices()
            await client.shock_all(intensity=50, duration=1000)
            await client.stop_all()

    asyncio.run(main())
    ```
    """

    base_url: str
    timeout: int
    api_key: Optional[str]

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openshock.app",
        timeout: int = 15,
        user_agent: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip(" /")
        self.timeout = timeout
        self.api_key = api_key
        self.user_agent: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

        self._client.headers.setdefault("Content-Type", "application/json")
        self._client.headers.setdefault("Accept", "application/json")
        if user_agent is not None:
            self.SetUA(user_agent)
        self.SetAPIKey(api_key)

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def _handle(self, resp: httpx.Response) -> Any:
        if 200 <= resp.status_code < 300:
            if resp.content:
                return resp.json()
            return None
        try:
            payload = resp.json()
        except Exception:
            payload = {"message": resp.text}
        raise OpenShockPYError(f"HTTP {resp.status_code}: {payload}")

    def _get_headers(self, api_key: Optional[str] = None) -> Dict[str, Any]:
        self._ensure_user_agent()
        headers = dict(self._client.headers)
        key = api_key if api_key is not None else self.api_key
        if key:
            headers["Open-Shock-Token"] = key
        else:
            headers.pop("Open-Shock-Token", None)
        return headers

    def _validate_action_params(self, intensity: int, duration: int) -> None:
        if intensity < 0 or intensity > 100:
            raise OpenShockPYError("intensity must be between 0 and 100")
        if duration < 300 or duration > 65535:
            raise OpenShockPYError(
                "duration must be between 300 and 65535 milliseconds"
            )

    def _ensure_user_agent(self) -> None:
        if not self.user_agent:
            raise OpenShockPYError(
                "User-Agent must be set via SetUA before using the client"
            )

    def SetUA(self, user_agent: str) -> None:
        """Update the User-Agent header (must be provided before requests)."""
        if not user_agent:
            raise ValueError("user_agent must be provided to SetUA")
        self.user_agent = user_agent
        self._client.headers["User-Agent"] = user_agent

    def SetAPIKey(self, api_key: Optional[str]) -> None:
        """Store the API key in memory and refresh headers/cookies."""
        self.api_key = api_key
        if api_key:
            self._client.headers["Open-Shock-Token"] = api_key
            # Some deployments expect the token as a cookie; set both.
            host = httpx.URL(self.base_url).host
            self._client.cookies.set(
                "Open-Shock-Token",
                api_key,
                domain=host or None,
                path="/",
            )
        else:
            self._client.headers.pop("Open-Shock-Token", None)
            self._client.cookies.pop("Open-Shock-Token", None)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncOpenShockClient":
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.aclose()

    # Devices
    async def list_devices(self, api_key: Optional[str] = None) -> Dict[str, Any]:
        resp = await self._client.get(
            self._url("/1/devices"), headers=self._get_headers(api_key)
        )
        return await self._handle(resp)

    async def get_device(
        self, device_id: str, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        resp = await self._client.get(
            self._url(f"/1/devices/{device_id}"), headers=self._get_headers(api_key)
        )
        return await self._handle(resp)

    async def list_shockers(
        self, device_id: Optional[str] = None, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        if device_id:
            resp = await self._client.get(
                self._url(f"/1/devices/{device_id}/shockers"),
                headers=self._get_headers(api_key),
            )
        else:
            resp = await self._client.get(
                self._url("/1/shockers/own"), headers=self._get_headers(api_key)
            )
        return await self._handle(resp)

    async def get_shocker(
        self, shocker_id: str, api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        resp = await self._client.get(
            self._url(f"/1/shockers/{shocker_id}"), headers=self._get_headers(api_key)
        )
        return await self._handle(resp)

    # Actions
    async def send_action(
        self,
        shocker_id: str,
        control_type: ControlType,
        intensity: int = 0,
        duration: int = 1000,
        exclusive: bool = False,
        api_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
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
        resp = await self._client.post(
            self._url("/2/shockers/control"),
            json=payload,
            headers=self._get_headers(api_key),
        )
        return await self._handle(resp)

    async def shock(
        self,
        shocker_id: str,
        intensity: int = 50,
        duration: int = 1000,
        api_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return await self.send_action(
            shocker_id, "Shock", intensity, duration, False, api_key
        )

    async def vibrate(
        self,
        shocker_id: str,
        intensity: int = 50,
        duration: int = 1000,
        api_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return await self.send_action(
            shocker_id, "Vibrate", intensity, duration, False, api_key
        )

    async def beep(
        self, shocker_id: str, duration: int = 300, api_key: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        return await self.send_action(shocker_id, "Sound", 0, duration, False, api_key)

    async def stop(
        self, shocker_id: str, api_key: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        return await self.send_action(shocker_id, "Stop", 0, 300, False, api_key)

    async def send_action_all(
        self,
        control_type: ControlType,
        intensity: int = 0,
        duration: int = 1000,
        exclusive: bool = False,
        api_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        self._validate_action_params(intensity, duration)
        # Get all shockers
        shockers_response = await self.list_shockers(api_key=api_key)
        devices = shockers_response.get("data", [])

        # Extract all shockers from both flat and nested responses
        all_shockers: List[Dict[str, Any]] = []
        if isinstance(devices, list):
            for entry in devices:
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

        payload = {"shocks": shocks_list, "customName": None}
        resp = await self._client.post(
            self._url("/2/shockers/control"),
            json=payload,
            headers=self._get_headers(api_key),
        )
        return await self._handle(resp)

    async def shock_all(
        self, intensity: int = 50, duration: int = 1000, api_key: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        return await self.send_action_all("Shock", intensity, duration, False, api_key)

    async def vibrate_all(
        self, intensity: int = 50, duration: int = 1000, api_key: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        return await self.send_action_all(
            "Vibrate", intensity, duration, False, api_key
        )

    async def beep_all(
        self, duration: int = 300, api_key: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        return await self.send_action_all("Sound", 0, duration, False, api_key)

    async def stop_all(self, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return await self.send_action_all("Stop", 0, 300, False, api_key)
