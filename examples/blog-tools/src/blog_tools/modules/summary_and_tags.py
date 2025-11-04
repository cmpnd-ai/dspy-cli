"""Example DSPy module with multiple signatures and custom return."""

import dspy
from blog_tools.signatures.summarizer import SummarizerSignature
from blog_tools.signatures.tagger import TaggerSignature

class SummaryAndTags(dspy.Module):
    """Generate both a summary and tags for a blog post."""

    def __init__(self):
        super().__init__()
        self.summarizer = dspy.Predict(SummarizerSignature)
        self.tagger = dspy.Predict(TaggerSignature)

    def forward(self, **kwargs):
        summary = self.summarizer(**kwargs)
        tags = self.tagger(blog_post=summary.summary)
        return dspy.Prediction(summary=summary.summary, tags=tags.tags)
