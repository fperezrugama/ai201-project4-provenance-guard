"""Detector for image *descriptions* — a lightweight, text-based second content
type. Uses deterministic heuristics only (no LLM, no image processing).

Score convention: 0.0 = human-like, 1.0 = AI-like.
"""

import re
import statistics

from app.detection.base import Detector


class ImageDescriptionDetector(Detector):
    """Heuristic detector for image descriptions.

    Looks at template-like phrasing, structural complexity, metadata
    specificity, and emotional language.
    """

    def __init__(self):
        # Phrasings common in AI-generated descriptions.
        self.ai_templates = [
            r'image shows', r'picture of', r'photo features', r'depicts a',
            r'scene includes', r'captured in', r'this image', r'in this picture',
        ]
        # Emotive words common in human descriptions.
        self.human_indicators = [
            r'i think', r'i feel', r'beautiful', r'stunning', r'amazing',
            r'wonderful', r'lovely', r'gorgeous', r'incredible',
        ]

    def get_supported_type(self):
        return 'image_description'

    def detect(self, content, metadata=None):
        if not content or len(content.strip()) < 10:
            return {
                'combined_score': 0.5,
                'confidence': 0.2,
                'signal_scores': {},
                'attribution': 'uncertain',
                'explanation': 'Description too short for meaningful analysis',
            }

        template_score = self._analyze_templates(content)
        complexity_score = self._analyze_complexity(content)
        metadata_score = self._analyze_metadata(metadata) if metadata else 0.5
        emotion_score = self._analyze_emotion(content)

        signal_scores = {
            'template_detection': round(template_score, 4),
            'complexity': round(complexity_score, 4),
            'metadata_consistency': round(metadata_score, 4),
            'emotion': round(emotion_score, 4),
        }

        # Weights: template most important, emotion least.
        combined_score = (
            template_score * 0.40
            + complexity_score * 0.30
            + metadata_score * 0.20
            + emotion_score * 0.10
        )

        # Agreement-based confidence (same idea as the text ensemble).
        scores = [template_score, complexity_score, metadata_score, emotion_score]
        std_dev = statistics.stdev(scores) if len(scores) > 1 else 0.3
        confidence = max(0.0, min(1.0, 1 - std_dev * 1.5))

        # Attribution standardized to 3 values (matches the text pipeline).
        if combined_score >= 0.65:
            attribution = 'ai_generated'
            explanation = 'Description shows strong AI-generated patterns'
        elif combined_score >= 0.40:
            attribution = 'uncertain'
            explanation = 'Mixed patterns detected'
        else:
            attribution = 'human_written'
            explanation = 'Description shows human-like writing patterns'

        return {
            'combined_score': round(combined_score, 4),
            'confidence': round(confidence, 4),
            'signal_scores': signal_scores,
            'attribution': attribution,
            'explanation': explanation,
        }

    def _analyze_templates(self, text):
        """Template-like AI phrasing -> higher (AI-like) score."""
        text_lower = text.lower()
        matches = sum(1 for t in self.ai_templates if re.search(t, text_lower))
        if matches >= 3:
            return 0.9
        if matches == 2:
            return 0.7
        if matches == 1:
            return 0.5
        return 0.2  # no templates -> more human-like

    def _analyze_complexity(self, text):
        """Sentence-length variance + vocabulary diversity -> AI-likeness."""
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        if len(sentences) < 2:
            return 0.5

        lengths = [len(s.split()) for s in sentences]
        avg_len = sum(lengths) / len(lengths)
        variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
        # Low variance (uniform) -> AI-like (high score). Normalized to ~25.
        variance_score = 1 - min(1, variance / 25)

        words = re.findall(r'\b\w+\b', text.lower())
        if len(words) < 10:
            ttr_score = 0.5  # too few words to judge diversity (neutral)
        else:
            ttr = len(set(words)) / len(words)
            # Higher TTR -> more human-like -> lower AI score.
            ttr_score = 1 - min(1, ttr / 0.5)

        return variance_score * 0.6 + ttr_score * 0.4

    def _analyze_metadata(self, metadata):
        """Specific metadata -> more human-like; generic -> more AI-like."""
        score = 0.5
        if metadata.get('width') and metadata.get('height'):
            score -= 0.1
        if metadata.get('format') and metadata.get('format') != 'unknown':
            score -= 0.1
        if metadata.get('objects'):
            score -= 0.1
        if metadata.get('format') == 'unknown':
            score += 0.15
        return max(0.0, min(1.0, score))

    def _analyze_emotion(self, text):
        """More emotive language -> more human-like (lower AI score)."""
        text_lower = text.lower()
        matches = sum(1 for w in self.human_indicators if re.search(w, text_lower))
        if matches >= 3:
            return 0.2
        if matches == 2:
            return 0.4
        if matches == 1:
            return 0.6
        return 0.8
