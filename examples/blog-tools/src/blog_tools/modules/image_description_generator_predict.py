import dspy
from blog_tools.signatures.image_description_generator import ImageDescriptionGeneratorSignature


class ImageDescriptionGeneratorPredict(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predictor = dspy.Predict(ImageDescriptionGeneratorSignature)

    def forward(self, image: dspy.Image) -> dspy.Prediction:
        return self.predictor(image=image)
