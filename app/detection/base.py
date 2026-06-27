"""Common interface for all content detectors (multi-modal support)."""

from abc import ABC, abstractmethod


class Detector(ABC):
    """Base interface that every content detector implements."""

    @abstractmethod
    def detect(self, content, metadata=None):
        """Analyze content and return detection results.

        Args:
            content: the content to analyze (text, description, ...).
            metadata: optional context (content_type, creator_id, ...).

        Returns:
            dict: {
                'combined_score': float (0-1),
                'confidence': float (0-1),
                'signal_scores': dict,
                'attribution': str,
                'explanation': str
            }
        """

    @abstractmethod
    def get_supported_type(self):
        """Return the content type string this detector handles."""
