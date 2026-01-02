"""Tests for gateway discovery."""


import dspy

from dspy_cli.discovery import DiscoveredModule
from dspy_cli.discovery.gateway_finder import (
    get_gateway_class,
    get_gateway_for_module,
    is_api_gateway,
    is_cron_gateway,
)
from dspy_cli.gateway import APIGateway, CronGateway, IdentityGateway


class TestGetGatewayForModule:
    """Tests for get_gateway_for_module function."""

    def test_returns_identity_gateway_when_no_gateway(self):
        """Should return IdentityGateway when module has no gateway attr."""
        class SimpleModule(dspy.Module):
            pass
        
        module = DiscoveredModule(
            name="SimpleModule",
            class_obj=SimpleModule,
            module_path="test.simple",
        )
        
        gateway = get_gateway_for_module(module)
        
        assert isinstance(gateway, IdentityGateway)

    def test_returns_custom_api_gateway(self):
        """Should return custom APIGateway when specified."""
        class CustomGateway(APIGateway):
            path = "/custom"
        
        class ModuleWithGateway(dspy.Module):
            gateway = CustomGateway
        
        module = DiscoveredModule(
            name="ModuleWithGateway",
            class_obj=ModuleWithGateway,
            module_path="test.with_gateway",
            gateway_class=CustomGateway,
        )
        
        gateway = get_gateway_for_module(module)
        
        assert isinstance(gateway, CustomGateway)
        assert gateway.path == "/custom"

    def test_returns_identity_for_invalid_gateway_attr(self):
        """Should fallback to IdentityGateway for invalid gateway attr."""
        class ModuleWithBadGateway(dspy.Module):
            gateway = "not a gateway class"
        
        module = DiscoveredModule(
            name="ModuleWithBadGateway",
            class_obj=ModuleWithBadGateway,
            module_path="test.bad_gateway",
        )
        
        gateway = get_gateway_for_module(module)
        
        assert isinstance(gateway, IdentityGateway)


class TestGetGatewayClass:
    """Tests for get_gateway_class function."""

    def test_returns_none_when_no_gateway(self):
        """Should return None when module has no gateway attr."""
        class NoGatewayModule(dspy.Module):
            pass
        
        module = DiscoveredModule(
            name="NoGatewayModule",
            class_obj=NoGatewayModule,
            module_path="test.no_gateway",
        )
        
        result = get_gateway_class(module)
        
        assert result is None

    def test_returns_gateway_class(self):
        """Should return gateway class when specified."""
        class MyGateway(APIGateway):
            pass
        
        class ModuleWithGateway(dspy.Module):
            gateway = MyGateway
        
        module = DiscoveredModule(
            name="ModuleWithGateway",
            class_obj=ModuleWithGateway,
            module_path="test.with_gateway",
            gateway_class=MyGateway,
        )
        
        result = get_gateway_class(module)
        
        assert result is MyGateway

    def test_ignores_non_gateway_class(self):
        """Should return None for non-Gateway class attributes."""
        class NotAGateway:
            pass
        
        class ModuleWithWrongType(dspy.Module):
            gateway = NotAGateway
        
        module = DiscoveredModule(
            name="ModuleWithWrongType",
            class_obj=ModuleWithWrongType,
            module_path="test.wrong_type",
        )
        
        result = get_gateway_class(module)
        
        assert result is None

    def test_ignores_gateway_instance(self):
        """Should return None when gateway is an instance, not a class."""
        class ModuleWithInstance(dspy.Module):
            gateway = IdentityGateway()
        
        module = DiscoveredModule(
            name="ModuleWithInstance",
            class_obj=ModuleWithInstance,
            module_path="test.instance",
        )
        
        result = get_gateway_class(module)
        
        assert result is None


class TestIsApiGateway:
    """Tests for is_api_gateway type check."""

    def test_identity_gateway_is_api(self):
        """IdentityGateway should be an API gateway."""
        assert is_api_gateway(IdentityGateway()) is True

    def test_api_gateway_subclass_is_api(self):
        """APIGateway subclass should be an API gateway."""
        class CustomAPI(APIGateway):
            pass
        
        assert is_api_gateway(CustomAPI()) is True

    def test_cron_gateway_is_not_api(self):
        """CronGateway should not be an API gateway."""
        class TestCron(CronGateway):
            schedule = "* * * * *"
            async def get_pipeline_inputs(self): return []
            async def on_complete(self, inputs, output): pass
        
        assert is_api_gateway(TestCron()) is False


class TestIsCronGateway:
    """Tests for is_cron_gateway type check."""

    def test_cron_gateway_is_cron(self):
        """CronGateway should be detected."""
        class TestCron(CronGateway):
            schedule = "* * * * *"
            async def get_pipeline_inputs(self): return []
            async def on_complete(self, inputs, output): pass
        
        assert is_cron_gateway(TestCron()) is True

    def test_api_gateway_is_not_cron(self):
        """APIGateway should not be a cron gateway."""
        assert is_cron_gateway(APIGateway()) is False
        assert is_cron_gateway(IdentityGateway()) is False
