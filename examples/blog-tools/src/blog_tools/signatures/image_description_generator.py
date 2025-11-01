"""Signature definitions for image_description_generator."""

import dspy

class ImageDescriptionGeneratorSignature(dspy.Signature):
    """
    Given an image, generate a descriptive caption for use as alt text.
    """

    image: dspy.Image = dspy.InputField(desc="")
    image_description: str = dspy.OutputField(desc="")
