import dspy
from blog_tools.signatures.image_description_generator import ImageDescriptionGeneratorSignature
from blog_tools.signatures.headline_generator import HeadlineGeneratorSignature

class ImageHeadlineGeneratorPredict(dspy.Module):
    def __init__(self):
        super().__init__()
        self.image_describer = dspy.Predict(ImageDescriptionGeneratorSignature)
        self.headline_generator = dspy.Predict(HeadlineGeneratorSignature)

    def forward(self, image: dspy.Image) -> dspy.Prediction:
        description = self.image_describer(image=image).image_description
        return self.headline_generator(blog_post=description)
