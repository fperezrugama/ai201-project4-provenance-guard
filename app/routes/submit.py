from flask import Blueprint, request, jsonify
import uuid

from app.detection.groq_signal import groq_signal
from app.detection.stylometric_signal import stylometric_signal
from app.services.audit_log import AuditLog
from app.utils.validators import validate_submission
from app.utils.helpers import (
    classify_score,
    combine_scores,
    compute_confidence,
    iso_timestamp,
)

bp = Blueprint('submit', __name__, url_prefix='/')

# Single shared audit log for the blueprint.
audit_log = AuditLog()


@bp.route('/submit', methods=['POST'])
def submit_content():
    """Submit content for attribution analysis using the Groq signal."""
    payload = request.get_json(silent=True)

    error = validate_submission(payload)
    if error:
        return jsonify({"error": error}), 400

    text = payload['text'].strip()
    creator_id = payload['creator_id'].strip()
    content_id = str(uuid.uuid4())
    timestamp = iso_timestamp()

    # Run the two independent detection signals. They are kept completely
    # separate — Signal 1 (Groq LLM) and Signal 2 (stylometric heuristics) —
    # and only their numeric scores are combined here.
    groq_result = groq_signal(text)
    groq_score = groq_result['score']

    stylometric_result = stylometric_signal(text)
    stylometric_score = stylometric_result['score']

    # Ensemble: weighted average (Groq 60%, Stylometric 40%) -> confidence ->
    # final prediction label, all from the combined score.
    combined_score = round(combine_scores(groq_score, stylometric_score), 4)
    confidence = round(compute_confidence(combined_score), 4)
    attribution, label = classify_score(combined_score)

    audit_log.add_entry({
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": timestamp,
        "attribution": attribution,
        "confidence": confidence,
        "groq_score": groq_score,
        "groq_confidence": groq_result['confidence'],
        "groq_reasoning": groq_result.get('reasoning', ''),
        "stylometric_score": stylometric_score,
        "combined_score": combined_score,
        "status": "classified",
        "signal_used": "ensemble",
    })

    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "label": label,
        "groq_score": groq_score,
        "stylometric_score": stylometric_score,
        "combined_score": combined_score,
        "confidence": confidence,
        "timestamp": timestamp,
        "appeal_available": True,
    }), 200


@bp.route('/log', methods=['GET'])
def get_log():
    """Return the audit log entries."""
    entries = audit_log.get_entries()
    return jsonify({"entries": entries, "count": len(entries)}), 200


@bp.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({
        "status": "healthy",
        "message": "Provenance Guard is running!",
        "log_entries": audit_log.get_entries(limit=5),
    }), 200
