"""Example DSPy module with multiple signatures and custom return."""

import dspy
from blog_tools.signatures.image_description_generator import ImageDescriptionGeneratorSignature
from blog_tools.signatures.headline_generator import HeadlineGeneratorSignature

class ImageHeadliner(dspy.Module):
    """Generate headlines for an image by first describing it."""

    def __init__(self):
        super().__init__()
        self.describer = dspy.Predict(ImageDescriptionGeneratorSignature)
        self.headliner = dspy.Predict(HeadlineGeneratorSignature)

    def forward(self, **kwargs):
        description = self.describer(**kwargs).image_description
        headliner = self.headliner(blog_post=description)
        return dspy.Prediction(
            image_description=description,
            headlines=headliner.headline_candidates
        )
