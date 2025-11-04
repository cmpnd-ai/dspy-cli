"""DSPy module discovery via introspection."""

import ast
import importlib.util
import inspect
import logging
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, get_type_hints

import dspy

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredModule:
    """Information about a discovered DSPy module."""

    name: str  # Module name (e.g., "CategorizerPredict")
    class_obj: Type[dspy.Module]  # The actual class
    module_path: str  # Python module path (e.g., "dspy_project.modules.categorizer_predict")
    signature: Optional[Type[dspy.Signature]] = None  # Signature if discoverable (for backward compatibility)
    signature_string: Optional[str] = None  # Human-readable signature (e.g., "image -> image_description, headlines")
    input_fields: Optional[Dict[str, Any]] = None  # Input field metadata {name: {type, description}}
    output_fields: Optional[Dict[str, Any]] = None  # Output field metadata {name: {type, description}}

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

                # Try to extract signature information and metadata
                signature, signature_string, input_fields, output_fields = _extract_signature(obj)

                discovered.append(
                    DiscoveredModule(
                        name=name,
                        class_obj=obj,
                        module_path=full_module_name,
                        signature=signature,
                        signature_string=signature_string,
                        input_fields=input_fields,
                        output_fields=output_fields
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


def _get_signature_from_type_hints(module_class: Type[dspy.Module]) -> Optional[Type[dspy.Signature]]:
    """Try to extract signature from type hints on the forward() method.

    Args:
        module_class: The DSPy Module class

    Returns:
        Signature class if type hints are complete, None otherwise
    """
    try:
        # Get type hints from forward method
        forward_method = getattr(module_class, 'forward', None)
        if forward_method is None:
            return None

        type_hints = get_type_hints(forward_method)

        # Need both parameters and return type to build a signature
        if 'return' not in type_hints or len(type_hints) <= 1:
            return None

        # Build a signature from the type hints
        # Input fields: all parameters except 'self' and 'return'
        input_fields = {
            name: hint for name, hint in type_hints.items()
            if name not in ('self', 'return')
        }

        # Output fields: extract from return type
        return_type = type_hints['return']

        # If return type is dspy.Prediction, we can't infer output fields
        # (would need to inspect what fields are set at runtime)
        if return_type == dspy.Prediction or (hasattr(return_type, '__origin__') and return_type.__origin__ == dspy.Prediction):
            return None

        # For now, we only support when the return type is explicitly a dict or typed dict
        # Otherwise, fall back to other methods
        return None

    except Exception as e:
        logger.debug(f"Could not extract signature from type hints for {module_class.__name__}: {e}")
        return None


def _build_signature_metadata(
    input_signature: Type[dspy.Signature],
    return_fields: List[str],
    module_instance: dspy.Module
) -> tuple[str, Dict[str, Any], Dict[str, Any]]:
    """Build signature metadata from input signature and return fields.

    Args:
        input_signature: The signature from the first predictor (for inputs)
        return_fields: List of output field names from AST analysis
        module_instance: Instance of the module to inspect all predictors

    Returns:
        Tuple of (signature_string, input_fields_dict, output_fields_dict)
    """
    # Extract input fields from the signature
    input_fields = {}
    input_names = []

    for field_name, field_info in input_signature.input_fields.items():
        input_names.append(field_name)
        type_annotation = field_info.annotation if hasattr(field_info, 'annotation') else str
        input_fields[field_name] = {
            "type": _format_type_name(type_annotation),
            "description": field_info.json_schema_extra.get("desc", "") if field_info.json_schema_extra else ""
        }

    # Collect all signatures from all predictors in the module
    all_signatures = []
    for name, value in module_instance.__dict__.items():
        sig = None
        if hasattr(value, 'signature') and hasattr(value.signature, 'output_fields'):
            sig = value.signature
        elif hasattr(value, 'predict') and hasattr(value.predict, 'signature'):
            sig = value.predict.signature

        if sig:
            all_signatures.append(sig)

    # Extract output fields
    output_fields = {}
    output_names = []

    # Check if return_fields match the first signature's output fields
    signature_output_names = set(input_signature.output_fields.keys())
    if set(return_fields) == signature_output_names:
        # Return fields match signature - use full metadata from signature
        for field_name, field_info in input_signature.output_fields.items():
            output_names.append(field_name)
            type_annotation = field_info.annotation if hasattr(field_info, 'annotation') else str
            output_fields[field_name] = {
                "type": _format_type_name(type_annotation),
                "description": field_info.json_schema_extra.get("desc", "") if field_info.json_schema_extra else ""
            }
    else:
        # Custom return fields - search all signatures for these fields
        output_names = return_fields
        for field_name in return_fields:
            # Try to find this field in any signature's outputs
            found = False
            for sig in all_signatures:
                if field_name in sig.output_fields:
                    field_info = sig.output_fields[field_name]
                    type_annotation = field_info.annotation if hasattr(field_info, 'annotation') else str
                    output_fields[field_name] = {
                        "type": _format_type_name(type_annotation),
                        "description": field_info.json_schema_extra.get("desc", "") if field_info.json_schema_extra else ""
                    }
                    found = True
                    break

            if not found:
                # Field not in any signature - use generic type
                output_fields[field_name] = {
                    "type": "str",
                    "description": ""
                }

    # Build signature string
    input_str = ", ".join(input_names)
    output_str = ", ".join(output_names)
    signature_string = f"{input_str} -> {output_str}"

    return signature_string, input_fields, output_fields


class ForwardMethodAnalyzer(ast.NodeVisitor):
    """AST visitor to analyze a module's forward() method."""

    def __init__(self):
        self.first_predictor_call = None
        self.return_fields = []
        self.predictor_names = []
        self._in_function = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit the forward function definition to analyze in order."""
        if node.name == 'forward':
            self._in_function = True
            # Visit the body statements in order (execution order)
            for stmt in node.body:
                self._visit_statement(stmt)
                # Stop after we find the first predictor
                if self.first_predictor_call is not None:
                    break
            # Now visit all statements again to find return statements
            for stmt in node.body:
                if isinstance(stmt, ast.Return):
                    self._analyze_return(stmt)
            self._in_function = False

    def _visit_statement(self, node: ast.AST) -> None:
        """Visit a statement looking for predictor calls."""
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            # Check the value being assigned
            value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else node.value
            self._check_for_predictor_call(value)
        elif isinstance(node, ast.Expr):
            # Expression statement
            self._check_for_predictor_call(node.value)
        elif isinstance(node, (ast.If, ast.For, ast.While, ast.With)):
            # For control flow, just check the first branch
            if hasattr(node, 'body') and node.body:
                for stmt in node.body:
                    self._visit_statement(stmt)
                    if self.first_predictor_call is not None:
                        return

    def _check_for_predictor_call(self, node: ast.AST) -> None:
        """Check if a node contains a call to self.predictor()."""
        if isinstance(node, ast.Call):
            # Direct call: self.predictor(...)
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                    predictor_name = node.func.attr
                    if predictor_name not in ['__init__', 'forward'] and self.first_predictor_call is None:
                        self.first_predictor_call = predictor_name
                        return
        elif isinstance(node, ast.Attribute):
            # Chained call: self.predictor(...).something
            if isinstance(node.value, ast.Call):
                self._check_for_predictor_call(node.value)

    def _analyze_return(self, node: ast.Return) -> None:
        """Analyze return statements to find output fields."""
        if node.value is None:
            return

        # Check if returning a dspy.Prediction(...) call
        if isinstance(node.value, ast.Call):
            # Check if it's dspy.Prediction or Prediction
            if isinstance(node.value.func, ast.Attribute):
                if (isinstance(node.value.func.value, ast.Name) and
                    node.value.func.value.id == 'dspy' and
                    node.value.func.attr == 'Prediction'):
                    # Extract field names from keyword arguments
                    fields = [kw.arg for kw in node.value.keywords if kw.arg]
                    self.return_fields.extend(fields)
            elif isinstance(node.value.func, ast.Name) and node.value.func.id == 'Prediction':
                # Direct Prediction call
                fields = [kw.arg for kw in node.value.keywords if kw.arg]
                self.return_fields.extend(fields)


def _extract_signature_from_forward(
    module_class: Type[dspy.Module]
) -> Optional[tuple[Type[dspy.Signature], Optional[str], Optional[Dict], Optional[Dict]]]:
    """Extract signature by analyzing the forward() method using AST parsing.

    This function:
    1. Parses the forward() method source code
    2. Finds the first predictor call for input signature
    3. Analyzes return statements for output fields
    4. Builds composite signature metadata when needed

    Args:
        module_class: The DSPy Module class

    Returns:
        Tuple of (signature, signature_string, input_fields, output_fields) or None
        - signature: The signature object (from first predictor)
        - signature_string: Human-readable string (e.g., "image -> image_description, headlines")
        - input_fields: Dict of input field metadata
        - output_fields: Dict of output field metadata
    """
    try:
        # Get the forward method
        forward_method = getattr(module_class, 'forward', None)
        if forward_method is None:
            return None

        # Get source code and dedent it (removes leading whitespace)
        source = inspect.getsource(forward_method)
        source = textwrap.dedent(source)

        # Parse the source code
        tree = ast.parse(source)

        # Analyze the AST
        analyzer = ForwardMethodAnalyzer()
        analyzer.visit(tree)

        # Create a temporary instance to get predictor signatures
        instance = module_class()

        # Get input signature from the first predictor
        input_signature = None
        if analyzer.first_predictor_call:
            predictor = getattr(instance, analyzer.first_predictor_call, None)
            if predictor:
                # Try to get signature
                if hasattr(predictor, 'signature'):
                    input_signature = predictor.signature
                elif hasattr(predictor, 'predict') and hasattr(predictor.predict, 'signature'):
                    input_signature = predictor.predict.signature

        # If no signature found, return None
        if input_signature is None:
            return None

        # Check if we found custom output fields from manual Prediction construction
        if analyzer.return_fields:
            # Build composite signature metadata (pass instance to search all predictors)
            signature_string, input_fields, output_fields = _build_signature_metadata(
                input_signature, analyzer.return_fields, instance
            )
            return (input_signature, signature_string, input_fields, output_fields)

        # Simple case: forward method directly returns predictor call
        # No custom metadata needed, return just the signature
        return (input_signature, None, None, None)

    except Exception as e:
        logger.debug(f"Could not extract signature from forward() for {module_class.__name__}: {e}")
        return None


def _extract_signature(
    module_class: Type[dspy.Module]
) -> tuple[Optional[Type[dspy.Signature]], Optional[str], Optional[Dict], Optional[Dict]]:
    """Try to extract the signature from a DSPy module.

    This function uses multiple strategies in order of preference:
    1. Type hints on forward() method (most explicit)
    2. AST analysis of forward() method (handles multi-signature modules)
    3. Instance attribute inspection (fallback for simple cases)

    Args:
        module_class: The DSPy Module class

    Returns:
        Tuple of (signature, signature_string, input_fields, output_fields)
        - signature: The signature object
        - signature_string: Human-readable string (e.g., "image -> image_description, headlines")
        - input_fields: Dict of input field metadata
        - output_fields: Dict of output field metadata
    """
    # Strategy 1: Try type hints first (most explicit)
    signature = _get_signature_from_type_hints(module_class)
    if signature is not None:
        logger.debug(f"Extracted signature from type hints for {module_class.__name__}")
        return (signature, None, None, None)

    # Strategy 2: Analyze forward() method using AST
    result = _extract_signature_from_forward(module_class)
    if result is not None:
        logger.debug(f"Extracted signature from forward() analysis for {module_class.__name__}")
        return result

    # Strategy 3: Fall back to __dict__ iteration (original approach)
    try:
        # Create a temporary instance to inspect
        instance = module_class()

        # Look for predictors - check for various predictor types
        for name, value in instance.__dict__.items():
            # Direct signature attribute (works for Predict and similar)
            if hasattr(value, 'signature') and hasattr(value.signature, 'input_fields'):
                logger.debug(f"Extracted signature from instance attribute for {module_class.__name__}")
                return (value.signature, None, None, None)

            # ChainOfThought and similar wrap a Predict object in a .predict attribute
            if hasattr(value, 'predict') and hasattr(value.predict, 'signature'):
                predict_obj = value.predict
                if hasattr(predict_obj.signature, 'input_fields'):
                    logger.debug(f"Extracted signature from wrapped predictor for {module_class.__name__}")
                    return (predict_obj.signature, None, None, None)

    except Exception as e:
        logger.debug(f"Could not extract signature from {module_class.__name__}: {e}")

    return (None, None, None, None)


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


def get_signature_fields(signature_or_module) -> Dict[str, Any]:
    """Extract input and output field information from a signature or DiscoveredModule.

    Args:
        signature_or_module: Either a DSPy Signature class or a DiscoveredModule

    Returns:
        Dictionary with 'inputs' and 'outputs' field definitions
    """
    # Check if it's a DiscoveredModule with metadata
    if isinstance(signature_or_module, DiscoveredModule):
        module = signature_or_module
        # Use module's field metadata if available
        if module.input_fields is not None and module.output_fields is not None:
            return {"inputs": module.input_fields, "outputs": module.output_fields}
        # Fall back to extracting from signature
        signature = module.signature
    else:
        signature = signature_or_module

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
