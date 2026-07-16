from app.api.routes.health import health_check


def test_health_check() -> None:
    assert health_check() == {"status": "ok"}
