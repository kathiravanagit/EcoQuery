from deployment import deployment_version


def test_configured_deployment_version_wins(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "2026.10.03-abc123")
    assert deployment_version() == "2026.10.03-abc123"


def test_dev_marker_does_not_hide_the_commit(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "dev")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123def456")
    assert deployment_version() == "abc123def456"
