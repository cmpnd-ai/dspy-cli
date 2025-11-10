# dspy-cli Test Suite

## Test Coverage

This test suite ensures the CLI commands work correctly and continue to work.

### Serve Integration Tests (`test_serve_integration.py`)

Real server tests without making LLM calls.

Done by creating a module that doesn't have any LLM calls in it.

## Test Strategy

Tests avoid LLM dependencies by using a dummy `Echo` module that returns deterministic results without calling LLMs

Otherwise they use:

- Using FastAPI's `TestClient` to make real HTTP requests to test endpoints
- Stubbing `uvicorn.run` only for runner orchestration tests
- Everything else is real - actual server, routes, discovery, OpenAPI generation
- Use Click's `CliRunner` for CLI testing
- Use pytest fixtures for temp projects and configs

## Running Tests

```bash
# Run all tests
uv run pytest
```

## Maintenance

When adding new CLI commands:
1. Add smoke test to `test_commands_smoke.py` 
2. Keep tests simple - something is better than nothing
3. Focus on happy paths and basic validation

When modifying serve behavior:
1. Add integration test to `test_serve_integration.py`
2. Use the `test_config` and `temp_project` fixtures
3. Stub external dependencies (uvicorn, dspy.LM, etc.)
