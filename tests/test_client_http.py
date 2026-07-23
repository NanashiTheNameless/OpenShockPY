"""Sync client tests that inspect the actual HTTP calls being made."""

import json

import pytest
from OpenShockPY import (
    OpenShockAuthError,
    OpenShockClient,
    OpenShockNotFoundError,
    OpenShockPYError,
    OpenShockRateLimitError,
    OpenShockValidationError,
)


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None, text=None):
        self.status_code = status_code
        self._json = json_data
        self.headers = headers or {}
        self.text = text if text is not None else json.dumps(json_data or {})
        self.content = b"" if json_data is None and not text else self.text.encode()

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


class Recorder:
    """Records every call and replays a queue of scripted responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        if len(self.responses) == 1:
            return self.responses[0]
        return self.responses.pop(0)


@pytest.fixture
def record(monkeypatch):
    def _install(*responses):
        recorder = Recorder(responses)
        monkeypatch.setattr(
            "OpenShockPY.client.requests.Session.request", recorder
        )
        return recorder

    return _install


def make_client(**kwargs):
    kwargs.setdefault("api_key", "tok")
    kwargs.setdefault("user_agent", "OpenShockPY-Test/0.1")
    return OpenShockClient(**kwargs)


def test_user_agent_is_required():
    client = OpenShockClient(api_key="tok")
    with pytest.raises(OpenShockValidationError):
        client.list_devices()


def test_api_token_sent_under_canonical_header(record):
    recorder = record(FakeResponse(200, {"data": []}))
    make_client().list_devices()
    headers = recorder.calls[0]["headers"]
    assert headers["OpenShockToken"] == "tok"
    # The server also accepts the legacy spelling; keep sending it for
    # older self-hosted deployments.
    assert headers["Open-Shock-Token"] == "tok"


def test_per_call_api_key_overrides_stored_one(record):
    recorder = record(FakeResponse(200, {"data": []}))
    make_client().list_devices(api_key="other")
    assert recorder.calls[0]["headers"]["OpenShockToken"] == "other"


def test_empty_per_call_api_key_strips_stored_header(record):
    recorder = record(FakeResponse(200, {"data": []}))
    make_client().list_devices(api_key="")
    assert recorder.calls[0]["headers"]["OpenShockToken"] is None


def test_session_token_sets_header_and_cookie(record):
    recorder = record(FakeResponse(200, {"data": []}))
    client = OpenShockClient(user_agent="OpenShockPY-Test/0.1")
    client.SetSessionToken("session-token")
    client.list_devices()
    assert client._session.headers["OpenShockSession"] == "session-token"
    assert client._session.cookies.get("openShockSession") == "session-token"
    assert recorder.calls[0]["method"] == "GET"


def test_control_uses_v2_endpoint_and_schema(record):
    recorder = record(FakeResponse(200, {"message": "ok"}))
    make_client().shock("s1", intensity=40, duration=1200, exclusive=True)
    call = recorder.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api.openshock.app/2/shockers/control"
    assert call["json"] == {
        "shocks": [
            {
                "id": "s1",
                "type": "Shock",
                "intensity": 40,
                "duration": 1200,
                "exclusive": True,
            }
        ],
        "customName": None,
    }


def test_custom_name_is_forwarded(record):
    recorder = record(FakeResponse(200, {"message": "ok"}))
    make_client().beep("s1", custom_name="nightly job")
    assert recorder.calls[0]["json"]["customName"] == "nightly job"


def test_stop_sends_stop_type(record):
    recorder = record(FakeResponse(200, {"message": "ok"}))
    make_client().stop("s1")
    entry = recorder.calls[0]["json"]["shocks"][0]
    assert entry["type"] == "Stop"
    assert entry["duration"] >= 300


def test_shock_all_string_dispatches_to_all(record):
    recorder = record(
        FakeResponse(200, {"data": [{"id": "hub", "shockers": [{"id": "s1"}]}]}),
        FakeResponse(200, {"message": "ok"}),
    )
    make_client().shock("ALL", intensity=10)
    assert recorder.calls[0]["url"].endswith("/1/shockers/own")
    assert recorder.calls[1]["json"]["shocks"][0]["id"] == "s1"


def test_send_action_all_deduplicates_shockers(record):
    recorder = record(
        FakeResponse(
            200,
            {
                "data": [
                    {"id": "hub1", "shockers": [{"id": "s1"}, {"id": "s2"}]},
                    {"id": "hub2", "shockers": [{"id": "s1"}]},
                ]
            },
        ),
        FakeResponse(200, {"message": "ok"}),
    )
    make_client().vibrate_all(intensity=20, duration=700)
    ids = [s["id"] for s in recorder.calls[1]["json"]["shocks"]]
    assert ids == ["s1", "s2"]


def test_send_action_all_sends_one_atomic_request(record):
    """The API declares no cap on ControlRequest.shocks, so never split."""
    shockers = [{"id": f"s{i}"} for i in range(200)]
    recorder = record(
        FakeResponse(200, {"data": [{"id": "hub", "shockers": shockers}]}),
        FakeResponse(200, {"message": "ok"}),
    )
    make_client().stop_all()
    posts = [c for c in recorder.calls if c["method"] == "POST"]
    assert len(posts) == 1
    assert len(posts[0]["json"]["shocks"]) == 200


def test_send_action_all_without_shockers_raises(record):
    record(FakeResponse(200, {"data": []}))
    with pytest.raises(OpenShockNotFoundError):
        make_client().shock_all()


def test_list_shockers_with_device_id_uses_device_endpoint(record):
    recorder = record(FakeResponse(200, {"data": []}))
    make_client().list_shockers("dev-1")
    assert recorder.calls[0]["url"].endswith("/1/devices/dev-1/shockers")


def test_pause_shocker_body(record):
    recorder = record(FakeResponse(200, {"message": "ok"}))
    make_client().pause_shocker("s1", True)
    assert recorder.calls[0]["url"].endswith("/1/shockers/s1/pause")
    assert recorder.calls[0]["json"] == {"pause": True}


def test_logs_query_params_drop_none(record):
    recorder = record(FakeResponse(200, {"data": []}))
    make_client().get_logs(page=2, page_size=50)
    assert recorder.calls[0]["params"] == {"page": 2, "pageSize": 50}


def test_error_status_maps_to_typed_exception(record):
    record(FakeResponse(403, {"detail": "Not allowed", "status": 403}))
    with pytest.raises(OpenShockAuthError) as exc:
        make_client().list_devices()
    assert exc.value.status_code == 403
    assert "Not allowed" in str(exc.value)
    # still catchable as the historical base error
    assert isinstance(exc.value, OpenShockPYError)


def test_non_json_error_body_is_tolerated(record):
    record(FakeResponse(500, None, text="<html>oops</html>"))
    with pytest.raises(OpenShockPYError) as exc:
        make_client().list_devices()
    assert exc.value.status_code == 500


def test_no_content_response_returns_none(record):
    record(FakeResponse(204, None, text=""))
    assert make_client().stop("s1") is None


def test_retries_on_rate_limit_then_succeeds(record, monkeypatch):
    slept = []
    monkeypatch.setattr("OpenShockPY.client.time.sleep", slept.append)
    recorder = record(
        FakeResponse(429, {"detail": "slow down"}, headers={"Retry-After": "3"}),
        FakeResponse(200, {"data": []}),
    )
    make_client().list_devices()
    assert len(recorder.calls) == 2
    assert slept == [3.0]


def test_control_post_is_not_replayed_after_a_server_error(record, monkeypatch):
    """A 504 may mean the shock landed and only the response was lost."""
    monkeypatch.setattr("OpenShockPY.client.time.sleep", lambda _: None)
    recorder = record(FakeResponse(504, {"detail": "gateway timeout"}))
    with pytest.raises(OpenShockPYError):
        make_client().shock("s1")
    assert len(recorder.calls) == 1


def test_control_post_is_not_replayed_after_a_timeout(record, monkeypatch):
    import requests

    monkeypatch.setattr("OpenShockPY.client.time.sleep", lambda _: None)
    calls = []

    class Boom:
        def __call__(self, method, url, **kwargs):
            calls.append(method)
            raise requests.ConnectionError("dropped")

    monkeypatch.setattr("OpenShockPY.client.requests.Session.request", Boom())
    with pytest.raises(OpenShockPYError):
        make_client().shock("s1")
    assert calls == ["POST"]


def test_control_post_is_replayed_after_a_rate_limit(record, monkeypatch):
    """429 means the request was rejected, so replaying it is safe."""
    monkeypatch.setattr("OpenShockPY.client.time.sleep", lambda _: None)
    recorder = record(
        FakeResponse(429, {"detail": "slow down"}),
        FakeResponse(200, {"message": "ok"}),
    )
    make_client().shock("s1")
    assert len(recorder.calls) == 2


def test_gives_up_after_max_retries(record, monkeypatch):
    monkeypatch.setattr("OpenShockPY.client.time.sleep", lambda _: None)
    recorder = record(FakeResponse(429, {"detail": "slow down"}))
    with pytest.raises(OpenShockRateLimitError):
        make_client(max_retries=2).list_devices()
    assert len(recorder.calls) == 3


def test_close_is_idempotent_and_blocks_reuse():
    client = make_client()
    client.close()
    client.close()
    with pytest.raises(OpenShockPYError):
        client.list_devices()


def test_context_manager_closes():
    with make_client() as client:
        assert client._session is not None
    assert client._session is None


def test_base_url_is_normalized(record):
    recorder = record(FakeResponse(200, {"data": []}))
    client = make_client(base_url="https://api.openshock.dev/")
    client.list_devices()
    assert recorder.calls[0]["url"] == "https://api.openshock.dev/1/devices"
