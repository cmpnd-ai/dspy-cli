"""Tests for module discovery including gateway extraction."""

import sys

import dspy

from dspy_cli.discovery.module_finder import (
    DiscoveredModule,
    _extract_gateway_classes,
    discover_modules,
)
from dspy_cli.gateway import APIGateway, CronGateway, IdentityGateway


class TestExtractGatewayClasses:
    """Tests for _extract_gateway_classes function."""

    def test_returns_empty_list_when_no_gateway(self):
        """Should return empty list when module has no gateway attribute."""
        class NoGatewayModule(dspy.Module):
            def forward(self, text: str) -> str:
                return text

        result = _extract_gateway_classes(NoGatewayModule)

        assert result == []

    def test_returns_single_api_gateway_in_list(self):
        """Should return list with single APIGateway subclass when specified."""
        class CustomGateway(APIGateway):
            path = "/custom"

        class ModuleWithGateway(dspy.Module):
            gateway = CustomGateway

            def forward(self, text: str) -> str:
                return text

        result = _extract_gateway_classes(ModuleWithGateway)

        assert result == [CustomGateway]

    def test_returns_identity_gateway_in_list(self):
        """Should return list with IdentityGateway when explicitly specified."""
        class ModuleWithIdentity(dspy.Module):
            gateway = IdentityGateway

            def forward(self, text: str) -> str:
                return text

        result = _extract_gateway_classes(ModuleWithIdentity)

        assert result == [IdentityGateway]

    def test_returns_multiple_gateways_from_list(self):
        """Should return list of gateways when gateway is a list."""
        class CustomCronGateway(CronGateway):
            schedule = "0 * * * *"

        class ModuleWithMultiple(dspy.Module):
            gateway = [CustomCronGateway, IdentityGateway]

            def forward(self, text: str) -> str:
                return text

        result = _extract_gateway_classes(ModuleWithMultiple)

        assert result == [CustomCronGateway, IdentityGateway]

    def test_filters_invalid_items_from_list(self):
        """Should filter out non-Gateway items from list."""
        class NotAGateway:
            pass

        class ModuleWithMixed(dspy.Module):
            gateway = [IdentityGateway, NotAGateway, "string"]

            def forward(self, text: str) -> str:
                return text

        result = _extract_gateway_classes(ModuleWithMixed)

        assert result == [IdentityGateway]

    def test_ignores_non_gateway_class(self):
        """Should return empty list for non-Gateway class attributes."""
        class NotAGateway:
            pass

        class ModuleWithWrongType(dspy.Module):
            gateway = NotAGateway

            def forward(self, text: str) -> str:
                return text

        result = _extract_gateway_classes(ModuleWithWrongType)

        assert result == []

    def test_ignores_gateway_instance(self):
        """Should return empty list when gateway is an instance, not a class."""
        class ModuleWithInstance(dspy.Module):
            gateway = IdentityGateway()

            def forward(self, text: str) -> str:
                return text

        result = _extract_gateway_classes(ModuleWithInstance)

        assert result == []

    def test_ignores_string_gateway(self):
        """Should return empty list when gateway is a string."""
        class ModuleWithString(dspy.Module):
            gateway = "not a gateway"

            def forward(self, text: str) -> str:
                return text

        result = _extract_gateway_classes(ModuleWithString)

        assert result == []


class TestDiscoverModulesWithGateway:
    """Integration tests for discover_modules with gateway extraction."""

    def test_discovers_module_with_gateway(self, tmp_path):
        """Should discover module and extract gateway class."""
        modules_dir = tmp_path / "test_pkg" / "modules"
        modules_dir.mkdir(parents=True)
        
        (modules_dir / "__init__.py").write_text("")
        (tmp_path / "test_pkg" / "__init__.py").write_text("")
        
        module_code = '''
import dspy
from dspy_cli.gateway import APIGateway

class CustomGateway(APIGateway):
    path = "/api/test"

class TestModule(dspy.Module):
    gateway = CustomGateway
    
    def forward(self, text: str) -> str:
        return text
'''
        (modules_dir / "test_module.py").write_text(module_code)
        
        sys.path.insert(0, str(tmp_path))
        try:
            discovered = discover_modules(modules_dir, "test_pkg.modules")
            
            assert len(discovered) == 1
            module = discovered[0]
            assert module.name == "TestModule"
            assert module.gateway_class is not None
            assert module.gateway_class.__name__ == "CustomGateway"
            assert issubclass(module.gateway_class, APIGateway)
        finally:
            sys.path.remove(str(tmp_path))
            for key in list(sys.modules.keys()):
                if key.startswith("test_pkg"):
                    del sys.modules[key]

    def test_discovers_module_without_gateway(self, tmp_path):
        """Should discover module with gateway_class=None when not specified."""
        modules_dir = tmp_path / "test_pkg2" / "modules"
        modules_dir.mkdir(parents=True)
        
        (modules_dir / "__init__.py").write_text("")
        (tmp_path / "test_pkg2" / "__init__.py").write_text("")
        
        module_code = '''
import dspy

class SimpleModule(dspy.Module):
    def forward(self, text: str) -> str:
        return text
'''
        (modules_dir / "simple.py").write_text(module_code)
        
        sys.path.insert(0, str(tmp_path))
        try:
            discovered = discover_modules(modules_dir, "test_pkg2.modules")
            
            assert len(discovered) == 1
            module = discovered[0]
            assert module.name == "SimpleModule"
            assert module.gateway_class is None
        finally:
            sys.path.remove(str(tmp_path))
            for key in list(sys.modules.keys()):
                if key.startswith("test_pkg2"):
                    del sys.modules[key]


class TestDiscoveredModuleDataclass:
    """Tests for DiscoveredModule dataclass."""

    def test_gateway_classes_defaults_to_none(self):
        """gateway_classes should default to None."""
        class DummyModule(dspy.Module):
            pass

        module = DiscoveredModule(
            name="DummyModule",
            class_obj=DummyModule,
            module_path="test.dummy",
        )

        assert module.gateway_classes is None
        assert module.gateway_class is None  # backward-compat property

    def test_gateway_classes_can_be_set(self):
        """gateway_classes can be set to a list of Gateway subclasses."""
        class DummyModule(dspy.Module):
            pass

        class MyGateway(APIGateway):
            pass

        module = DiscoveredModule(
            name="DummyModule",
            class_obj=DummyModule,
            module_path="test.dummy",
            gateway_classes=[MyGateway],
        )

        assert module.gateway_classes == [MyGateway]
        assert module.gateway_class is MyGateway  # backward-compat property

    def test_gateway_class_returns_first_from_list(self):
        """gateway_class property should return first gateway from list."""
        class DummyModule(dspy.Module):
            pass

        class MyGateway(APIGateway):
            pass

        module = DiscoveredModule(
            name="DummyModule",
            class_obj=DummyModule,
            module_path="test.dummy",
            gateway_classes=[MyGateway, IdentityGateway],
        )

        assert module.gateway_class is MyGateway
