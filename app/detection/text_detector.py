"""Text detector: the Detector-interface wrapper around the existing 3-signal
text pipeline.

This does NOT reimplement detection — it reuses the exact same signal functions
and EnsembleDetector that the text /submit path uses, exposing them through the
common Detector interface so the registry can dispatch by content type.
"""

from app.detection.base import Detector
from app.detection.groq_signal import groq_signal
from app.detection.stylometric_signal import stylometric_signal
from app.detection.behavioral_signal import behavioral_signal
from app.detection.ensemble import EnsembleDetector
from app.utils.helpers import predict_attribution


class TextDetector(Detector):
    """Detector for plain text content (Groq + Stylometric + Behavioral)."""

    def __init__(self):
        self.ensemble = EnsembleDetector()

    def get_supported_type(self):
        return 'text'

    def detect(self, content, metadata=None):
        meta = metadata or {}
        creator_id = meta.get('creator_id')
        history = meta.get('submission_history')  # optional prior submissions

        groq_result = groq_signal(content)
        stylometric_result = stylometric_signal(content)
        behavioral_result = behavioral_signal(content, creator_id, submission_history=history)

        result = self.ensemble.detect_three_signal(
            groq_result, stylometric_result, behavioral_result)
        combined = result['combined_score']

        return {
            'combined_score': combined,
            'confidence': result['confidence'],
            'signal_scores': {
                'groq': groq_result['score'],
                'stylometric': stylometric_result['score'],
                'behavioral': behavioral_result['score'],
            },
            'attribution': predict_attribution(combined),
            'explanation': self._explanation(combined, result['confidence']),
        }

    @staticmethod
    def _explanation(score, confidence):
        pct = int(confidence * 100)
        if score >= 0.60:
            return f'Signals lean AI-generated (confidence: {pct}%)'
        if score >= 0.40:
            return f'Mixed signals — uncertain (confidence: {pct}%)'
        return f'Signals lean human-written (confidence: {pct}%)'
