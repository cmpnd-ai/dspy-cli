"""Tests for module discovery including gateway extraction."""

import sys

import dspy

from dspy_cli.discovery.module_finder import (
    DiscoveredModule,
    _extract_gateway_class,
    discover_modules,
)
from dspy_cli.gateway import APIGateway, IdentityGateway


class TestExtractGatewayClass:
    """Tests for _extract_gateway_class function."""

    def test_returns_none_when_no_gateway(self):
        """Should return None when module has no gateway attribute."""
        class NoGatewayModule(dspy.Module):
            def forward(self, text: str) -> str:
                return text
        
        result = _extract_gateway_class(NoGatewayModule)
        
        assert result is None

    def test_returns_api_gateway_class(self):
        """Should return APIGateway subclass when specified."""
        class CustomGateway(APIGateway):
            path = "/custom"
        
        class ModuleWithGateway(dspy.Module):
            gateway = CustomGateway
            
            def forward(self, text: str) -> str:
                return text
        
        result = _extract_gateway_class(ModuleWithGateway)
        
        assert result is CustomGateway

    def test_returns_identity_gateway_class(self):
        """Should return IdentityGateway when explicitly specified."""
        class ModuleWithIdentity(dspy.Module):
            gateway = IdentityGateway
            
            def forward(self, text: str) -> str:
                return text
        
        result = _extract_gateway_class(ModuleWithIdentity)
        
        assert result is IdentityGateway

    def test_ignores_non_gateway_class(self):
        """Should return None for non-Gateway class attributes."""
        class NotAGateway:
            pass
        
        class ModuleWithWrongType(dspy.Module):
            gateway = NotAGateway
            
            def forward(self, text: str) -> str:
                return text
        
        result = _extract_gateway_class(ModuleWithWrongType)
        
        assert result is None

    def test_ignores_gateway_instance(self):
        """Should return None when gateway is an instance, not a class."""
        class ModuleWithInstance(dspy.Module):
            gateway = IdentityGateway()
            
            def forward(self, text: str) -> str:
                return text
        
        result = _extract_gateway_class(ModuleWithInstance)
        
        assert result is None

    def test_ignores_string_gateway(self):
        """Should return None when gateway is a string."""
        class ModuleWithString(dspy.Module):
            gateway = "not a gateway"
            
            def forward(self, text: str) -> str:
                return text
        
        result = _extract_gateway_class(ModuleWithString)
        
        assert result is None


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

    def test_gateway_class_defaults_to_none(self):
        """gateway_class should default to None."""
        class DummyModule(dspy.Module):
            pass
        
        module = DiscoveredModule(
            name="DummyModule",
            class_obj=DummyModule,
            module_path="test.dummy",
        )
        
        assert module.gateway_class is None

    def test_gateway_class_can_be_set(self):
        """gateway_class can be set to a Gateway subclass."""
        class DummyModule(dspy.Module):
            pass
        
        class MyGateway(APIGateway):
            pass
        
        module = DiscoveredModule(
            name="DummyModule",
            class_obj=DummyModule,
            module_path="test.dummy",
            gateway_class=MyGateway,
        )
        
        assert module.gateway_class is MyGateway
