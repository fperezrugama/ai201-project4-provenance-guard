from flask import Blueprint, jsonify

from app.services.analytics import AnalyticsService

bp = Blueprint('analytics', __name__, url_prefix='/analytics')


@bp.route('/metrics', methods=['GET'])
def get_metrics():
    """Return all analytics metrics derived from the audit log.

    Includes: total_submissions, detection_counts, avg_confidence,
    appeal_count, appeal_rate, appeal_status, confidence_timeline (7-day trend),
    avg_signal_scores, and recent_entries.
    """
    metrics = AnalyticsService().get_metrics()
    return jsonify(metrics), 200


@bp.route('/summary', methods=['GET'])
def get_summary():
    """Return a brief, display-formatted summary for a quick dashboard view."""
    metrics = AnalyticsService().get_metrics()
    summary = {
        'total_submissions': metrics['total_submissions'],
        'detection_counts': metrics['detection_counts'],
        'avg_confidence': f"{metrics['avg_confidence'] * 100:.1f}%",
        'appeal_rate': f"{metrics['appeal_rate'] * 100:.1f}%",
        'pending_appeals': metrics['appeal_status']['pending'],
    }
    return jsonify(summary), 200
