# Concept: AI Features

## Definition

AI features are application-embedded functionality backed by language models. They are exposed as HTTP endpoints and integrated into existing applications, providing task-specific capabilities such as document summarization, content classification, or contextual text generation.

Unlike conversational interfaces or autonomous agents, AI features are discrete services that applications invoke to complete specific operations within their workflow.

## Characteristics

AI features have several defining properties:

- **Task-specific**: Designed to solve a particular problem rather than handle general-purpose queries
- **Endpoint-based**: Exposed as HTTP APIs that return structured responses
- **Application-embedded**: Integrated into existing software (browser extensions, plugins, background services)
- **Deterministic interfaces**: Accept defined inputs and return structured outputs
- **Stateless operation**: Each request is independent, without conversational context

## Comparison with Other Patterns

| Pattern | Execution Model | Interface Type | Primary Use Case |
|---------|----------------|----------------|------------------|
| **AI Features** | Application calls endpoint for specific task | HTTP API with structured I/O | Embedded functionality in existing apps |
| **Chat Interfaces** | User interacts with conversational agent | Natural language dialogue | Open-ended assistance and exploration |
| **Batch Processing** | Offline processing of datasets | Pipeline/job-based | Large-scale data transformation |
| **Agents** | LLM controls execution flow and tool use | Autonomous decision-making | Multi-step tasks requiring planning |

AI features differ from chat interfaces in that they provide specific functionality rather than conversational interaction. Unlike agents, the application controls execution flow and calls the feature as needed. Unlike batch processing, AI features operate on individual requests in real-time.

## Common Use Cases

### Content Analysis

- Document summarization that extracts key points and generates structured summaries
- Technical documentation analysis that explains complex concepts
- Code review assistance that identifies patterns and suggests improvements

### Classification and Categorization

- Email categorization based on content, sender, and context
- Content tagging systems that apply metadata automatically
- Priority scoring for tasks, tickets, or messages

### Contextual Generation

- Smart reply generation for email and messaging applications
- Form completion based on user context and historical data
- Content recommendations tailored to specific situations

### Data Extraction

- Invoice processing that extracts vendor, amount, and line items
- Resume parsing that structures candidate information
- Document metadata extraction from unstructured sources

### Browser Extensions

- Page summarizers that condense content with custom focus
- Context-aware form fillers
- Research assistants that analyze and annotate content

## Integration Patterns

AI features are invoked via HTTP POST requests with JSON payloads. Common integration points:

- **Browser extensions**: Content scripts call endpoints for page analysis
- **CMS plugins**: Authoring tools invoke generation endpoints
- **Email clients**: Background workers call categorization endpoints
- **Background automation**: Async workers process documents via API

See [Examples](https://github.com/cmpnd-ai/dspy-cli/tree/main/examples) for complete integration code.

## Implementation with dspy-cli

Create and launch AI features:

```bash
dspy-cli new document-summarizer -s "document -> summary, key_points"
dspy-cli serve
```

See [Getting Started](../getting-started.md) for complete workflow.
