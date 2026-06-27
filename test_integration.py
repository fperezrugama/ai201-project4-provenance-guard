"""Milestone 4 integration test: the full /submit ensemble pipeline.

Drives the real endpoint through Flask's test client, so it exercises the
entire chain end to end: validation -> Groq signal -> stylometric signal ->
weighted combination -> confidence -> label -> audit log -> response.

The Groq signal makes a live API call, so its exact score varies run to run.
The assertions therefore check the pipeline's *invariants* (the combination
and confidence math, label consistency, schema, and logging) rather than
hard-coded Groq values.

    python test_integration.py
"""

from app import create_app
from app.utils.helpers import (
    GROQ_WEIGHT,
    STYLOMETRIC_WEIGHT,
    classify_score,
    combine_scores,
    compute_confidence,
    predict_attribution,
)

SAMPLES = [
    ("Clearly AI-generated",
     "Artificial intelligence represents a transformative paradigm shift in "
     "modern society. It is important to note that while the benefits of AI "
     "are numerous, it is equally essential to consider the ethical "
     "implications. Furthermore, stakeholders across various sectors must "
     "collaborate to ensure responsible deployment."),

    ("Clearly human-written",
     "ok so i finally tried that new ramen place downtown and honestly? "
     "underwhelming. the broth was fine but they put WAY too much sodium in "
     "it and i was thirsty for like three hours after. my friend got the "
     "spicy version and said it was better. probably won't go back unless "
     "someone drags me there"),

    ("Borderline formal human",
     "The relationship between monetary policy and asset price inflation has "
     "been extensively studied in the literature. Central banks face a "
     "fundamental tension between their mandate for price stability and the "
     "unintended consequences of prolonged low interest rates on equity and "
     "real estate valuations."),

    ("Borderline edited AI",
     "I've been thinking a lot about remote work lately. There are genuine "
     "tradeoffs—flexibility and no commute on one side, isolation and blurred "
     "work-life boundaries on the other. Studies show productivity varies "
     "widely by individual and role type."),
]

REQUIRED_RESPONSE_FIELDS = {
    "content_id", "attribution", "label", "groq_score", "stylometric_score",
    "combined_score", "confidence", "timestamp", "appeal_available",
}


def test_integration():
    app = create_app()
    client = app.test_client()

    print("🧪 Milestone 4 integration test (Groq + Stylometric ensemble)")
    print(f"   weights: Groq {GROQ_WEIGHT:.0%} / Stylometric {STYLOMETRIC_WEIGHT:.0%}")
    print("=" * 60)

    for name, text in SAMPLES:
        resp = client.post("/submit", json={"text": text, "creator_id": "m4-test"})
        assert resp.status_code == 200, f"{name}: HTTP {resp.status_code}"
        body = resp.get_json()

        groq = body["groq_score"]
        stylo = body["stylometric_score"]
        combined = body["combined_score"]
        confidence = body["confidence"]

        print(f"\n📝 {name}")
        print(f"   Groq score:        {groq:.4f}")
        print(f"   Stylometric score: {stylo:.4f}")
        print(f"   Combined score:    {combined:.4f}")
        print(f"   Confidence:        {confidence:.4f}")
        print(f"   Final prediction:  {body['attribution']}  |  {body['label']}")

        # --- Invariants that must hold regardless of Groq's exact value ---
        assert REQUIRED_RESPONSE_FIELDS <= set(body), f"{name}: missing fields"
        for value in (groq, stylo, combined, confidence):
            assert 0.0 <= value <= 1.0, f"{name}: value out of [0,1]"
        # Combination math (allow rounding tolerance).
        assert abs(combined - combine_scores(groq, stylo)) < 1e-3, f"{name}: combine math"
        # Confidence math: rises away from 0.5, deterministic.
        assert abs(confidence - compute_confidence(combined)) < 1e-3, f"{name}: confidence math"
        # Prediction & label are derived from the COMBINED score (not a single
        # signal). attribution is the standardized 3-value prediction; label is
        # the detailed display string from classify_score.
        assert body["attribution"] == predict_attribution(combined), \
            f"{name}: attribution not derived from combined score"
        assert body["label"] == classify_score(combined)[1], \
            f"{name}: label not derived from combined score"
        assert body["attribution"] in {"ai_generated", "uncertain", "human_written"}, \
            f"{name}: attribution not standardized"
        assert body["transparency_variant"] in {"likely_ai", "uncertain", "likely_human"}, \
            f"{name}: transparency_variant not standardized"

    # --- Audit log records every required field for each submission ---
    log = client.get("/log").get_json()
    assert log["count"] >= len(SAMPLES), "audit log missing entries"
    recent = log["entries"][-len(SAMPLES):]
    for entry in recent:
        for field in ("groq_score", "stylometric_score", "combined_score",
                      "confidence", "attribution"):
            assert field in entry, f"audit log entry missing '{field}'"

    print("\n" + "=" * 60)
    print("✅ Integration tests passed — both signals contribute to every result.")


if __name__ == "__main__":
    test_integration()
