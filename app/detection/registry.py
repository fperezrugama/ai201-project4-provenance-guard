"""Registry of content detectors, keyed by content type."""

from app.detection.text_detector import TextDetector
from app.detection.image_description_detector import ImageDescriptionDetector


class DetectorRegistry:
    """Maps a content_type string to the detector that handles it."""

    def __init__(self):
        self.detectors = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register(TextDetector())
        self.register(ImageDescriptionDetector())

    def register(self, detector):
        self.detectors[detector.get_supported_type()] = detector

    def get_detector(self, content_type):
        return self.detectors.get(content_type)

    def get_supported_types(self):
        return list(self.detectors.keys())
