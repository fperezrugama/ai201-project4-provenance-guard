"""Ensemble aggregator: combine independent detection signals into one result.

Supports BOTH the original two-signal ensemble (Groq + Stylometric, kept for
backward compatibility) and the new three-signal ensemble that adds the
behavioral signal.
"""

import statistics

# Three-signal weights (Stretch Feature 1). Groq is weighted highest because it
# captures semantic meaning; stylometric is structural; behavioral is the
# newest and least-proven signal, so it carries the least weight.
GROQ_WEIGHT_3 = 0.40
STYLOMETRIC_WEIGHT_3 = 0.35
BEHAVIORAL_WEIGHT_3 = 0.25


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


class EnsembleDetector:
    """Combine signal results into a final score plus a confidence value."""

    def detect_three_signal(self, groq_result, stylometric_result, behavioral_result):
        """Combine three signals into one score + agreement-based confidence.

            combined   = 0.40*groq + 0.35*stylometric + 0.25*behavioral
            confidence = 1 - stdev([groq, stylometric, behavioral]) * 1.5

        Confidence is driven by agreement: when the three signals cluster
        (low standard deviation) confidence is high; when they disagree
        (high standard deviation) confidence drops. Uses the sample standard
        deviation (n-1), matching the worked examples in the spec.
        """
        groq = groq_result['score']
        stylometric = stylometric_result['score']
        behavioral = behavioral_result['score']

        combined = (groq * GROQ_WEIGHT_3
                    + stylometric * STYLOMETRIC_WEIGHT_3
                    + behavioral * BEHAVIORAL_WEIGHT_3)

        std_dev = statistics.stdev([groq, stylometric, behavioral])
        confidence = _clamp(1 - std_dev * 1.5)

        return {
            'combined_score': round(combined, 4),
            'confidence': round(confidence, 4),
            'std_dev': round(std_dev, 4),
            'signals': {
                'groq': groq,
                'stylometric': stylometric,
                'behavioral': behavioral,
            },
        }

    def detect_two_signal(self, groq_result, stylometric_result):
        """Backward-compatible two-signal ensemble (Groq 60% / Stylometric 40%).

        Confidence uses the original distance-from-0.5 definition. Retained so
        the two-signal mode remains fully available alongside the three-signal
        mode.
        """
        from app.utils.helpers import combine_scores, compute_confidence
        groq = groq_result['score']
        stylometric = stylometric_result['score']
        combined = combine_scores(groq, stylometric)
        return {
            'combined_score': round(combined, 4),
            'confidence': round(compute_confidence(combined), 4),
            'signals': {'groq': groq, 'stylometric': stylometric},
        }
