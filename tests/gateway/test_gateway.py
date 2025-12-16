"""Tests for Gateway base classes."""

import asyncio
from typing import Any, Dict, List

import pytest
from pydantic import BaseModel

from dspy_cli.gateway import APIGateway, CronGateway, Gateway, IdentityGateway


def run_async(coro):
    """Helper to run async functions in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestIdentityGateway:
    """Tests for IdentityGateway (default pass-through)."""

    def test_to_pipeline_inputs_dict_passthrough(self):
        """Dict inputs should pass through unchanged."""
        gateway = IdentityGateway()
        inputs = {"text": "hello", "count": 5}
        
        result = gateway.to_pipeline_inputs(inputs)
        
        assert result == {"text": "hello", "count": 5}

    def test_to_pipeline_inputs_pydantic_model(self):
        """Pydantic model should be converted to dict."""
        class RequestModel(BaseModel):
            text: str
            count: int
        
        gateway = IdentityGateway()
        request = RequestModel(text="hello", count=5)
        
        result = gateway.to_pipeline_inputs(request)
        
        assert result == {"text": "hello", "count": 5}

    def test_to_pipeline_inputs_empty(self):
        """Empty/None inputs should return empty dict."""
        gateway = IdentityGateway()
        
        assert gateway.to_pipeline_inputs({}) == {}
        assert gateway.to_pipeline_inputs(None) == {}

    def test_from_pipeline_output_passthrough(self):
        """Output should pass through unchanged."""
        gateway = IdentityGateway()
        output = {"answer": "result", "score": 0.95}
        
        result = gateway.from_pipeline_output(output)
        
        assert result == {"answer": "result", "score": 0.95}

    def test_default_attributes(self):
        """Default attributes should be set correctly."""
        gateway = IdentityGateway()
        
        assert gateway.request_model is None
        assert gateway.response_model is None
        assert gateway.path is None
        assert gateway.method == "POST"
        assert gateway.requires_auth is True


class TestAPIGateway:
    """Tests for custom APIGateway subclasses."""

    def test_custom_to_pipeline_inputs(self):
        """Subclass can override input transformation."""
        class WebhookGateway(APIGateway):
            def to_pipeline_inputs(self, request: Any) -> Dict[str, Any]:
                return {"text": request["data"]["content"]}
        
        gateway = WebhookGateway()
        request = {"data": {"content": "hello world"}}
        
        result = gateway.to_pipeline_inputs(request)
        
        assert result == {"text": "hello world"}

    def test_custom_from_pipeline_output(self):
        """Subclass can override output transformation."""
        class WrappedGateway(APIGateway):
            def from_pipeline_output(self, output: Any) -> Any:
                return {"status": "success", "result": output}
        
        gateway = WrappedGateway()
        output = {"answer": "42"}
        
        result = gateway.from_pipeline_output(output)
        
        assert result == {"status": "success", "result": {"answer": "42"}}

    def test_custom_path_and_method(self):
        """Subclass can set custom path and method."""
        class CustomGateway(APIGateway):
            path = "/api/v2/analyze"
            method = "PUT"
            requires_auth = True
        
        gateway = CustomGateway()
        
        assert gateway.path == "/api/v2/analyze"
        assert gateway.method == "PUT"
        assert gateway.requires_auth is True

    def test_custom_request_response_models(self):
        """Subclass can specify Pydantic models."""
        class MyRequest(BaseModel):
            query: str
        
        class MyResponse(BaseModel):
            answer: str
        
        class TypedGateway(APIGateway):
            request_model = MyRequest
            response_model = MyResponse
        
        gateway = TypedGateway()
        
        assert gateway.request_model is MyRequest
        assert gateway.response_model is MyResponse


class TestCronGateway:
    """Tests for CronGateway abstract class."""

    def test_requires_schedule(self):
        """CronGateway subclass must define schedule."""
        class ValidCronGateway(CronGateway):
            schedule = "*/5 * * * *"
            
            async def get_pipeline_inputs(self) -> List[Dict[str, Any]]:
                return [{"text": "test"}]
            
            async def on_complete(self, inputs: Dict[str, Any], output: Any) -> None:
                pass
        
        gateway = ValidCronGateway()
        assert gateway.schedule == "*/5 * * * *"

    def test_abstract_methods_required(self):
        """Cannot instantiate CronGateway without implementing abstract methods."""
        class IncompleteCronGateway(CronGateway):
            schedule = "0 * * * *"
        
        with pytest.raises(TypeError, match="abstract"):
            IncompleteCronGateway()

    def test_get_pipeline_inputs(self):
        """get_pipeline_inputs should return list of input dicts."""
        class TestCronGateway(CronGateway):
            schedule = "0 0 * * *"
            
            async def get_pipeline_inputs(self) -> List[Dict[str, Any]]:
                return [
                    {"id": 1, "text": "first"},
                    {"id": 2, "text": "second"},
                ]
            
            async def on_complete(self, inputs: Dict[str, Any], output: Any) -> None:
                pass
        
        gateway = TestCronGateway()
        inputs = run_async(gateway.get_pipeline_inputs())
        
        assert len(inputs) == 2
        assert inputs[0] == {"id": 1, "text": "first"}

    def test_on_complete_receives_inputs_and_output(self):
        """on_complete should receive original inputs and pipeline output."""
        received = {}
        
        class TrackingCronGateway(CronGateway):
            schedule = "0 0 * * *"
            
            async def get_pipeline_inputs(self) -> List[Dict[str, Any]]:
                return [{"text": "test", "_meta": {"msg_id": 123}}]
            
            async def on_complete(self, inputs: Dict[str, Any], output: Any) -> None:
                received["inputs"] = inputs
                received["output"] = output
        
        gateway = TrackingCronGateway()
        inputs = run_async(gateway.get_pipeline_inputs())[0]
        run_async(gateway.on_complete(inputs, {"result": "done"}))
        
        assert received["inputs"]["_meta"]["msg_id"] == 123
        assert received["output"] == {"result": "done"}


class TestGatewayInheritance:
    """Tests for Gateway class hierarchy."""

    def test_identity_gateway_is_api_gateway(self):
        """IdentityGateway should be a subclass of APIGateway."""
        assert issubclass(IdentityGateway, APIGateway)
        assert issubclass(IdentityGateway, Gateway)

    def test_api_gateway_is_gateway(self):
        """APIGateway should be a subclass of Gateway."""
        assert issubclass(APIGateway, Gateway)

    def test_cron_gateway_is_gateway(self):
        """CronGateway should be a subclass of Gateway."""
        assert issubclass(CronGateway, Gateway)

    def test_cron_gateway_not_api_gateway(self):
        """CronGateway should NOT be a subclass of APIGateway."""
        assert not issubclass(CronGateway, APIGateway)
