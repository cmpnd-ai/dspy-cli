"""Signature definitions for image_description_generator."""

import dspy

class ImageDescriptionGeneratorSignature(dspy.Signature):
    """
    """

    image: dspy.Image = dspy.InputField(desc="")
    image_description: str = dspy.OutputField(desc="")
