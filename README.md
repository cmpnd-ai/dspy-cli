# dspy-cli

[![Documentation](https://img.shields.io/badge/docs-cmpnd--ai.github.io-blue)](https://cmpnd-ai.github.io/dspy-cli/)
[![PyPI](https://img.shields.io/pypi/v/dspy-cli)](https://pypi.org/project/dspy-cli/)

`dspy-cli` is a tool for creating, developing, testing, and deploying [DSPy](https://dspy.ai) programs as HTTP APIs. `dspy-cli` auto-generates endpoints, OpenAPI specs, and Docker configs.

With `dspy-cli`, you get:

- A standard project layout for DSPy programs.
- A [FastAPI](https://fastapi.tiangolo.com) server with auto-generated endpoints.
- [OpenAPI](https://www.openapis.org) specs and an optional [MCP server](https://modelcontextprotocol.io/docs/getting-started/intro).
- [Dockerfile](https://docs.docker.com/reference/dockerfile/) and logging out of the box.

## Quick Start

### Installing & Creating a New Project

To install `dspy-cli`, we recommend using [`uv`](https://github.com/astral-sh/uv).

```bash
uv tool install dspy-cli
```

> You can also use `pip install dspy-cli`, but the example below assumes `uv`.

Running `dspy-cli new` creates a new *project*, which can have many *programs*, each of which performs a specific task.

To illustrate, let's build a project that manages AI-powered functions we might want to call from a [content management system](https://en.wikipedia.org/wiki/Content_management_system) we use to draft, publish, and manage blog posts. We'll call it "cms-kit".

```bash
dspy-cli new cms-kit
```

This command launches an interactive menu that walks you through setting up your first program and connecting to an inference provider. 

Here are our answers:

```bash
Would you like to specify your first program? [Y/n]: Y
What is the name of your first DSPy program? [my_program]: summarizer
```

The first program we'll build will write short summaries of our blog posts. We'll call it `summarizer`. 

Continuing:

```bash
Choose a module type:
  1. Predict - Basic prediction module (default)
  2. ChainOfThought (CoT) - Step-by-step reasoning with chain of thought
  3. ProgramOfThought (PoT) - Generates and executes code for reasoning
  4. ReAct - Reasoning and acting with tools
  5. MultiChainComparison - Compare multiple reasoning paths
  6. Refine - Iterative refinement of outputs
Enter number or name [1]: 1
Enter your signature or type '?' for guided input:
  Examples: 'question -> answer', 'post:str -> tags:list[str], category:str'
Signature [question:str -> answer:str]: blog_post -> summary
```

Here we're using a basic `Predict` [module](https://dspy.ai/learn/programming/modules/) and specifying our [signature](https://dspy.ai/learn/programming/signatures/) as "blog_post -> summary". 

Lastly, we'll connect to the model we want to use:

```bash
Enter your model (LiteLLM format):
  Examples: 'anthropic/claude-sonnet-4-5', 'openai/gpt-4o', 'ollama/llama2'
Model [openai/gpt-5-mini]: openai/gpt-5-mini
Enter your OpenAI API key:
  (This will be stored in .env as OPENAI_API_KEY)
  Press Enter to skip and set it manually later
OPENAI_API_KEY: your_key_here
```

DSPy uses [LiteLLM](https://www.litellm.ai/) to connect to language models, so we're using a [LiteLLM style string](https://docs.litellm.ai/docs/providers) to call GPT-5-mini. Paste in your OpenAI key, and you're good to go. `dspy-cli` will attempt to detect any API key variables in your local environment and will pre-populate this field if a candidate is found.

`dspy-cli` will now create your project structure and define your first program. Let's `cd` into the folder `cms-kit`, activate our environment, and serve our project.

```bash
cd cms-kit
uv sync
source .venv/bin/activate
dspy-cli serve
```

`dspy-cli` will detect the module we've defined, define an endpoint for it, then stand up an HTTP server to call, at `http://localhost:8000` (by default). Visiting that URL will let you submit a form to call your program:

![The summarizer program web UI](docs/assets/images/initial_ui.png)

Or, you can call the API endpoint directly, like so:

```bash
curl -X POST http://0.0.0.0:8000/SummarizerPredict \
  -H "Content-Type: application/json" \
  -d '{
  "blog_post": "[AN EXAMPLE BLOG POST]"
}'
```

Here, `/SummarizerPredict` is the auto-generated route name corresponding to the DSPy module created for our `summarizer` program.

### Creating Another Program

In addition to summarizing blog posts, we can imagine several other LLM-powered functions we could perform in our CMS: tagging, image description writing, drafting social media posts, etc. 

To add a new program to `cms-kit`, we can run the `generate scaffold` command:

```bash
dspy-cli generate scaffold tagger -s "blog_post -> tags:list[str]"
```

We name our program `tagger` and use the `-s` or `--signature` flag to pass in a signature detailing passing in a blog post and getting back a list of tags, which we specify as `list[str]`.

`generate scaffold` creates our program by creating a *signature* and *module* file in `src/cms_kit/signatures` and `src/cms_kit/modules`, respectively.

If we run `dspy-cli serve`, the new module will be discovered and hosted in the web UI and as a new API route.

### Exploring Our Project

Running `dspy-cli new` sets up your project directory. Let's walk through a few key items created:

- `src/cms_kit/signatures`: [Class-based DSPy signatures](https://dspy.ai/learn/programming/signatures/#class-based-dspy-signatures) are created and housed here.
- `src/cms_kit/modules`: [DSPy modules](https://dspy.ai/learn/programming/modules/) are stored here. This folder is where `dspy-cli` discovers available programs when running `serve`. 
- `src/cms_kit/utils`: While you can add arbitrary code to your module and signature files, `utils` is a handy place to stash additional logic and tool definitions. Just create, code, and import from your signatures and modules.
- `logs`: When your programs are called (via the web UI or API calls), usage is logged to a program-specific JSONL file, in the `logs` folder.
- `dspy.config.yaml`: This config file sets a few parameters, but is mainly where inference providers and models are defined, both globally and (if you want) on a per-program basis.

Speaking of model definitions...

### Connecting to Models

In `dspy.config.yaml` you're able to define language models you intend to call. We define models in a YAML format, with similar parameters to the LiteLLM integration [DSPy uses](https://dspy.ai/learn/programming/language_models/).

Here's what our model registry looks like in our `cms-kit` project:

```yaml
models:
  # The default model to use if no per-program override is specified
  default: openai:gpt-5-mini

  # Model registry - define all available models here
  registry:
    openai:gpt-5-mini:
      model: openai/gpt-5-mini
      model_type: chat
      max_tokens: 16000
      temperature: 1.0
      env: OPENAI_API_KEY
```

In the `registry` list we define models, using the LiteLLM convention, like: "openai/gpt-5-mini". 

To add more models, extend the `registry`:

```bash
models:
  default: openai:gpt-5-mini

  registry:
    openai:gpt-5-mini:
      model: openai/gpt-5-mini
      model_type: chat
      max_tokens: 16000
      temperature: 1.0
      env: OPENAI_API_KEY

    anthropic:sonnet-4.5:
      model: anthropic/claude-sonnet-4-5
      env: ANTHROPIC_API_KEY
      max_tokens: 8192
      temperature: 0.7
      model_type: chat

    # A local model hosted with LM Studio
    qwen:qwen-3-4b:
      model: openai/qwen/qwen3-4b
      api_base: http://127.0.0.1:1234/v1
      api_key: placeholder
      max_tokens: 4096
      temperature: 1.0
      model_type: chat
```

The `default` key in the `models` list specifies the default model your programs will call. If you'd like, you can assign different programs to different models, like so:

```yaml
program_models:
   TaggerPredict: qwen:qwen-3-4b
   SummarizerPredict: anthropic:sonnet-4.5
```

The `env` variable for each model refers to an API key defined in an `.env` file located at the root of your project directory.

### Learning More

We've built out a lot of quality of life features in `dspy-cli`, including:

- **Auto-discovery of modules:** Create a module in the `modules` folder and `dspy-cli` will detect the program and infer its parameters.
- **Type validation:** Typed parameters and return values defined in a module's `forward` method are validated during API calls.
- **Hot-reloading:** Tweaking signature or module definitions will cause `dspy-cli` to reload the server, updating the programs.
- **OpenAPI spec generation:** With each run of `serve`, `dspy-cli` creates an OpenAPI JSON definition of your API, which is accessible at `/openapi.json`.
- **MCP tool support:** Pass in `--mcp` while calling `serve` to stand up an MCP server for your program.
- **Docker configuration:** Running `new` creates a Dockerfile, which can be used to quickly stand up your program in Docker.

Check out [the full docs](https://cmpnd-ai.github.io/dspy-cli/) to learn more.

### License

MIT
