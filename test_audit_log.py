"""Milestone 5 - Step 4: verify the audit log is complete and well-formed.

Asserts that every audit-log entry records the required fields, that appealed
entries additionally carry the appeal information, and that the log on disk
remains structured JSON. Also prints three sample entries (normal submission,
second submission, appealed submission).

    python test_audit_log.py
"""

import json

import app.routes.submit as submit_mod
from app import create_app

# Required keys on every entry. "attribution" is the prediction field.
REQUIRED_FIELDS = {
    "timestamp",
    "content_id",
    "creator_id",
    "groq_score",
    "stylometric_score",
    "combined_score",
    "confidence",
    "attribution",   # prediction
    "status",
}
# Appeal information is only expected once an entry has been appealed.
APPEAL_FIELDS = {"appeal_reasoning", "appeal_timestamp", "original_classification"}

LOG_FILE = "data/audit_log.json"


def test_audit_log():
    # Deterministic, offline signals so the test does not hit the network.
    submit_mod.groq_signal = lambda t: {"score": 0.9, "confidence": 0.9, "reasoning": "demo"}
    submit_mod.stylometric_signal = lambda t: {"score": 0.85, "metrics": {}}

    app = create_app()
    client = app.test_client()

    # Start from an empty log for a clean demonstration.
    submit_mod.audit_log.clear()

    # 1) normal submission, 2) second submission
    first = client.post("/submit", json={"text": "first piece of content", "creator_id": "alice"}).get_json()
    client.post("/submit", json={"text": "second piece of content", "creator_id": "bob"}).get_json()

    # 3) appeal the first submission
    client.post("/appeal", json={
        "content_id": first["content_id"],
        "creator_reasoning": "This is my original work.",
    })

    entries = client.get("/log").get_json()["entries"]

    # --- Verify every entry has the required fields ---
    for entry in entries:
        missing = REQUIRED_FIELDS - set(entry)
        assert not missing, f"entry {entry.get('content_id')} missing {missing}"

    # --- Verify the appealed entry carries appeal information ---
    appealed = next(e for e in entries if e["content_id"] == first["content_id"])
    assert appealed["status"] == "under_review", "appealed entry status not updated"
    assert APPEAL_FIELDS <= set(appealed), f"appeal fields missing: {APPEAL_FIELDS - set(appealed)}"

    # --- Verify the log on disk is still valid, structured JSON ---
    with open(LOG_FILE) as f:
        on_disk = json.load(f)
    assert isinstance(on_disk, list) and len(on_disk) == len(entries), "log is not a JSON list"

    print("✅ Audit log complete: every entry has all required fields.")
    print(f"   {len(entries)} entries, valid JSON, appealed entry carries appeal info.\n")
    print("=== SAMPLE AUDIT LOG ===")
    print(json.dumps(entries, indent=2, ensure_ascii=False))

    open(LOG_FILE, "w").close()  # restore the git-ignored log to empty


if __name__ == "__main__":
    test_audit_log()
