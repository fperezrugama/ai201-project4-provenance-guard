from flask import Blueprint, request, jsonify
import uuid

from app.detection.groq_signal import groq_signal
from app.services.audit_log import AuditLog
from app.utils.validators import validate_submission
from app.utils.helpers import classify_score, iso_timestamp

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

    # Signal 1: Groq LLM assessment. It is the only signal wired up in
    # Milestone 3, so its score maps directly to the label (the ensemble and
    # calibration steps arrive in Milestone 4).
    groq_result = groq_signal(text)
    score = groq_result['score']
    confidence = groq_result['confidence']

    attribution, label = classify_score(score)

    audit_log.add_entry({
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": timestamp,
        "attribution": attribution,
        "confidence": confidence,
        "groq_score": score,
        "groq_confidence": confidence,
        "groq_reasoning": groq_result.get('reasoning', ''),
        "status": "classified",
        "signal_used": "groq",
    })

    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "confidence": confidence,
        "label": label,
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
