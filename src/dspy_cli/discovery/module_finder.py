"""DSPy module discovery via introspection."""

import importlib.util
import inspect
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import dspy

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredModule:
    """Information about a discovered DSPy module."""

    name: str  # Module name (e.g., "CategorizerPredict")
    class_obj: Type[dspy.Module]  # The actual class
    module_path: str  # Python module path (e.g., "dspy_project.modules.categorizer_predict")
    signature: Optional[Type[dspy.Signature]] = None  # Signature if discoverable

    def instantiate(self, lm: dspy.LM | None = None) -> dspy.Module:
        """Create an instance of this module."""
        return self.class_obj()


def discover_modules(
    package_path: Path,
    package_name: str,
    require_public: bool = True
) -> List[DiscoveredModule]:
    """Discover DSPy modules in a package using direct file imports.

    This function:
    1. Enumerates all Python files in the directory
    2. Directly imports each file using importlib.util
    3. Finds classes that subclass dspy.Module
    4. Returns information about each discovered module

    Args:
        package_path: Path to the package directory (e.g., src/dspy_project/modules)
        package_name: Full Python package name (e.g., "dspy_project.modules")
        require_public: If True, skip classes with names starting with _

    Returns:
        List of DiscoveredModule objects
    """
    discovered = []

    # Ensure the package path exists
    if not package_path.exists():
        logger.warning(f"Package path does not exist: {package_path}")
        return discovered

    # Add parent directories to sys.path to allow relative imports
    src_path = package_path.parent.parent
    package_parent_path = package_path.parent

    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    if str(package_parent_path) not in sys.path:
        sys.path.insert(0, str(package_parent_path))

    # Find all Python files in the modules directory
    python_files = list(package_path.glob("*.py"))

    for py_file in python_files:
        # Skip __init__.py and private modules
        if py_file.name == "__init__.py" or py_file.name.startswith("_"):
            continue

        module_name = py_file.stem  # filename without .py
        full_module_name = f"{package_name}.{module_name}"

        try:
            # Load the module directly from file
            spec = importlib.util.spec_from_file_location(full_module_name, py_file)
            if spec is None or spec.loader is None:
                logger.warning(f"Could not load spec for {py_file}")
                continue

            module = importlib.util.module_from_spec(spec)

            # Add to sys.modules before executing to support circular imports
            sys.modules[full_module_name] = module

            # Execute the module
            spec.loader.exec_module(module)

            # Find all classes in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Check if it's a DSPy Module
                if not issubclass(obj, dspy.Module):
                    continue

                # Skip dspy.Module itself
                if obj is dspy.Module:
                    continue

                # Check that the class is defined in this module (not imported)
                if obj.__module__ != full_module_name:
                    continue

                # Skip private classes if required
                if require_public and name.startswith("_"):
                    continue

                logger.info(f"Discovered module: {name} in {py_file.name}")

                # Try to extract signature information
                signature = _extract_signature(obj)

                discovered.append(
                    DiscoveredModule(
                        name=name,
                        class_obj=obj,
                        module_path=full_module_name,
                        signature=signature
                    )
                )

        except ModuleNotFoundError as e:
            logger.error(f"Error loading module {py_file}: {e}")
            logger.warning(
                f"\n⚠  Missing dependency detected while importing {py_file.name}\n"
                f"   This might be because you are using a global dspy-cli install rather than a local one.\n\n"
                f"   To fix this:\n"
                f"   1. Install dependencies: uv sync (or pip install -e .)\n"
                f"   2. Run from within the venv: source .venv/bin/activate && dspy-cli serve\n"
                f"   3. Or use a task runner: uv run dspy-cli serve\n"
            )
            continue
        except Exception as e:
            logger.error(f"Error loading module {py_file}: {e}", exc_info=True)
            continue

    return discovered


def _extract_signature(module_class: Type[dspy.Module]) -> Optional[Type[dspy.Signature]]:
    """Try to extract the signature from a DSPy module.

    This looks for predictors in the module's __init__ method and extracts
    their signatures.

    Args:
        module_class: The DSPy Module class

    Returns:
        Signature class if found, None otherwise
    """
    try:
        # Create a temporary instance to inspect
        instance = module_class()

        # Look for predictors - check for various predictor types
        for name, value in instance.__dict__.items():
            # Direct signature attribute (works for Predict and similar)
            if hasattr(value, 'signature') and hasattr(value.signature, 'input_fields'):
                return value.signature

            # ChainOfThought and similar wrap a Predict object in a .predict attribute
            if hasattr(value, 'predict') and hasattr(value.predict, 'signature'):
                predict_obj = value.predict
                if hasattr(predict_obj.signature, 'input_fields'):
                    return predict_obj.signature

    except Exception as e:
        logger.debug(f"Could not extract signature from {module_class.__name__}: {e}")

    return None


def _format_type_name(annotation: Any) -> str:
    """Format a type annotation into a readable string.

    Args:
        annotation: Type annotation object

    Returns:
        Formatted type string (e.g., "str", "list[str]", "int", "dspy.Image")
    """
    if annotation is None:
        return "str"

    # Check if it's a generic type (e.g., List[str], Dict[str, int])
    if hasattr(annotation, '__origin__'):
        # Handle typing generics like list[str]
        type_str = str(annotation)
        type_str = type_str.replace("<class '", "").replace("'>", "")
        type_str = type_str.replace("typing.", "")
        return type_str

    # Handle basic types with __name__
    if hasattr(annotation, '__name__'):
        # Check if this is a dspy type (preserve dspy. prefix)
        if hasattr(annotation, '__module__') and annotation.__module__.startswith('dspy'):
            return f"dspy.{annotation.__name__}"
        return annotation.__name__

    # Fallback to string representation
    type_str = str(annotation)
    type_str = type_str.replace("<class '", "").replace("'>", "")
    type_str = type_str.replace("typing.", "")

    return type_str


def get_signature_fields(signature: Optional[Type[dspy.Signature]]) -> Dict[str, Any]:
    """Extract input and output field information from a signature.

    Args:
        signature: DSPy Signature class

    Returns:
        Dictionary with 'inputs' and 'outputs' field definitions
    """
    if signature is None:
        return {"inputs": {}, "outputs": {}}

    try:
        inputs = {}
        outputs = {}

        # Get input fields
        for field_name, field_info in signature.input_fields.items():
            type_annotation = field_info.annotation if hasattr(field_info, 'annotation') else str
            inputs[field_name] = {
                "type": _format_type_name(type_annotation),
                "description": field_info.json_schema_extra.get("desc", "") if field_info.json_schema_extra else ""
            }

        # Get output fields
        for field_name, field_info in signature.output_fields.items():
            type_annotation = field_info.annotation if hasattr(field_info, 'annotation') else str
            outputs[field_name] = {
                "type": _format_type_name(type_annotation),
                "description": field_info.json_schema_extra.get("desc", "") if field_info.json_schema_extra else ""
            }

        return {"inputs": inputs, "outputs": outputs}

    except Exception as e:
        logger.error(f"Error extracting signature fields: {e}")
        return {"inputs": {}, "outputs": {}}
