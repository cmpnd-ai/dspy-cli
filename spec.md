# dspy-cli Spec

This is the spec for the `dspy-cli` tool. The tool will assist with the creation of DSPy projects and programs and allow users to `serve` them as an web API, for local testing or serving within a VM or container.

This tool takes heavy inspiration from the Ruby on Rails CLI tool. When in doubt, default to a similar UX as that tool, unless otherwise specified.

## Requirements

- Able to ship as a single Python package, with a clear `src/` layout.
- Supports multiple DSPy programs living in one project, with composition possible between them. Modules can import and use other modules.
- Signatures are defined in a different file than modules, allowing the same signature to be loaded by multiple different modules.
- In a DSPy project directory signatures, modules, optimizers, and metrics will be put in dedicated folders.
- Config is set up via `dspy.config.yaml` in the project root. Secrets are in a `.env` file in the project root.
- When a project directory is created, the CLI will create the `.env` file but will also add it to a `.gitignore`.
- Provide a CLI and HTTP service for running programs locally and in production.
- Keep configuration out of code where reasonable.
- Avoid decorators for discovery. Use programmatic discovery (inspection).
- Use the 'click' library for argument handling and the CLI interface.
- Use the FastAPI library to serve an API exposing the DSPy programs. Contain the code required to serve the FastAPI code in the `dspy-cli` library, do not rely on users providing their own API code in their DSPy porjects.

## Commands

- `new [project-name]`: Running `new` creates a folder with the 'project-name'. 
    - A boilerplate directory structure will be set up according to the definition below. 
    - 'project-name' will serve as the project name and the initial name of the program that will be set up in the new directory (see below), though with the '-' converted to an '_', if it exists.
    - Users will have the option to pass in a different name for the initial program with the `--program-name` or `-p` flag. Which could be called like this: `dspy-clip new my-dspy-project -p categorizer`.
    - `new` will also run `git init` in the new directory.
- `serve --port 8000 --host 0.0.0.0`: This identifies the DSPy programs in the `module` folder and serves them up as routes in a web API, while printing logs to STDOUT.
    - The CLI tool first checks that it is being run inside a directory structure matching the conventions of one created by the `new` command. If not, it returns an informative error.
    - The user can change the port or host values, or omit them entirely and rely on the defaults.
    - The tool identifies the modules it will serve by checking the `src/project_name/modules/` directory and detecting the models contained within. Each module file will be evaluated and loaded.
    - Loaded modules will be hosted behind an endpoint with a route matching their module name. A POST request, with parameters matching their program input definitions, will be served, with the available endpoints printed to STDOUT.
    - Calls to the endpoints should be logged in the `logs` directory, with each module having a separate log file that logs are appended to.

## Directory Structure

The boiler-plate directory structure created by the `new` command will be as follows.

If the user runs:

```
$ dspy-cli new categorizer
```

The following directory and directory structure will be created:

```
categorizer/
├── pyproject.toml
├── dspy.config.yaml           # model registry, routing, discovery overrides
├── .env                       # API keys and secrets (copied to .env)
├── README.md
├── src/
│   └── dspy_project/          # importable package
│       ├── __init__.py
│       ├── modules/           # DSPy program implementations
│       │   ├── __init__.py
│       │   ├── categorizer_predict.py
│       ├── signatures/        # reusable signatures
│       │   ├── __init__.py
│       │   └── categorizer.py
│       ├── optimizers/        # e.g., GEPA, MIPROv2, etc.
│       │   ├── __init__.py
│       │   └── categorizer_gepa.py
│       ├── metrics/           # eval metrics for programs
│       │   ├── __init__.py
│       │   └── categorizer.py
│       └── utils/               # shared helpers (I/O, prompts, utils)
│           └── __init__.py
├── data/
├── logs/
└── tests/
    └── test_modules.py
```

Here are a few notes regarding this design:

- ``** layout** prevents path-import footguns and matches modern Python/uv norms.
- Keep **program code** in `modules/`. Composition across modules is encouraged via normal imports.
- Use **snake\_case** files; public names can be **PascalCase** classes (e.g., `CategorizerCoT(dspy.Module)`).

## Configuration

A single file at the repo root governs language model definitions (using DSPy's LM instantiation conventions). Here is an example:

```yaml
# dspy.config.yaml
models:
  default: openai:gpt-5-mini
  registry:
    openai:gpt-4o-mini:
      model: openai/gpt-5-mini
      env: OPENAI_API_KEY
      max_tokens: 16000
      temperature: 1.0
      model_type: responses
    anthropic:sonnet-3.5:
      provider: anthropic/claude-3-5-sonnet
      env: ANTHROPIC_API_KEY
      model_type: chat

# Optional: per-program model overrides (by program/class name)
program_models:
  CategorizerCoT: anthropic:sonnet-3.5
```

We then use these configurations to set up the LM using DSPy. Here is how the default model would be set up:

```python
# Configure DSPy to use the Responses API for your language model
dspy.settings.configure(
    lm=dspy.LM(
        "openai/gpt-5-mini",
        model_type="responses",
        temperature=1.0,
        max_tokens=16000,
        api_key='OPENAI_API_KEY_FROM_ENV'
    ),
)
```

The api_key would be loaded from .env.

This would set up the model when running `serve`

## Program Discovery

Discovery relies on import-time introspection against `dspy.Module`. It works like this:

1. **Enumerate modules** in the configured package (default `[project_name].modules`) using `pkgutil.iter_modules` or `importlib.resources`.
2. **Import** each candidate module.
3. **Introspect** with `inspect.getmembers(mod, inspect.isclass)`:
   - Accept class `C` if:
     - `issubclass(C, dspy.Module)` **and** `C is not dspy.Module`.
     - `C.__module__ == mod.__name__` (defined in that file, not a re-export), unless `require_public`/`only_named` says otherwise.
     - If `require_public: true`, skip classes with names starting `_`.
4. **Instantiate** lazily: create callables (endpoints/CLI targets) that build the class with defaults or with parsed params.
5. **Register** each accepted class under a program name (default: class name; can be overridden by `routes` or CLI flags).

## Serving via the CLI Tool

Again, no server code will be created in the user project. The CLI package (installed globally or in the local env) owns the HTTP server implimentation.

On `serve` startup, the CLI:

  1. Loads `dspy.config.yaml`, resolves the model registry, and reads keys from environment variables.
  2. **Discovers** programs in your package (default: `dspy_project.modules`).
  3. Mounts endpoints per discovered program and optional route overrides from config.
  4. Prints the current routing to the STDOUT
  5. Prints log files from the server to STDOUT

Route endpoints will be:

- `GET  /programs` — list discovered programs and their expected inputs/outputs (optional schema derivation from `signatures/`).
- `POST /{program}/run` — run once with JSON payload mapped to signature fields.
- `POST /{program}/optimize` — optional; runs configured optimizer for that program.