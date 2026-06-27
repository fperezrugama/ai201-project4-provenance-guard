from flask import Blueprint, request, jsonify
import uuid

from app.detection.groq_signal import groq_signal
from app.detection.stylometric_signal import stylometric_signal
from app.extensions import limiter
from app.services.audit_log import AuditLog
from app.utils.validators import validate_submission, validate_appeal
from app.utils.helpers import (
    classify_score,
    combine_scores,
    compute_confidence,
    iso_timestamp,
    predict_attribution,
    transparency_label,
)

bp = Blueprint('submit', __name__, url_prefix='/')

# Single shared audit log for the blueprint.
audit_log = AuditLog()


# Rate limits for content submission (per client IP), from planning.md:
# 10 requests/minute throttles bursts/abuse; 100 requests/day caps sustained
# volume. Only this endpoint is protected — /appeal, /log and /health are not.
@bp.route('/submit', methods=['POST'])
@limiter.limit("10 per minute; 100 per day")
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

    # Prediction vs. transparency are kept as separate concepts:
    #   attribution         -> standardized prediction (ai_generated/uncertain/human_written)
    #   label               -> detailed 5-tier display string (unchanged)
    #   transparency_variant-> user-facing variant (likely_ai/uncertain/likely_human)
    attribution = predict_attribution(combined_score)
    _, label = classify_score(combined_score)

    # Milestone 5: build the explanatory transparency label. This is derived
    # from the prediction and confidence above; it does not alter either.
    transparency_variant, transparency_text = transparency_label(attribution, confidence)

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
        "transparency_label": transparency_text,
        "transparency_variant": transparency_variant,
        "groq_score": groq_score,
        "stylometric_score": stylometric_score,
        "combined_score": combined_score,
        "confidence": confidence,
        "timestamp": timestamp,
        "appeal_available": True,
    }), 200


@bp.route('/appeal', methods=['POST'])
def appeal_content():
    """Appeal a prior classification, flagging it for human review.

    This only changes the submission's review status and records the appeal.
    It does NOT re-run or alter any prediction — the original classification is
    preserved and snapshotted into the audit log.
    """
    payload = request.get_json(silent=True)

    error = validate_appeal(payload)
    if error:
        return jsonify({"error": error}), 400

    content_id = payload['content_id'].strip()
    creator_reasoning = payload['creator_reasoning'].strip()

    # Locate the existing submission.
    entry = audit_log.get_entry_by_content_id(content_id)
    if not entry:
        return jsonify({"error": "Content not found"}), 404

    # Snapshot the original classification so the appeal record preserves it.
    original_classification = {
        "attribution": entry.get("attribution"),
        "combined_score": entry.get("combined_score"),
        "confidence": entry.get("confidence"),
        "groq_score": entry.get("groq_score"),
        "stylometric_score": entry.get("stylometric_score"),
    }

    appeal_timestamp = iso_timestamp()
    audit_log.update_entry(content_id, {
        "status": "under_review",
        "appeal_reasoning": creator_reasoning,
        "appeal_timestamp": appeal_timestamp,
        "original_classification": original_classification,
    })

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "appeal_timestamp": appeal_timestamp,
        "message": "Appeal received. Your content will be reviewed by a human.",
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
