"""Unit tests for the shared pipeline execution module."""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import dspy
import pytest

from dspy_cli.server.execution import (
    _convert_dspy_types,
    _extract_lm_metrics,
    _normalize_output,
    _serialize_for_logging,
    execute_pipeline,
)


def run_async(coro):
    """Helper to run async functions in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestNormalizeOutput:
    """Tests for _normalize_output function."""

    def test_prediction_to_dict(self):
        """dspy.Prediction should be converted to dict."""
        module = MagicMock()
        module.is_forward_typed = False
        module.forward_output_fields = None

        prediction = dspy.Prediction(answer="hello", confidence=0.9)
        result = _normalize_output(prediction, module)

        assert isinstance(result, dict)
        assert result["answer"] == "hello"
        assert result["confidence"] == 0.9

    def test_dict_passthrough(self):
        """Dict should pass through unchanged."""
        module = MagicMock()
        module.is_forward_typed = False
        module.forward_output_fields = None

        data = {"key": "value", "num": 42}
        result = _normalize_output(data, module)

        assert result == data

    def test_simple_value_with_typed_output(self):
        """Simple value with single typed output field should use field name."""
        module = MagicMock()
        module.is_forward_typed = True
        module.forward_output_fields = {"summary": {"type": "str", "annotation": str}}

        result = _normalize_output("This is a summary", module)

        assert result == {"summary": "This is a summary"}

    def test_simple_value_without_typed_output(self):
        """Simple value without typed output should use 'result' key."""
        module = MagicMock()
        module.is_forward_typed = False
        module.forward_output_fields = None

        result = _normalize_output("plain text", module)

        assert result == {"result": "plain text"}

    def test_object_with_dict(self):
        """Object with __dict__ should be converted via vars()."""
        module = MagicMock()
        module.is_forward_typed = False
        module.forward_output_fields = None

        @dataclass
        class Result:
            name: str
            value: int

        obj = Result(name="test", value=123)
        result = _normalize_output(obj, module)

        assert result == {"name": "test", "value": 123}


class TestConvertDspyTypes:
    """Tests for _convert_dspy_types function."""

    def test_passthrough_when_not_typed(self):
        """Should pass through when module is not forward typed."""
        module = MagicMock()
        module.is_forward_typed = False
        module.forward_input_fields = None

        inputs = {"text": "hello"}
        result = _convert_dspy_types(inputs, module)

        assert result == inputs

    def test_passthrough_unknown_fields(self):
        """Should pass through fields not in forward_input_fields."""
        module = MagicMock()
        module.is_forward_typed = True
        module.forward_input_fields = {"known": {"annotation": str}}

        inputs = {"known": "value", "unknown": "other"}
        result = _convert_dspy_types(inputs, module)

        assert result["unknown"] == "other"

    def test_passthrough_non_dspy_types(self):
        """Should pass through non-dspy types."""
        module = MagicMock()
        module.is_forward_typed = True
        module.forward_input_fields = {"text": {"annotation": str}}

        inputs = {"text": "hello"}
        result = _convert_dspy_types(inputs, module)

        assert result == {"text": "hello"}


class TestExtractLmMetrics:
    """Tests for _extract_lm_metrics function."""

    def test_no_history(self):
        """Should return None values when no history."""
        lm = MagicMock()
        lm.history = []

        result = _extract_lm_metrics(lm, 0)

        assert result == {"tokens": None, "cost_usd": None, "lm_calls": None}

    def test_no_history_attr(self):
        """Should handle LM without history attribute."""
        lm = MagicMock(spec=[])

        result = _extract_lm_metrics(lm, 0)

        assert result == {"tokens": None, "cost_usd": None, "lm_calls": None}

    def test_extracts_token_counts(self):
        """Should extract token counts from history."""
        lm = MagicMock()
        lm.history = [
            {
                "model": "gpt-4",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                "cost": 0.005,
            },
            {
                "model": "gpt-4",
                "usage": {"prompt_tokens": 80, "completion_tokens": 30},
                "cost": 0.003,
            },
        ]

        result = _extract_lm_metrics(lm, 0)

        assert result["tokens"]["prompt_tokens"] == 180
        assert result["tokens"]["completion_tokens"] == 80
        assert result["tokens"]["total_tokens"] == 260
        assert result["cost_usd"] == 0.008
        assert len(result["lm_calls"]) == 2

    def test_respects_start_index(self):
        """Should only count entries from start_idx onwards."""
        lm = MagicMock()
        lm.history = [
            {"model": "gpt-4", "usage": {"prompt_tokens": 100, "completion_tokens": 50}},
            {"model": "gpt-4", "usage": {"prompt_tokens": 80, "completion_tokens": 30}},
        ]

        result = _extract_lm_metrics(lm, 1)

        assert result["tokens"]["prompt_tokens"] == 80
        assert result["tokens"]["completion_tokens"] == 30


class TestSerializeForLogging:
    """Tests for _serialize_for_logging function."""

    def test_dict_serialization(self, tmp_path):
        """Should serialize nested dicts."""
        data = {"outer": {"inner": "value"}}
        result = _serialize_for_logging(data, tmp_path, "test_program")

        assert result == {"outer": {"inner": "value"}}

    def test_list_serialization(self, tmp_path):
        """Should serialize lists."""
        data = ["a", "b", "c"]
        result = _serialize_for_logging(data, tmp_path, "test_program")

        assert result == ["a", "b", "c"]

    def test_passthrough_primitives(self, tmp_path):
        """Should pass through primitive types."""
        assert _serialize_for_logging("text", tmp_path, "prog") == "text"
        assert _serialize_for_logging(42, tmp_path, "prog") == 42
        assert _serialize_for_logging(True, tmp_path, "prog") is True


class TestExecutePipeline:
    """Tests for execute_pipeline function."""

    def test_successful_execution(self, tmp_path):
        """Should execute module and return output dict."""
        module = MagicMock()
        module.is_forward_typed = False
        module.forward_output_fields = None

        # Use spec to ensure instance doesn't have aforward (sync execution path)
        instance = MagicMock(spec=['__call__'])
        instance.return_value = {"result": "success"}

        lm = MagicMock()
        lm.copy.return_value = lm
        lm.history = []

        async def run():
            with patch("dspy_cli.server.execution.dspy.context"):
                return await execute_pipeline(
                    module=module,
                    instance=instance,
                    lm=lm,
                    model_name="test-model",
                    program_name="test_program",
                    inputs={"text": "hello"},
                    logs_dir=tmp_path,
                )

        result = run_async(run())
        assert result == {"result": "success"}
        instance.assert_called_once_with(text="hello")

    def test_async_module_execution(self, tmp_path):
        """Should use acall for modules with aforward."""
        module = MagicMock()
        module.is_forward_typed = False
        module.forward_output_fields = None

        instance = MagicMock(spec=['aforward', 'acall'])
        instance.acall = AsyncMock(return_value={"async_result": "done"})

        lm = MagicMock()
        lm.copy.return_value = lm
        lm.history = []

        async def run():
            with patch("dspy_cli.server.execution.dspy.context"):
                return await execute_pipeline(
                    module=module,
                    instance=instance,
                    lm=lm,
                    model_name="test-model",
                    program_name="test_program",
                    inputs={"query": "test"},
                    logs_dir=tmp_path,
                )

        result = run_async(run())
        assert result == {"async_result": "done"}
        instance.acall.assert_called_once_with(query="test")

    def test_logs_on_success(self, tmp_path):
        """Should log inference on successful execution."""
        module = MagicMock()
        module.is_forward_typed = False
        module.forward_output_fields = None

        # Use spec to ensure instance doesn't have aforward (sync execution path)
        instance = MagicMock(spec=['__call__'])
        instance.return_value = {"result": "ok"}

        lm = MagicMock()
        lm.copy.return_value = lm
        lm.history = []

        async def run():
            with patch("dspy_cli.server.execution.dspy.context"), \
                 patch("dspy_cli.server.execution.log_inference") as mock_log:
                await execute_pipeline(
                    module=module,
                    instance=instance,
                    lm=lm,
                    model_name="gpt-4",
                    program_name="my_program",
                    inputs={"x": 1},
                    logs_dir=tmp_path,
                )
                return mock_log

        mock_log = run_async(run())
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["program_name"] == "my_program"
        assert call_kwargs["model"] == "gpt-4"
        assert "error" not in call_kwargs or call_kwargs.get("error") is None

    def test_logs_on_error(self, tmp_path):
        """Should log inference with error on failure."""
        module = MagicMock()
        module.is_forward_typed = False
        module.forward_output_fields = None

        # Use spec to ensure instance doesn't have aforward (sync execution path)
        instance = MagicMock(spec=['__call__'])
        instance.side_effect = ValueError("Something went wrong")

        lm = MagicMock()
        lm.copy.return_value = lm
        lm.history = []

        mock_log_ref = MagicMock()

        async def run():
            with patch("dspy_cli.server.execution.dspy.context"), \
                 patch("dspy_cli.server.execution.log_inference") as mock_log:
                mock_log_ref.mock = mock_log
                await execute_pipeline(
                    module=module,
                    instance=instance,
                    lm=lm,
                    model_name="gpt-4",
                    program_name="failing_program",
                    inputs={"x": 1},
                    logs_dir=tmp_path,
                )

        with pytest.raises(ValueError, match="Something went wrong"):
            run_async(run())

        mock_log_ref.mock.assert_called_once()
        call_kwargs = mock_log_ref.mock.call_args.kwargs
        assert call_kwargs["error"] == "Something went wrong"
        assert call_kwargs["outputs"] == {}

    def test_copies_lm_for_isolation(self, tmp_path):
        """Should copy LM to avoid concurrent request interference."""
        module = MagicMock()
        module.is_forward_typed = False
        module.forward_output_fields = None

        # Use spec to ensure instance doesn't have aforward (sync execution path)
        instance = MagicMock(spec=['__call__'])
        instance.return_value = {}

        lm = MagicMock()
        copied_lm = MagicMock()
        copied_lm.history = []
        lm.copy.return_value = copied_lm

        async def run():
            with patch("dspy_cli.server.execution.dspy.context") as mock_context:
                await execute_pipeline(
                    module=module,
                    instance=instance,
                    lm=lm,
                    model_name="test",
                    program_name="test",
                    inputs={},
                    logs_dir=tmp_path,
                )
                return mock_context

        mock_context = run_async(run())
        lm.copy.assert_called_once()
        mock_context.assert_called_once_with(lm=copied_lm)
