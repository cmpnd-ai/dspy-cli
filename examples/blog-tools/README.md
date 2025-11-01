# Blog Tools

This is an example DSPy project, supporting a hypothetical content management system. This hypothetical CMS lets users draft, publish, and manage blog posts. The "Blog Tools" project is comprised of several DSPy programs, powering features in this CMS system:

1. **Headline Generator:** Given a blog post, generate several candidate headlines.
2. **Image Description Generator:** Given an image, generate a descriptive caption for use as a caption or alt text.
3. **Spell Checker:** Evaluate a blog post for spelling errors and suggest corrections.
4. **Summarizer:** Given a blog post, generate a short summary. Specify a summary length and an optional tone to adopt.
5. **Tagger:** Given a blog post, suggest relevant tags for the post.
6. **Tweet Extractor:** Given a blog post, generate three draft Twitter posts for use when sharing the post. Specify whether or not you'd like emojis in the drafts.

All of the above programs use `Predict` modules, with the exception of **Tagger* which is staged as both `Predict` and `ChainOfThought` modules.

## Setup

1. Create a `.env` file and set your inference provider API keys:

```bash
# Edit .env and add your API keys
OPENAI_API_KEY=your-key-here
```

2. Update model configurations in `dspy.config.yaml` as needed. 
3. Run `dspy-cli serve` to stand up a development server, which can be used as an API. Add the `--ui` flag to `dspy-cli serve` to also stand up a web UI for testing the programs.