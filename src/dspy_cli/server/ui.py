"""Web UI routes and utilities for DSPy programs."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any

from fastapi import HTTPException
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)


def get_recent_logs(logs_dir: Path, program_name: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Read recent log entries for a program.

    Args:
        logs_dir: Directory containing log files
        program_name: Name of the program
        limit: Maximum number of log entries to return

    Returns:
        List of log entry dictionaries (most recent first)
    """
    log_file = logs_dir / f"{program_name}.log"

    if not log_file.exists():
        logger.debug(f"Log file does not exist: {log_file}")
        return []

    logs = []

    try:
        with open(log_file, "r") as f:
            # Read all lines
            lines = f.readlines()

            # Take the last N lines
            recent_lines = lines[-limit:] if len(lines) > limit else lines

            # Parse JSON from each line
            for line in recent_lines:
                line = line.strip()
                if not line:
                    continue

                try:
                    log_entry = json.loads(line)
                    logs.append(log_entry)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse log line: {e}")
                    continue

        # Reverse to show most recent first
        logs.reverse()

    except Exception as e:
        logger.error(f"Error reading log file {log_file}: {e}")
        return []

    return logs


def _detect_module_type(module: Any) -> str:
    """Detect the type of DSPy module (ChainOfThought, Predict, ReAct, etc.).

    Args:
        module: DiscoveredModule object

    Returns:
        Module type string (e.g., 'ChainOfThought', 'Predict', 'ReAct')
    """
    try:
        # Instantiate the module to inspect its structure
        instance = module.instantiate()

        # Check for common predictor types
        if hasattr(instance, 'predictor'):
            predictor = instance.predictor
            predictor_class_name = predictor.__class__.__name__

            # Map predictor class names to types
            if 'ChainOfThought' in predictor_class_name or 'CoT' in predictor_class_name:
                return 'ChainOfThought'
            elif 'ReAct' in predictor_class_name:
                return 'ReAct'
            elif 'ProgramOfThought' in predictor_class_name or 'PoT' in predictor_class_name:
                return 'ProgramOfThought'
            elif 'Refine' in predictor_class_name:
                return 'Refine'
            elif 'MultiChainComparison' in predictor_class_name:
                return 'MultiChainComparison'
            elif 'Predict' in predictor_class_name:
                return 'Predict'

        # Fallback: check module class name for hints
        module_class_name = module.class_obj.__name__
        if 'CoT' in module_class_name or 'ChainOfThought' in module_class_name:
            return 'ChainOfThought'
        elif 'ReAct' in module_class_name:
            return 'ReAct'
        elif 'PoT' in module_class_name or 'ProgramOfThought' in module_class_name:
            return 'ProgramOfThought'
        elif 'Refine' in module_class_name:
            return 'Refine'
        elif 'MultiChain' in module_class_name:
            return 'MultiChainComparison'

        # Default to Predict if unknown
        return 'Predict'

    except Exception as e:
        logger.warning(f"Failed to detect module type for {module.name}: {e}")
        return 'Predict'


def create_ui_routes(app, modules: List[Any], config: Dict, logs_dir: Path):
    """Create UI routes for the FastAPI application.

    Args:
        app: FastAPI application
        modules: List of DiscoveredModule objects
        config: Configuration dictionary
        logs_dir: Directory containing log files
    """
    from dspy_cli.templates.ui.templates import render_index, render_program

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Render the index page with a list of all programs."""
        html = render_index(modules, config)
        return HTMLResponse(content=html)

    @app.get("/ui/{program_name}", response_class=HTMLResponse)
    async def program_page(program_name: str):
        """Render the program detail page."""
        # Find the module
        module = None
        for m in modules:
            if m.name == program_name:
                module = m
                break

        if not module:
            raise HTTPException(status_code=404, detail=f"Program '{program_name}' not found")

        # Detect module type for auto-streaming detection
        module_type = _detect_module_type(module)

        html = render_program(module, config, program_name, module_type)
        return HTMLResponse(content=html)

    @app.get("/api/logs/{program_name}")
    async def get_logs(program_name: str, limit: int = 50):
        """Get recent logs for a program."""
        # Verify program exists
        program_exists = any(m.name == program_name for m in modules)
        if not program_exists:
            raise HTTPException(status_code=404, detail=f"Program '{program_name}' not found")

        logs = get_recent_logs(logs_dir, program_name, limit)

        return {"logs": logs, "count": len(logs)}
