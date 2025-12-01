import json

import pytest
from OpenShockPY.async_client import AsyncOpenShockClient
from OpenShockPY.client import OpenShockPYError

respx = pytest.importorskip("respx")
httpx = pytest.importorskip("httpx")


@pytest.mark.asyncio
@respx.mock
async def test_list_shockers_success():
    client = AsyncOpenShockClient(api_key="abc", user_agent="OpenShockPY-Test/0.1")

    respx.get("https://api.openshock.app/1/shockers/own").respond(
        200,
        json={
            "data": [{"id": "device-uuid", "shockers": [{"id": "s1"}]}],
            "message": "",
        },
    )

    data = await client.list_shockers()
    assert "data" in data
    assert data["data"][0]["shockers"][0]["id"] == "s1"

    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_shock_all_success():
    client = AsyncOpenShockClient(api_key="abc", user_agent="OpenShockPY-Test/0.1")

    # Mock the shockers listing
    respx.get("https://api.openshock.app/1/shockers/own").respond(
        200,
        json={
            "data": [{"id": "device-uuid", "shockers": [{"id": "s1"}, {"id": "s2"}]}],
            "message": "",
        },
    )

    post_route = respx.post("https://api.openshock.app/2/shockers/control").respond(
        200, json={"ok": True}
    )

    data = await client.shock_all(intensity=40, duration=1200)
    assert data.get("ok") is True  # type: ignore

    # assert last call payload was the array with both s1, s2
    assert post_route.calls
    call = post_route.calls[-1]
    body = json.loads(call.request.content)
    assert isinstance(body, dict)
    assert "shocks" in body
    assert len(body["shocks"]) == 2
    assert {s["id"] for s in body["shocks"]} == {"s1", "s2"}

    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_shock_all_flat_shockers():
    client = AsyncOpenShockClient(api_key="abc", user_agent="OpenShockPY-Test/0.1")

    respx.get("https://api.openshock.app/1/shockers/own").respond(
        200,
        json={"shockers": [{"id": "s1"}], "message": ""},
    )

    post_route = respx.post("https://api.openshock.app/2/shockers/control").respond(
        200, json={"ok": True}
    )

    data = await client.beep_all(duration=400)
    assert data.get("ok") is True  # type: ignore

    assert post_route.calls
    call = post_route.calls[-1]
    body = json.loads(call.request.content)
    assert isinstance(body, dict)
    assert len(body["shocks"]) == 1
    assert body["shocks"][0]["id"] == "s1"

    await client.aclose()


@pytest.mark.asyncio
async def test_async_intensity_validation():
    client = AsyncOpenShockClient(api_key="abc", user_agent="OpenShockPY-Test/0.1")
    with pytest.raises(OpenShockPYError):
        await client.shock("s1", intensity=200)
    await client.aclose()


@pytest.mark.asyncio
async def test_async_all_duration_validation():
    client = AsyncOpenShockClient(api_key="abc", user_agent="OpenShockPY-Test/0.1")
    with pytest.raises(OpenShockPYError):
        await client.vibrate_all(duration=200)
    await client.aclose()
