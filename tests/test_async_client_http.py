"""Async client tests that inspect the actual HTTP calls being made."""

import json

import pytest
from OpenShockPY import (
    OpenShockAuthError,
    OpenShockNotFoundError,
    OpenShockPYError,
    OpenShockRateLimitError,
    OpenShockValidationError,
)
from OpenShockPY.async_client import AsyncOpenShockClient

respx = pytest.importorskip("respx")
httpx = pytest.importorskip("httpx")

BASE = "https://api.openshock.app"


def make_client(**kwargs):
    kwargs.setdefault("api_key", "tok")
    kwargs.setdefault("user_agent", "OpenShockPY-Test/0.1")
    return AsyncOpenShockClient(**kwargs)


def body_of(route, index=-1):
    return json.loads(route.calls[index].request.content)


@pytest.mark.asyncio
async def test_user_agent_is_required():
    async with AsyncOpenShockClient(api_key="tok") as client:
        with pytest.raises(OpenShockValidationError):
            await client.list_devices()


@pytest.mark.asyncio
@respx.mock
async def test_api_token_sent_under_canonical_header():
    route = respx.get(f"{BASE}/1/devices").respond(200, json={"data": []})
    async with make_client() as client:
        await client.list_devices()
    headers = route.calls[0].request.headers
    assert headers["OpenShockToken"] == "tok"
    assert headers["Open-Shock-Token"] == "tok"


@pytest.mark.asyncio
@respx.mock
async def test_session_token_sets_header_and_cookie():
    route = respx.get(f"{BASE}/1/devices").respond(200, json={"data": []})
    async with AsyncOpenShockClient(user_agent="OpenShockPY-Test/0.1") as client:
        client.SetSessionToken("session-token")
        await client.list_devices()
    request = route.calls[0].request
    assert request.headers["OpenShockSession"] == "session-token"
    assert "openShockSession=session-token" in request.headers["cookie"]


@pytest.mark.asyncio
@respx.mock
async def test_control_uses_v2_endpoint_and_schema():
    route = respx.post(f"{BASE}/2/shockers/control").respond(200, json={"message": ""})
    async with make_client() as client:
        await client.shock("s1", intensity=40, duration=1200, exclusive=True)
    assert body_of(route) == {
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


@pytest.mark.asyncio
@respx.mock
async def test_custom_name_is_forwarded():
    route = respx.post(f"{BASE}/2/shockers/control").respond(200, json={"message": ""})
    async with make_client() as client:
        await client.vibrate("s1", custom_name="nightly job")
    assert body_of(route)["customName"] == "nightly job"


@pytest.mark.asyncio
@respx.mock
async def test_all_keyword_dispatches_like_the_sync_client():
    """`shock("all")` used to hit the API with a literal id of "all"."""
    respx.get(f"{BASE}/1/shockers/own").respond(
        200, json={"data": [{"id": "hub", "shockers": [{"id": "s1"}, {"id": "s2"}]}]}
    )
    route = respx.post(f"{BASE}/2/shockers/control").respond(200, json={"message": ""})
    async with make_client() as client:
        await client.shock("all", intensity=10)
    assert {s["id"] for s in body_of(route)["shocks"]} == {"s1", "s2"}


@pytest.mark.asyncio
@respx.mock
async def test_send_action_all_deduplicates_shockers():
    respx.get(f"{BASE}/1/shockers/own").respond(
        200,
        json={
            "data": [
                {"id": "hub1", "shockers": [{"id": "s1"}, {"id": "s2"}]},
                {"id": "hub2", "shockers": [{"id": "s1"}]},
            ]
        },
    )
    route = respx.post(f"{BASE}/2/shockers/control").respond(200, json={"message": ""})
    async with make_client() as client:
        await client.stop_all()
    assert [s["id"] for s in body_of(route)["shocks"]] == ["s1", "s2"]


@pytest.mark.asyncio
@respx.mock
async def test_send_action_all_sends_one_atomic_request():
    """The API declares no cap on ControlRequest.shocks, so never split."""
    shockers = [{"id": f"s{i}"} for i in range(200)]
    respx.get(f"{BASE}/1/shockers/own").respond(
        200, json={"data": [{"id": "hub", "shockers": shockers}]}
    )
    route = respx.post(f"{BASE}/2/shockers/control").respond(200, json={"message": ""})
    async with make_client() as client:
        await client.beep_all()
    assert len(route.calls) == 1
    assert len(body_of(route)["shocks"]) == 200


@pytest.mark.asyncio
@respx.mock
async def test_send_action_all_without_shockers_raises():
    respx.get(f"{BASE}/1/shockers/own").respond(200, json={"data": []})
    async with make_client() as client:
        with pytest.raises(OpenShockNotFoundError):
            await client.shock_all()


@pytest.mark.asyncio
@respx.mock
async def test_list_shockers_with_device_id_uses_device_endpoint():
    route = respx.get(f"{BASE}/1/devices/dev-1/shockers").respond(
        200, json={"data": []}
    )
    async with make_client() as client:
        await client.list_shockers("dev-1")
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_pause_shocker_body():
    route = respx.post(f"{BASE}/1/shockers/s1/pause").respond(200, json={"message": ""})
    async with make_client() as client:
        await client.pause_shocker("s1", False)
    assert body_of(route) == {"pause": False}


@pytest.mark.asyncio
@respx.mock
async def test_logs_query_params_drop_none():
    route = respx.get(f"{BASE}/1/shockers/logs").respond(200, json={"data": []})
    async with make_client() as client:
        await client.get_logs(page=2, page_size=50)
    assert route.calls[0].request.url.params.multi_items() == [
        ("page", "2"),
        ("pageSize", "50"),
    ]


@pytest.mark.asyncio
@respx.mock
async def test_error_status_maps_to_typed_exception():
    respx.get(f"{BASE}/1/devices").respond(
        403, json={"detail": "Not allowed", "status": 403}
    )
    async with make_client() as client:
        with pytest.raises(OpenShockAuthError) as exc:
            await client.list_devices()
    assert exc.value.status_code == 403
    assert isinstance(exc.value, OpenShockPYError)


@pytest.mark.asyncio
@respx.mock
async def test_no_content_response_returns_none():
    respx.post(f"{BASE}/2/shockers/control").respond(204)
    async with make_client() as client:
        assert await client.stop("s1") is None


@pytest.mark.asyncio
@respx.mock
async def test_retries_on_rate_limit_then_succeeds(monkeypatch):
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr("OpenShockPY.async_client.asyncio.sleep", fake_sleep)
    route = respx.get(f"{BASE}/1/devices")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "3"}, json={"detail": "slow"}),
        httpx.Response(200, json={"data": []}),
    ]
    async with make_client() as client:
        await client.list_devices()
    assert len(route.calls) == 2
    assert slept == [3.0]


@pytest.mark.asyncio
@respx.mock
async def test_control_post_is_not_replayed_after_a_server_error(monkeypatch):
    """A 504 may mean the shock landed and only the response was lost."""

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("OpenShockPY.async_client.asyncio.sleep", fake_sleep)
    route = respx.post(f"{BASE}/2/shockers/control").respond(504, json={"detail": "gw"})
    async with make_client() as client:
        with pytest.raises(OpenShockPYError):
            await client.shock("s1")
    assert len(route.calls) == 1


@pytest.mark.asyncio
@respx.mock
async def test_control_post_is_not_replayed_after_a_timeout(monkeypatch):
    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("OpenShockPY.async_client.asyncio.sleep", fake_sleep)
    route = respx.post(f"{BASE}/2/shockers/control").mock(
        side_effect=httpx.ConnectTimeout("dropped")
    )
    async with make_client() as client:
        with pytest.raises(OpenShockPYError):
            await client.shock("s1")
    assert len(route.calls) == 1


@pytest.mark.asyncio
@respx.mock
async def test_control_post_is_replayed_after_a_rate_limit(monkeypatch):
    """429 means the request was rejected, so replaying it is safe."""

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("OpenShockPY.async_client.asyncio.sleep", fake_sleep)
    route = respx.post(f"{BASE}/2/shockers/control")
    route.side_effect = [
        httpx.Response(429, json={"detail": "slow"}),
        httpx.Response(200, json={"message": "ok"}),
    ]
    async with make_client() as client:
        await client.shock("s1")
    assert len(route.calls) == 2


@pytest.mark.asyncio
@respx.mock
async def test_gives_up_after_max_retries(monkeypatch):
    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("OpenShockPY.async_client.asyncio.sleep", fake_sleep)
    route = respx.get(f"{BASE}/1/devices").respond(429, json={"detail": "slow"})
    async with make_client(max_retries=2) as client:
        with pytest.raises(OpenShockRateLimitError):
            await client.list_devices()
    assert len(route.calls) == 3


@pytest.mark.asyncio
@respx.mock
async def test_transport_errors_are_wrapped(monkeypatch):
    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("OpenShockPY.async_client.asyncio.sleep", fake_sleep)
    respx.get(f"{BASE}/1/devices").mock(side_effect=httpx.ConnectError("boom"))
    async with make_client(max_retries=0) as client:
        with pytest.raises(OpenShockPYError) as exc:
            await client.list_devices()
    assert "boom" in str(exc.value)


@pytest.mark.asyncio
async def test_aclose_is_idempotent_and_blocks_reuse():
    client = make_client()
    await client.aclose()
    await client.aclose()
    with pytest.raises(OpenShockPYError):
        await client.list_devices()


@pytest.mark.asyncio
@respx.mock
async def test_base_url_is_normalized():
    route = respx.get("https://api.openshock.dev/1/devices").respond(
        200, json={"data": []}
    )
    async with make_client(base_url="https://api.openshock.dev/") as client:
        await client.list_devices()
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_sync_and_async_expose_the_same_surface():
    from OpenShockPY import OpenShockClient

    def public(obj):
        return {
            name
            for name in dir(obj)
            if not name.startswith("_") and callable(getattr(obj, name))
        }

    # Only the close methods differ by name; everything else is 1:1.
    assert public(OpenShockClient) - {"close"} == (
        public(AsyncOpenShockClient) - {"aclose"}
    )
