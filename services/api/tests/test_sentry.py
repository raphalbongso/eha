"""Tests for Sentry initialization."""

from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from app.config import Settings
from app.main import _init_sentry


def _make_settings(**overrides) -> Settings:
    defaults = {
        "database_url": "postgresql+asyncpg://test:test@localhost/test",
        "redis_url": "redis://localhost:6379/0",
        "celery_broker_url": "redis://localhost:6379/1",
        "celery_result_backend": "redis://localhost:6379/2",
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestSentryInit:
    @patch("sentry_sdk.init")
    def test_init_called_when_dsn_set(self, mock_init):
        """sentry_sdk.init() is called when sentry_dsn is configured."""
        settings = _make_settings(
            sentry_dsn=SecretStr("https://abc@sentry.io/123"),
            sentry_traces_sample_rate=0.25,
        )
        _init_sentry(settings)

        mock_init.assert_called_once()
        call_kwargs = mock_init.call_args[1]
        assert call_kwargs["dsn"] == "https://abc@sentry.io/123"
        assert call_kwargs["traces_sample_rate"] == 0.25
        assert call_kwargs["send_default_pii"] is False

    def test_init_skipped_when_no_dsn(self):
        """sentry_sdk.init() is NOT called when sentry_dsn is empty."""
        settings = _make_settings(sentry_dsn=SecretStr(""))
        # Should return early without importing sentry_sdk — no error raised
        _init_sentry(settings)
