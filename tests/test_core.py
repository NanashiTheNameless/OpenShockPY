import pytest
from OpenShockPY import _core


def test_extract_shocker_ids_nested_hubs():
    response = {
        "message": "",
        "data": [
            {"id": "hub1", "shockers": [{"id": "s1"}, {"id": "s2"}]},
            {"id": "hub2", "shockers": [{"id": "s3"}]},
        ],
    }
    assert _core.extract_shocker_ids(response) == ["s1", "s2", "s3"]


def test_extract_shocker_ids_flat_list():
    response = {"message": "", "data": [{"id": "s1"}, {"id": "s2"}]}
    assert _core.extract_shocker_ids(response) == ["s1", "s2"]


def test_extract_shocker_ids_legacy_top_level_key():
    assert _core.extract_shocker_ids({"shockers": [{"id": "s1"}]}) == ["s1"]


def test_extract_shocker_ids_deduplicates_and_keeps_order():
    response = {
        "data": [{"id": "hub", "shockers": [{"id": "s2"}, {"id": "s1"}]}],
        "shockers": [{"id": "s1"}, {"id": "s3"}],
    }
    assert _core.extract_shocker_ids(response) == ["s2", "s1", "s3"]


def test_extract_shocker_ids_ignores_junk():
    assert _core.extract_shocker_ids({"data": ["nope", 3, {}]}) == []
    assert _core.extract_shocker_ids(None) == []
    assert _core.extract_shocker_ids([]) == []


@pytest.mark.parametrize(
    "intensity,duration",
    [(0, 300), (100, 65535), (50, 1000)],
)
def test_validate_action_params_accepts_bounds(intensity, duration):
    _core.validate_action_params(intensity, duration)


@pytest.mark.parametrize(
    "intensity,duration",
    [(-1, 1000), (101, 1000), (50, 299), (50, 65536)],
)
def test_validate_action_params_rejects_out_of_range(intensity, duration):
    with pytest.raises(_core.OpenShockValidationError):
        _core.validate_action_params(intensity, duration)


def test_validate_action_params_rejects_non_integers():
    with pytest.raises(_core.OpenShockValidationError):
        _core.validate_action_params("50", 1000)  # type: ignore[arg-type]
    with pytest.raises(_core.OpenShockValidationError):
        _core.validate_action_params(50, True)  # type: ignore[arg-type]


def test_validate_control_type_rejects_unknown():
    with pytest.raises(_core.OpenShockValidationError):
        _core.validate_control_type("Zap")


def test_build_control_request_rejects_empty():
    with pytest.raises(_core.OpenShockValidationError):
        _core.build_control_request([])


def test_build_control_request_imposes_no_size_cap():
    """ControlRequest.shocks declares no maxItems in either API version."""
    many = [_core.build_control(f"s{i}", "Shock", 1, 300) for i in range(500)]
    assert len(_core.build_control_request(many)["shocks"]) == 500


def test_build_control_request_shape():
    payload = _core.build_control_request(
        [_core.build_control("s1", "Vibrate", 20, 700, True)], "my script"
    )
    assert payload == {
        "shocks": [
            {
                "id": "s1",
                "type": "Vibrate",
                "intensity": 20,
                "duration": 700,
                "exclusive": True,
            }
        ],
        "customName": "my script",
    }


def test_build_api_error_maps_status_codes():
    assert isinstance(_core.build_api_error(401, {}), _core.OpenShockAuthError)
    assert isinstance(_core.build_api_error(403, {}), _core.OpenShockAuthError)
    assert isinstance(_core.build_api_error(404, {}), _core.OpenShockNotFoundError)
    assert isinstance(_core.build_api_error(429, {}), _core.OpenShockRateLimitError)
    assert isinstance(_core.build_api_error(503, {}), _core.OpenShockServerError)
    generic = _core.build_api_error(418, {})
    assert type(generic) is _core.OpenShockAPIError
    # Every API error stays catchable as the historical exception type.
    assert isinstance(generic, _core.OpenShockPYError)


def test_build_api_error_uses_problem_detail():
    err = _core.build_api_error(412, {"detail": "Shocker is paused", "status": 412})
    assert err.status_code == 412
    assert "Shocker is paused" in str(err)
    assert err.payload == {"detail": "Shocker is paused", "status": 412}


def test_rate_limit_error_carries_retry_after():
    err = _core.build_api_error(429, {}, retry_after=12.0)
    assert isinstance(err, _core.OpenShockRateLimitError)
    assert err.retry_after == 12.0


def test_parse_retry_after():
    assert _core.parse_retry_after("5") == 5.0
    assert _core.parse_retry_after(" 2.5 ") == 2.5
    assert _core.parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") is None
    assert _core.parse_retry_after("-1") is None
    assert _core.parse_retry_after(None) is None


def test_should_retry():
    assert _core.should_retry(429)
    assert _core.should_retry(503)
    assert not _core.should_retry(200)
    assert not _core.should_retry(404)


def test_post_is_only_retried_when_the_server_rejected_it():
    """A replayed control POST would deliver a second shock."""
    # 429 means the request never executed, so replaying it is safe.
    assert _core.should_retry(429, "POST")
    # These are ambiguous: the shock may already have been delivered.
    for status in (502, 503, 504):
        assert not _core.should_retry(status, "POST")
        assert _core.should_retry(status, "GET")
        assert _core.should_retry(status, "DELETE")


def test_transport_errors_are_only_retried_for_idempotent_methods():
    assert _core.should_retry_transport_error("GET")
    assert _core.should_retry_transport_error("delete")
    assert not _core.should_retry_transport_error("POST")


def test_validation_error_is_also_a_value_error():
    """Older code caught ValueError from SetUA/SetBaseURL."""
    assert issubclass(_core.OpenShockValidationError, ValueError)
    assert issubclass(_core.OpenShockValidationError, _core.OpenShockPYError)


def test_retry_delay_prefers_retry_after_and_caps():
    assert _core.retry_delay(0, backoff_factor=0.5) == 0.5
    assert _core.retry_delay(2, backoff_factor=0.5) == 2.0
    assert _core.retry_delay(0, retry_after=7.0) == 7.0
    assert _core.retry_delay(99, backoff_factor=0.5, max_delay=30.0) == 30.0


def test_normalize_base_url():
    assert _core.normalize_base_url(" https://api.openshock.app/ ") == (
        "https://api.openshock.app"
    )
    with pytest.raises(_core.OpenShockValidationError):
        _core.normalize_base_url("   ")


def test_auth_headers_uses_canonical_and_legacy_names():
    headers = _core.auth_headers("token")
    assert headers == {"OpenShockToken": "token", "Open-Shock-Token": "token"}
    assert _core.auth_headers(None) == {}


def test_session_headers():
    assert _core.session_headers("s") == {"OpenShockSession": "s"}
    assert _core.session_headers(None) == {}


def test_clean_params_drops_none():
    assert _core.clean_params({"a": 1, "b": None, "c": 0}) == {"a": 1, "c": 0}
