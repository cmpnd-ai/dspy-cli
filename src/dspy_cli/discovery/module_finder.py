"""DSPy module discovery via introspection."""

import importlib.util
import inspect
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, get_type_hints

import dspy
from pydantic import BaseModel

if TYPE_CHECKING:
    from dspy_cli.gateway import Gateway

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredModule:
    """Information about a discovered DSPy module."""

    name: str  # Module name (e.g., "CategorizerPredict")
    class_obj: Type[dspy.Module]  # The actual class
    module_path: str  # Python module path (e.g., "dspy_project.modules.categorizer_predict")
    signature: Optional[Type[dspy.Signature]] = None  # Signature if discoverable (deprecated, use forward types)
    forward_input_fields: Optional[Dict[str, Any]] = None  # Input field types from forward() method
    forward_output_fields: Optional[Dict[str, Any]] = None  # Output field types from forward() method
    is_forward_typed: bool = False  # True if forward() has proper type annotations
    gateway_class: Optional[Type["Gateway"]] = None  # Gateway class if specified on module

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

                # Try to extract forward method type information
                forward_info = _extract_forward_types(obj)

                # Also try to extract signature (for backward compatibility and fallback)
                signature = _extract_signature(obj)

                # Extract gateway class if specified
                gateway_class = _extract_gateway_class(obj)

                discovered.append(
                    DiscoveredModule(
                        name=name,
                        class_obj=obj,
                        module_path=full_module_name,
                        signature=signature,
                        forward_input_fields=forward_info.get("inputs"),
                        forward_output_fields=forward_info.get("outputs"),
                        is_forward_typed=forward_info.get("is_typed", False),
                        gateway_class=gateway_class,
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


def _extract_gateway_class(module_class: Type[dspy.Module]) -> Optional[Type["Gateway"]]:
    """Extract the gateway class from a module if specified.
    
    Checks for a `gateway` class attribute on the module that should be
    a Gateway subclass.
    
    Args:
        module_class: The DSPy Module class
        
    Returns:
        Gateway subclass if specified and valid, None otherwise
    """
    from dspy_cli.gateway import Gateway
    
    gateway_attr = getattr(module_class, 'gateway', None)
    
    if gateway_attr is None:
        return None
    
    try:
        if isinstance(gateway_attr, type) and issubclass(gateway_attr, Gateway):
            logger.debug(f"Found gateway {gateway_attr.__name__} on {module_class.__name__}")
            return gateway_attr
    except TypeError:
        pass
    
    logger.warning(
        f"Module {module_class.__name__} has 'gateway' attribute but it's not a Gateway subclass: "
        f"{type(gateway_attr)}. Ignoring."
    )
    return None


def _extract_forward_types(module_class: Type[dspy.Module]) -> Dict[str, Any]:
    """Extract type information from a module's forward() method.

    This function analyzes the forward() method's type annotations to determine:
    1. Input parameters and their types
    2. Return type and its structure
    3. Whether the forward method is properly typed

    Args:
        module_class: The DSPy Module class

    Returns:
        Dictionary with:
        - inputs: Dict[str, Dict] - input field names and their type info
        - outputs: Dict[str, Dict] - output field names and their type info
        - is_typed: bool - whether the forward method has complete type annotations
    """
    try:
        # Get the forward method
        forward_method = getattr(module_class, 'forward', None) or getattr(module_class, 'aforward', None)
        if forward_method is None:
            logger.debug(f"No forward method found for {module_class.__name__}")
            return {"inputs": None, "outputs": None, "is_typed": False}

        # Get type hints from the forward method
        try:
            type_hints = get_type_hints(forward_method)
        except Exception as e:
            logger.debug(f"Could not get type hints for {module_class.__name__}.forward(): {e}")
            return {"inputs": None, "outputs": None, "is_typed": False}

        # Check if return type is present
        if 'return' not in type_hints:
            logger.debug(f"No return type annotation on {module_class.__name__}.forward()")
            return {"inputs": None, "outputs": None, "is_typed": False}

        # Extract input parameters (everything except 'self' and 'return')
        input_params = {}
        for param_name, param_type in type_hints.items():
            if param_name in ('self', 'return'):
                continue
            input_params[param_name] = {
                "type": _format_type_name(param_type),
                "annotation": param_type
            }

        # Check for **kwargs which we don't support
        sig = inspect.signature(forward_method)
        for param in sig.parameters.values():
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                logger.debug(f"{module_class.__name__}.forward() uses **kwargs - not supported")
                return {"inputs": None, "outputs": None, "is_typed": False}

        # Extract signature (if available) to help with dspy.Prediction return types
        signature = _extract_signature(module_class)

        # Extract return type
        return_type = type_hints['return']
        output_params = _parse_return_type(return_type, signature)

        # Check if we have at least one input and a valid return type
        # output_params can be empty dict (for dspy.Prediction) which is valid
        if not input_params or output_params is None:
            logger.debug(f"{module_class.__name__}.forward() missing input or output types")
            return {"inputs": None, "outputs": None, "is_typed": False}

        return {
            "inputs": input_params,
            "outputs": output_params,
            "is_typed": True
        }

    except Exception as e:
        logger.debug(f"Error extracting forward types from {module_class.__name__}: {e}")
        return {"inputs": None, "outputs": None, "is_typed": False}


def _parse_return_type(return_type: Any, signature: Optional[Type[dspy.Signature]] = None) -> Optional[Dict[str, Any]]:
    """Parse a return type annotation to extract output fields.

    Supports:
    - dspy.Prediction (accepted but returns empty dict - no field validation)
    - Dict[str, Any] or dict (no field info, returns None)
    - Pydantic BaseModel subclasses (extracts field names and types)
    - TypedDict subclasses (extracts field names and types)
    - Custom dataclass/NamedTuple (extracts field names and types)

    Args:
        return_type: The return type annotation from forward()
        signature: Optional signature (not used anymore, kept for compatibility)

    Returns:
        Dictionary mapping field names to their type info, empty dict for dspy.Prediction, or None if invalid
    """
    # Check for dspy.Prediction - accept it but don't validate fields
    if return_type == dspy.Prediction or (hasattr(return_type, '__origin__') and return_type.__origin__ == dspy.Prediction):
        logger.debug("Return type is dspy.Prediction - no output field validation")
        # Return empty dict to indicate "valid but no field validation"
        return {}

    # Check for dict types - we can't infer fields from these either
    if return_type is dict or return_type is Dict:
        logger.debug("Return type is dict - cannot infer fields")
        return None

    if hasattr(return_type, '__origin__') and return_type.__origin__ in (dict, Dict):
        logger.debug("Return type is Dict[...] - cannot infer fields")
        return None

    # Check for Pydantic BaseModel
    try:
        if inspect.isclass(return_type) and issubclass(return_type, BaseModel):
            output_fields = {}
            for field_name, field_info in return_type.model_fields.items():
                output_fields[field_name] = {
                    "type": _format_type_name(field_info.annotation),
                    "annotation": field_info.annotation
                }
            logger.debug(f"Extracted {len(output_fields)} fields from Pydantic model")
            logger.debug(f"Output fields: {output_fields}")
            return output_fields
    except (TypeError, AttributeError):
        pass

    # Try TypedDict or dataclass
    if hasattr(return_type, '__annotations__'):
        annotations = getattr(return_type, '__annotations__', {})
        if annotations:
            output_fields = {}
            for field_name, field_type in annotations.items():
                output_fields[field_name] = {
                    "type": _format_type_name(field_type),
                    "annotation": field_type
                }
            return output_fields

    # Simple types (str, int, list[str], etc.)
    # If we have a signature, use its field name; otherwise use "result"
    if signature and hasattr(signature, 'output_fields'):
        output_field_items = list(signature.output_fields.items())
        if len(output_field_items) == 1:
            # Use the signature's field name and the forward's return type
            field_name, _ = output_field_items[0]
            output_fields = {
                field_name: {
                    "type": _format_type_name(return_type),
                    "annotation": return_type
                }
            }
            logger.debug(f"Using simple return type with signature field name '{field_name}': {return_type}")
            return output_fields

    # No signature or multiple output fields - use default "result" name
    output_fields = {
        "result": {
            "type": _format_type_name(return_type),
            "annotation": return_type
        }
    }
    logger.debug(f"Using simple return type with 'result' field: {return_type}")
    return output_fields


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


def get_module_fields(module: DiscoveredModule) -> Dict[str, Any]:
    """Extract input and output field information from a discovered module.

    This function only uses forward() type annotations. Signatures are no longer used.

    Args:
        module: DiscoveredModule instance

    Returns:
        Dictionary with 'inputs' and 'outputs' field definitions
    """
    # Only use forward types - signatures are deprecated for API/UI generation
    if module.is_forward_typed and module.forward_input_fields is not None:
        # Convert forward types to the format expected by callers
        inputs = {}
        outputs = {}

        for field_name, field_info in module.forward_input_fields.items():
            inputs[field_name] = {
                "type": field_info.get("type", "str"),
                "description": ""  # No description from type hints
            }

        # forward_output_fields can be empty dict for dspy.Prediction (no validation)
        if module.forward_output_fields:
            for field_name, field_info in module.forward_output_fields.items():
                outputs[field_name] = {
                    "type": field_info.get("type", "str"),
                    "description": ""  # No description from type hints
                }

        return {"inputs": inputs, "outputs": outputs}

    # No typed forward method - return empty fields
    return {"inputs": {}, "outputs": {}}


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
