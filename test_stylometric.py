"""Independent test for Signal 2 (stylometric heuristics).

This signal makes no network calls, so it can be tested directly without a
running server or any API key:

    python test_stylometric.py

For the full diagnostic matrix (the four Milestone 4 samples plus targeted
edge cases) see test_metrics.py.
"""

from app.detection.stylometric_signal import stylometric_signal

REQUIRED_METRICS = {
    "sentence_variance",
    "average_sentence_length",
    "type_token_ratio",
}


def test_stylometric():
    print("🧪 Testing Stylometric Signal...")
    print("=" * 50)

    # Human-like: varied sentence lengths, contractions, varied punctuation.
    human_text = (
        "The coffee was cold, but I drank it anyway. Rain. "
        "I sat by the window for what felt like hours, watching strangers "
        "hurry past with umbrellas that the wind had turned inside out. "
        "Funny how a grey afternoon can feel oddly comforting, isn't it?"
    )

    # AI-like: uniform sentence lengths, repetitive vocabulary and structure.
    ai_text = (
        "Artificial intelligence is a transformative technology in modern "
        "society. Artificial intelligence improves efficiency in modern "
        "society. Artificial intelligence enhances productivity in modern "
        "society. Artificial intelligence supports innovation in modern "
        "society."
    )

    human = stylometric_signal(human_text)
    ai = stylometric_signal(ai_text)

    print(f"📝 HUMAN text -> score {human['score']:.2f}  {human['metrics']}")
    print(f"🤖 AI text    -> score {ai['score']:.2f}  {ai['metrics']}")

    # Score bounds and required-metric schema.
    for result in (human, ai):
        assert 0.0 <= result["score"] <= 1.0, "score must be in [0, 1]"
        assert REQUIRED_METRICS <= set(result["metrics"]), "missing required metrics"

    # Human text should score clearly lower (more human-like) than AI text,
    # with a meaningful gap (recalibration target: separation is not tiny).
    assert human["score"] < ai["score"], "human should score lower than AI"
    assert ai["score"] - human["score"] > 0.15, "human/AI separation too small"

    # Too-short and empty inputs return a neutral score, not a crash.
    assert stylometric_signal("hello").get("score") == 0.5, "short text -> neutral"
    assert stylometric_signal("   ").get("score") == 0.5, "empty -> neutral"

    # No single metric may dominate: every weight is <= 0.25.
    from app.detection import stylometric_signal as mod
    weights = [
        mod.WEIGHT_VARIANCE,
        mod.WEIGHT_DIVERSITY,
        mod.WEIGHT_PUNCTUATION,
        mod.WEIGHT_CONTRACTION,
        mod.WEIGHT_AVG_LENGTH,
    ]
    assert abs(sum(weights) - 1.0) < 1e-9, "weights must sum to 1.0"
    assert max(weights) <= 0.25 + 1e-9, "no metric may dominate (weight > 0.25)"

    print("=" * 50)
    print("✅ Tests complete!")


if __name__ == "__main__":
    test_stylometric()
