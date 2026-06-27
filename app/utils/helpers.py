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
