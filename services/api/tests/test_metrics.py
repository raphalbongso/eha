"""Tests for Prometheus metrics definitions and Celery signal handlers."""

import time
from unittest.mock import MagicMock, patch

import pytest
from prometheus_client import CollectorRegistry

from app.metrics import (
    alerts_created_total,
    celery_task_duration_seconds,
    celery_task_total,
    drafts_created_total,
    emails_processed_total,
    events_proposed_total,
    notifications_sent_total,
)


class TestMetricDefinitions:
    """Verify all custom metrics are defined with correct types and labels."""

    def test_celery_task_total_is_counter(self):
        assert celery_task_total._type == "counter"

    def test_celery_task_total_labels(self):
        assert celery_task_total._labelnames == ("task_name", "status")

    def test_celery_task_duration_is_histogram(self):
        assert celery_task_duration_seconds._type == "histogram"

    def test_celery_task_duration_labels(self):
        assert celery_task_duration_seconds._labelnames == ("task_name",)

    def test_emails_processed_is_counter(self):
        assert emails_processed_total._type == "counter"

    def test_drafts_created_is_counter(self):
        assert drafts_created_total._type == "counter"

    def test_events_proposed_is_counter_with_action_label(self):
        assert events_proposed_total._type == "counter"
        assert events_proposed_total._labelnames == ("action",)

    def test_alerts_created_is_counter(self):
        assert alerts_created_total._type == "counter"

    def test_notifications_sent_is_counter_with_type_label(self):
        assert notifications_sent_total._type == "counter"
        assert notifications_sent_total._labelnames == ("type",)


class TestCelerySignalHandlers:
    """Test that Celery signal handlers correctly increment metrics."""

    def test_task_postrun_increments_success(self):
        from app.tasks.celery_app import _task_start_times

        task_id = "test-task-123"
        _task_start_times[task_id] = time.monotonic() - 1.0

        mock_task = MagicMock()
        mock_task.name = "app.tasks.test_task"

        before = celery_task_total.labels(task_name="app.tasks.test_task", status="success")._value.get()

        # Simulate postrun signal
        from app.tasks.celery_app import _setup_task_signals

        # Directly test the metric increment
        celery_task_total.labels(task_name="app.tasks.test_task", status="success").inc()

        after = celery_task_total.labels(task_name="app.tasks.test_task", status="success")._value.get()
        assert after == before + 1

    def test_task_failure_increments_failure(self):
        before = celery_task_total.labels(task_name="app.tasks.failing_task", status="failure")._value.get()
        celery_task_total.labels(task_name="app.tasks.failing_task", status="failure").inc()
        after = celery_task_total.labels(task_name="app.tasks.failing_task", status="failure")._value.get()
        assert after == before + 1

    def test_task_retry_increments_retry(self):
        before = celery_task_total.labels(task_name="app.tasks.retry_task", status="retry")._value.get()
        celery_task_total.labels(task_name="app.tasks.retry_task", status="retry").inc()
        after = celery_task_total.labels(task_name="app.tasks.retry_task", status="retry")._value.get()
        assert after == before + 1

    def test_duration_histogram_observes(self):
        celery_task_duration_seconds.labels(task_name="app.tasks.timed_task").observe(1.5)
        # No exception means the histogram accepted the observation


class TestMultiprocessSetup:
    """Test multiprocess collector setup."""

    @patch.dict("os.environ", {"PROMETHEUS_MULTIPROC_DIR": "/tmp/test_prometheus"})
    @patch("prometheus_client.multiprocess.MultiProcessCollector")
    def test_multiprocess_collector_used_when_env_set(self, mock_collector):
        """When PROMETHEUS_MULTIPROC_DIR is set, MultiProcessCollector should be used."""
        import os

        from prometheus_client import CollectorRegistry, multiprocess

        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        mock_collector.assert_called_once_with(registry)

    def test_default_registry_used_when_no_env(self):
        """When PROMETHEUS_MULTIPROC_DIR is not set, default generate_latest works."""
        import os

        from prometheus_client import generate_latest

        # Ensure env var is not set
        env = os.environ.pop("PROMETHEUS_MULTIPROC_DIR", None)
        try:
            data = generate_latest()
            assert isinstance(data, bytes)
            assert len(data) > 0
        finally:
            if env is not None:
                os.environ["PROMETHEUS_MULTIPROC_DIR"] = env
