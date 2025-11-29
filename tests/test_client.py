import json
import types
import builtins
import pytest

from OpenShockPY.client import OpenShockClient, OpenShockError


class DummyResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text or json.dumps(self._json)
        self.content = self.text.encode("utf-8")

    def json(self):
        return self._json


class RequestsMock:
    def __init__(self):
        self.calls = []
        self._routes = {}

    def when(self, method: str, url: str, result: DummyResponse):
        self._routes[(method.upper(), url)] = result
        return self

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        key = (method.upper(), url)
        resp = self._routes.get(key)
        if resp is None:
            return DummyResponse(status_code=404, json_data={"error": "not found"})
        return resp


@pytest.fixture
def requests_mock(monkeypatch):
    mock = RequestsMock()
    monkeypatch.setattr("OpenShockPY.client.requests.Session.request", mock.request)
    return mock


def test_list_devices_success(requests_mock):
    client = OpenShockClient(api_key="abc", user_agent="OpenShockPY-Test/0.1")
    requests_mock.when(
        "GET",
        "https://api.openshock.app/1/devices",
        DummyResponse(200, {"devices": [{"id": "d1"}]}),
    )
    data = client.list_devices()
    assert "devices" in data
    assert data["devices"][0]["id"] == "d1"


def test_list_shockers_success(requests_mock):
    client = OpenShockClient(api_key="abc", user_agent="OpenShockPY-Test/0.1")
    requests_mock.when(
        "GET",
        "https://api.openshock.app/1/shockers/own",
        DummyResponse(200, {"shockers": [{"id": "s1"}]}),
    )
    data = client.list_shockers()
    assert "shockers" in data
    assert data["shockers"][0]["id"] == "s1"


def test_send_action_validation_error(requests_mock):
    client = OpenShockClient(api_key="abc", user_agent="OpenShockPY-Test/0.1")
    with pytest.raises(OpenShockError):
        client.shock("s1", intensity=150, duration=500)


def test_shock_vibrate_beep_success(requests_mock):
    client = OpenShockClient(api_key="abc", user_agent="OpenShockPY-Test/0.1")
    # Control endpoint
    requests_mock.when(
        "POST",
        "https://api.openshock.app/2/shockers/control",
        DummyResponse(200, {"ok": True}),
    )

    # Shock
    data = client.shock("s-uuid", intensity=40, duration=1200)
    assert data.get("ok") is True

    # Vibrate
    data = client.vibrate("s-uuid", intensity=20, duration=800)
    assert data.get("ok") is True

    # Beep
    data = client.beep("s-uuid", duration=500)
    assert data.get("ok") is True
