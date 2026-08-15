from app.redis import LOGOUT_CHANNEL, build_redis


def test_build_redis_none_when_unconfigured() -> None:
    assert build_redis(None) is None


def test_logout_channel_value() -> None:
    assert LOGOUT_CHANNEL == "lichat:logout"
