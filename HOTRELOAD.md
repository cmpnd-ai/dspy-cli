# Hot Reload Feature

The `dspy-cli serve` command now supports automatic server reloading when files change during development.

## Usage

### Enable Hot Reload (Default)
```bash
dspy-cli serve              # Reload enabled by default
dspy-cli serve --reload     # Explicitly enable reload
```

### Disable Hot Reload
```bash
dspy-cli serve --no-reload
```

## What Gets Watched

When hot reload is enabled, the server watches for changes in:

1. **Python modules** (`*.py`) in `src/`
   - DSPy module implementations
   - Signature definitions
   - Utilities and metrics

2. **Configuration files**
   - `dspy.config.yaml` - Model configuration and program overrides
   - `.env` - API keys and environment variables

## How It Works

1. Uvicorn's built-in file watcher monitors the specified directories
2. When a change is detected, uvicorn automatically restarts the server process
3. The entire application is reloaded with fresh imports
4. Your changes are reflected immediately without manual restart

## Example Workflow

```bash
# Terminal 1: Start the server with hot reload
cd my-dspy-project
dspy-cli serve --ui

# Server starts and displays:
# Hot reload: ENABLED
#   Watching for changes in:
#     • /path/to/src/my_project/modules
#     • /path/to/dspy.config.yaml
#     • /path/to/.env
```

```python
# Terminal 2: Edit a module
vim src/my_project/modules/categorizer_predict.py

# Make your changes and save...
# The server automatically restarts in Terminal 1
```

## Performance Notes

- **Reload latency**: ~1-2 seconds for full process restart
- **Production use**: Disable reload in production with `--no-reload`
- **Large projects**: Reload time may increase with project size

## Technical Details

The implementation uses uvicorn's `--reload` feature with:
- `reload_dirs`: Watches `src/` and project root
- `reload_includes`: Filters for `*.py`, `*.yaml`, `.env` files
- `factory=True`: Recreates app from scratch on each reload

See `src/dspy_cli/server/runner.py:create_app_instance()` for implementation details.
