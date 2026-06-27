"""Shared helpers: score-to-label mapping and timestamp formatting."""

from datetime import datetime, timezone

# Score thresholds (high -> low) mapped to (attribution, transparency label).
# A 0-1 score is "AI-likeness": 0 = human, 1 = AI. The first threshold the
# score meets, scanning top to bottom, wins.
SCORE_LABELS = [
    (0.80, "ai_generated", "⚠️ AI-GENERATED CONTENT DETECTED"),
    (0.60, "likely_ai", "⚡ AI-GENERATED CONTENT LIKELY"),
    (0.40, "uncertain", "🔍 UNCERTAIN - Human Review Recommended"),
    (0.20, "likely_human", "📝 LIKELY HUMAN-WRITTEN CONTENT"),
    (0.00, "human_written", "✅ HUMAN-WRITTEN CONTENT CONFIRMED"),
]


def classify_score(score):
    """Map a 0-1 AI-likeness score to its (attribution, label) pair."""
    for threshold, attribution, label in SCORE_LABELS:
        if score >= threshold:
            return attribution, label
    # Scores are clamped to 0-1 upstream, so the final row always matches;
    # this is a defensive fallback for an out-of-range score.
    return SCORE_LABELS[-1][1], SCORE_LABELS[-1][2]


def iso_timestamp():
    """Return the current UTC time as an ISO-8601 string ending in 'Z'."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# --- Milestone 4: ensemble combination of the two detection signals ----------
# Weights come from planning.md ("weighted average (Groq: 60%, Stylometric:
# 40%)" and "raw_score = (groq_score x 0.6) + (stylometric_score x 0.4)").
# The planning document takes precedence over the 70/30 default. Groq is
# weighted higher because it captures semantic meaning; the stylometric signal
# is purely structural and so contributes less.
GROQ_WEIGHT = 0.60
STYLOMETRIC_WEIGHT = 0.40


def combine_scores(groq_score, stylometric_score):
    """Combine the two independent signal scores into one 0-1 AI-likeness score.

    combined = 0.60 * groq_score + 0.40 * stylometric_score
    """
    return GROQ_WEIGHT * groq_score + STYLOMETRIC_WEIGHT * stylometric_score


def compute_confidence(combined_score):
    """Confidence in the prediction (0-1), as a deterministic function.

    Confidence rises as the combined score moves away from 0.5 (a clear
    human or AI signal) and falls to 0 at exactly 0.5 (maximal uncertainty):

        confidence = 2 * |combined_score - 0.5|

    Note: planning.md discusses a richer signal-agreement calibration, but it
    uses the calibrated score itself as the "confidence" percentage, which does
    not match the distance-from-0.5 behavior required here. We therefore follow
    the explicit distance-based definition for this metric.
    """
    return max(0.0, min(1.0, 2 * abs(combined_score - 0.5)))
