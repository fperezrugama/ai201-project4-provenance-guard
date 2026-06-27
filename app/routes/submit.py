from flask import Blueprint, request, jsonify
import uuid
import time
from collections import defaultdict

from app.detection.groq_signal import groq_signal
from app.detection.stylometric_signal import stylometric_signal
from app.detection.behavioral_signal import behavioral_signal
from app.detection.ensemble import EnsembleDetector
from app.detection.registry import DetectorRegistry
from app.extensions import limiter
from app.services.audit_log import AuditLog
from app.services.certificate import certificate_service
from app.utils.validators import validate_submission, validate_appeal
from app.utils.helpers import (
    classify_score,
    iso_timestamp,
    predict_attribution,
    transparency_label,
)

bp = Blueprint('submit', __name__, url_prefix='/')

# Single shared audit log for the blueprint.
audit_log = AuditLog()

# Shared ensemble aggregator.
ensemble = EnsembleDetector()

# Registry of content detectors (multi-modal: 'text', 'image_description').
detector_registry = DetectorRegistry()

# Lightweight in-memory submission history per creator, used only to give the
# behavioral signal something to compare against (recent text + time). It is
# process-local and resets on restart — it is NOT persisted and does not change
# the audit log. With no prior entry for a creator the behavioral signal stays
# neutral (0.5).
_submission_history = defaultdict(list)


# Rate limits for content submission (per client IP), from planning.md:
# 10 requests/minute throttles bursts/abuse; 100 requests/day caps sustained
# volume. Only this endpoint is protected — /appeal, /log and /health are not.
@bp.route('/submit', methods=['POST'])
@limiter.limit("10 per minute; 100 per day")
def submit_content():
    """Submit content for attribution analysis.

    Supports content_type 'text' (default, the 3-signal ensemble) and
    'image_description' (heuristic detector). Text is handled inline below;
    image descriptions are routed to a parallel handler.
    """
    payload = request.get_json(silent=True)

    # Multi-modal dispatch. Text falls through to the unchanged path below.
    if isinstance(payload, dict):
        content_type = payload.get('content_type', 'text')
        if content_type == 'image_description':
            return _submit_image_description(payload)
        if content_type != 'text':
            return jsonify({
                "error": f"Unsupported content_type: {content_type}",
                "supported_types": detector_registry.get_supported_types(),
            }), 400

    error = validate_submission(payload)
    if error:
        return jsonify({"error": error}), 400

    text = payload['text'].strip()
    creator_id = payload['creator_id'].strip()
    content_id = str(uuid.uuid4())
    timestamp = iso_timestamp()

    # Run the three independent detection signals. They are kept completely
    # separate — Signal 1 (Groq LLM, semantic), Signal 2 (stylometric,
    # structural), Signal 3 (behavioral, metadata) — and only their numeric
    # scores are combined by the ensemble.
    groq_result = groq_signal(text)
    groq_score = groq_result['score']

    stylometric_result = stylometric_signal(text)
    stylometric_score = stylometric_result['score']

    # Behavioral signal: pass the creator's PRIOR submissions so it can assess
    # behavior. With no prior history it returns a neutral 0.5.
    prior_history = list(_submission_history[creator_id])
    behavioral_result = behavioral_signal(text, creator_id, submission_history=prior_history)
    behavioral_score = behavioral_result['score']
    # Record this submission for future behavioral comparisons (in-memory only).
    _submission_history[creator_id].append({"text": text, "time": time.time()})

    # Three-signal ensemble: combined score (Groq 40% / Stylometric 35% /
    # Behavioral 25%) and agreement-based confidence (1 - stdev * 1.5).
    result = ensemble.detect_three_signal(groq_result, stylometric_result, behavioral_result)
    combined_score = result['combined_score']
    confidence = result['confidence']

    # Prediction vs. transparency are kept as separate concepts:
    #   attribution         -> standardized prediction (ai_generated/uncertain/human_written)
    #   label               -> detailed 5-tier display string (unchanged)
    #   transparency_variant-> user-facing variant (likely_ai/uncertain/likely_human)
    attribution = predict_attribution(combined_score)
    _, label = classify_score(combined_score)

    # Verified Human credential (display only — does not affect detection).
    is_verified = certificate_service.is_verified(creator_id)

    # Milestone 5: explanatory transparency label, derived from the prediction
    # and confidence above; it does not alter either. A verified creator gets a
    # badge appended to the label text.
    transparency_variant, transparency_text = transparency_label(
        attribution, confidence, is_verified=is_verified)

    audit_log.add_entry({
        "content_id": content_id,
        "creator_id": creator_id,
        "content_type": "text",
        "timestamp": timestamp,
        "attribution": attribution,
        "confidence": confidence,
        "groq_score": groq_score,
        "groq_confidence": groq_result['confidence'],
        "groq_reasoning": groq_result.get('reasoning', ''),
        "stylometric_score": stylometric_score,
        "behavioral_score": behavioral_score,
        "combined_score": combined_score,
        "status": "classified",
        "signal_used": "ensemble-3",
    })

    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "label": label,
        "transparency_label": transparency_text,
        "transparency_variant": transparency_variant,
        "is_verified": is_verified,
        "content_type": "text",
        "groq_score": groq_score,
        "stylometric_score": stylometric_score,
        "behavioral_score": behavioral_score,
        "combined_score": combined_score,
        "confidence": confidence,
        "timestamp": timestamp,
        "appeal_available": True,
    }), 200


def _submit_image_description(payload):
    """Handle an image_description submission (parallel to the text path).

    Runs the heuristic ImageDescriptionDetector via the registry, then applies
    the same transparency-label, certificate, and audit-log conventions as the
    text path. Called from within submit_content so the rate limit applies.
    """
    creator_id = payload.get('creator_id')
    if not isinstance(creator_id, str) or not creator_id.strip():
        return jsonify({"error": "Invalid input - creator_id field required"}), 400
    creator_id = creator_id.strip()

    description = payload.get('description')
    if not isinstance(description, str) or not description.strip():
        return jsonify({"error": "Invalid input - description field required for image_description"}), 400
    description = description.strip()

    metadata = {
        "creator_id": creator_id,
        "width": payload.get('width'),
        "height": payload.get('height'),
        "format": payload.get('format', 'unknown'),
        "objects": payload.get('objects', []),
    }

    detector = detector_registry.get_detector('image_description')
    result = detector.detect(description, metadata)

    combined_score = round(result['combined_score'], 4)
    confidence = round(result['confidence'], 4)
    attribution = result['attribution']
    signal_scores = result.get('signal_scores', {})
    explanation = result.get('explanation', '')

    _, label = classify_score(combined_score)
    is_verified = certificate_service.is_verified(creator_id)
    transparency_variant, transparency_text = transparency_label(
        attribution, confidence, is_verified=is_verified)

    content_id = str(uuid.uuid4())
    timestamp = iso_timestamp()

    audit_log.add_entry({
        "content_id": content_id,
        "creator_id": creator_id,
        "content_type": "image_description",
        "timestamp": timestamp,
        "attribution": attribution,
        "confidence": confidence,
        "combined_score": combined_score,
        "signal_scores": signal_scores,
        "status": "classified",
        "signal_used": "image_description",
        "is_verified": is_verified,
    })

    return jsonify({
        "content_id": content_id,
        "attribution": attribution,
        "label": label,
        "transparency_label": transparency_text,
        "transparency_variant": transparency_variant,
        "is_verified": is_verified,
        "content_type": "image_description",
        "combined_score": combined_score,
        "confidence": confidence,
        "signal_scores": signal_scores,
        "explanation": explanation,
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
