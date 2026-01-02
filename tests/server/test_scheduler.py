"""Tests for GatewayScheduler."""

from typing import Any, Dict, List
from unittest.mock import MagicMock

import dspy
import pytest

from dspy_cli.discovery import DiscoveredModule
from dspy_cli.gateway import CronGateway
from dspy_cli.server.scheduler import GatewayScheduler


class MockCronGateway(CronGateway):
    """Test CronGateway implementation."""

    schedule = "*/5 * * * *"

    def __init__(self, use_batch: bool = False, num_threads: int | None = None):
        self.inputs_to_return: List[Dict[str, Any]] = []
        self.completed_calls: List[tuple] = []
        self.use_batch = use_batch
        self.num_threads = num_threads

    async def get_pipeline_inputs(self) -> List[Dict[str, Any]]:
        return self.inputs_to_return

    async def on_complete(self, inputs: Dict[str, Any], output: Any) -> None:
        self.completed_calls.append((inputs, output))


@pytest.fixture
def mock_module():
    """Create a mock DiscoveredModule."""
    module = MagicMock(spec=DiscoveredModule)
    module.name = "TestModule"
    module.is_forward_typed = False
    module.forward_input_fields = None

    mock_instance = MagicMock()
    mock_instance.return_value = {"result": "test_output"}
    module.instantiate.return_value = mock_instance

    return module


@pytest.fixture
def mock_lm():
    """Create a mock LM."""
    lm = MagicMock(spec=dspy.LM)
    lm.copy.return_value = lm
    lm.history = []
    return lm


class TestGatewayScheduler:
    """Tests for GatewayScheduler."""

    def test_init(self, tmp_path):
        """Scheduler initializes with empty jobs."""
        scheduler = GatewayScheduler(logs_dir=tmp_path)

        assert scheduler.job_count == 0
        assert scheduler.logs_dir == tmp_path

    def test_register_cron_gateway(self, tmp_path, mock_module, mock_lm):
        """Registering a cron gateway adds a job."""
        scheduler = GatewayScheduler(logs_dir=tmp_path)
        gateway = MockCronGateway()

        scheduler.register_cron_gateway(
            module=mock_module,
            gateway=gateway,
            lm=mock_lm,
            model_name="test-model",
        )

        assert scheduler.job_count == 1
        assert "TestModule" in scheduler._jobs

    def test_multiple_registrations(self, tmp_path, mock_lm):
        """Multiple gateways can be registered."""
        scheduler = GatewayScheduler(logs_dir=tmp_path)

        for i in range(3):
            module = MagicMock(spec=DiscoveredModule)
            module.name = f"Module{i}"
            module.is_forward_typed = False
            module.forward_input_fields = None
            module.instantiate.return_value = MagicMock(return_value={"result": "ok"})

            gateway = MockCronGateway()
            scheduler.register_cron_gateway(
                module=module,
                gateway=gateway,
                lm=mock_lm,
                model_name="test-model",
            )

        assert scheduler.job_count == 3

    def test_shutdown_when_not_running(self, tmp_path):
        """Shutdown is safe when scheduler not running."""
        scheduler = GatewayScheduler(logs_dir=tmp_path)
        scheduler.shutdown()


class TestCronJobExecution:
    """Tests for cron job execution flow."""

    def test_job_is_registered(self, tmp_path, mock_module, mock_lm):
        """Job should be registered with correct ID."""
        scheduler = GatewayScheduler(logs_dir=tmp_path)
        gateway = MockCronGateway()
        gateway.inputs_to_return = [{"text": "test"}]

        scheduler.register_cron_gateway(
            module=mock_module,
            gateway=gateway,
            lm=mock_lm,
            model_name="test-model",
        )

        job = scheduler.scheduler.get_job("cron_TestModule")
        assert job is not None

    def test_job_handles_empty_inputs(self, tmp_path, mock_module, mock_lm):
        """Job should handle empty input list gracefully."""
        scheduler = GatewayScheduler(logs_dir=tmp_path)
        gateway = MockCronGateway()
        gateway.inputs_to_return = []

        scheduler.register_cron_gateway(
            module=mock_module,
            gateway=gateway,
            lm=mock_lm,
            model_name="test-model",
        )

        assert scheduler.job_count == 1


class TestCronGatewayBatchConfig:
    """Tests for CronGateway batch mode configuration."""

    def test_default_batch_settings(self):
        """CronGateway has batch disabled by default."""
        gateway = MockCronGateway()
        assert gateway.use_batch is False
        assert gateway.num_threads is None

    def test_batch_enabled(self):
        """CronGateway can enable batch mode."""
        gateway = MockCronGateway(use_batch=True, num_threads=4)
        assert gateway.use_batch is True
        assert gateway.num_threads == 4

    def test_register_batch_gateway_logs_batch_info(self, tmp_path, mock_module, mock_lm, caplog):
        """Registering a batch gateway logs batch info."""
        import logging
        caplog.set_level(logging.INFO)

        scheduler = GatewayScheduler(logs_dir=tmp_path)
        gateway = MockCronGateway(use_batch=True, num_threads=8)
        gateway.inputs_to_return = []

        scheduler.register_cron_gateway(
            module=mock_module,
            gateway=gateway,
            lm=mock_lm,
            model_name="test-model",
        )

        assert "batch=True" in caplog.text
        assert "threads=8" in caplog.text

    def test_register_sequential_gateway_no_batch_in_log(self, tmp_path, mock_module, mock_lm, caplog):
        """Registering a sequential gateway doesn't mention batch."""
        import logging
        caplog.set_level(logging.INFO)

        scheduler = GatewayScheduler(logs_dir=tmp_path)
        gateway = MockCronGateway(use_batch=False)
        gateway.inputs_to_return = []

        scheduler.register_cron_gateway(
            module=mock_module,
            gateway=gateway,
            lm=mock_lm,
            model_name="test-model",
        )

        assert "batch=" not in caplog.text
