from datetime import datetime, timedelta, timezone

from routers.auth import _generate_state, _oauth_states, _validate_state


def test_oauth_state_requires_the_initiating_cookie():
    state = _generate_state()

    assert _validate_state(state, "different-state") is False
    assert _validate_state(state, state) is True


def test_oauth_state_is_one_time_use():
    state = _generate_state()

    assert _validate_state(state, state) is True
    assert _validate_state(state, state) is False


def test_oauth_state_expiry_is_enforced():
    state = _generate_state()
    _oauth_states[state] = datetime.now(timezone.utc) - timedelta(seconds=1)

    assert _validate_state(state, state) is False
