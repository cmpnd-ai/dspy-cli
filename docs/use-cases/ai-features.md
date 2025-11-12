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

**Content Analysis**
- Document summarization that extracts key points and generates structured summaries
- Technical documentation analysis that explains complex concepts
- Code review assistance that identifies patterns and suggests improvements

**Classification and Categorization**
- Email categorization based on content, sender, and context
- Content tagging systems that apply metadata automatically
- Priority scoring for tasks, tickets, or messages

**Contextual Generation**
- Smart reply generation for email and messaging applications
- Form completion based on user context and historical data
- Content recommendations tailored to specific situations

**Data Extraction**
- Invoice processing that extracts vendor, amount, and line items
- Resume parsing that structures candidate information
- Document metadata extraction from unstructured sources

**Browser Extensions**
- Page summarizers that condense content with custom focus
- Context-aware form fillers
- Research assistants that analyze and annotate content

## Integration Patterns

### Browser Extension Integration

Browser extensions call AI feature endpoints from content scripts or background workers:

```javascript
// Content script calling document analysis endpoint
async function analyzeDocument(content) {
  const response = await fetch('https://api.example.com/DocumentAnalyzerPredict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document: content })
  });
  return response.json();
}
```

### CMS Plugin Integration

Content management systems integrate AI features to enhance authoring workflows:

```javascript
// Notion-style plugin calling emoji suggestion endpoint
async function suggestEmoji(postContent) {
  const response = await fetch('https://api.example.com/EmojiPickerPredict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ post_content: postContent })
  });
  const { emoji } = await response.json();
  return emoji;
}
```

### Email Client Integration

Email applications use AI features for categorization and smart replies:

```python
# Email categorizer endpoint
class EmailCategorizer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.classify = dspy.ChainOfThought(
            "email_content, sender -> category, priority"
        )
    
    def forward(self, email_content, sender):
        return self.classify(email_content=email_content, sender=sender)
```

### Background Automation

Background services invoke AI features for asynchronous processing:

```python
# Invoice processor for automated document handling
class InvoiceProcessor(dspy.Module):
    def __init__(self):
        super().__init__()
        self.extract = dspy.ChainOfThought(
            "invoice_data -> vendor, amount, date, line_items"
        )
    
    def forward(self, invoice_data):
        return self.extract(invoice_data=invoice_data)
```

## Implementation with dspy-cli

dspy-cli provides tooling to create and deploy AI features. A typical workflow:

```bash
# Create a new AI feature module
dspy-cli new document-summarizer --program-name Summarizer \
  --signature "document -> summary, key_points"

# Test locally
dspy-cli serve

# Deploy to production
flyctl launch
```

The resulting endpoint accepts structured input and returns structured output:

```bash
curl http://localhost:8000/SummarizerPredict \
  -H "Content-Type: application/json" \
  -d '{"document": "Long document text..."}'

# Returns
{
  "summary": "Brief summary of document",
  "key_points": ["Point 1", "Point 2", "Point 3"]
}
```

## Deployment Requirements

AI features require:

- **HTTP server**: To expose endpoints for application integration
- **Model inference**: Runtime for executing language model operations
- **Authentication**: API keys or tokens for access control
- **Monitoring**: Logging and metrics for production operations
- **Versioning**: Ability to update features without breaking integrations

## Examples

- [Email Categorizer](../../examples/email-categorizer/) - Classifies emails by category and priority
- [Document Summarizer](../../examples/doc-summarizer/) - Generates structured summaries from text
- [Smart Form Filler](../../examples/form-filler/) - Completes forms using contextual understanding

## Learn More

- [Getting Started Guide](../getting-started.md) - Build your first AI feature
- [Deployment Guide](../deployment.md) - Deploy to production environments
- [Commands: serve](../commands/serve.md) - Local development and testing
- [Examples](../../examples/) - Complete integration examples
