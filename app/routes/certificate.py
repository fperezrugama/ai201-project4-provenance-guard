from flask import Blueprint, request, jsonify

from app.services.certificate import certificate_service as cert_service

bp = Blueprint('certificate', __name__, url_prefix='/certificate')


@bp.route('/request', methods=['POST'])
def request_verification():
    """Request verification for a creator -> pending."""
    data = request.get_json(silent=True)
    if not data or 'creator_id' not in data or not isinstance(data['creator_id'], str):
        return jsonify({'error': 'creator_id required'}), 400
    creator_id = data['creator_id'].strip()
    if not creator_id:
        return jsonify({'error': 'creator_id cannot be empty'}), 400

    result = cert_service.request_verification(creator_id)
    status = result.get('status')
    if status == 'pending':
        return jsonify(result), 202  # Accepted
    if status in ('already_verified', 'already_pending'):
        return jsonify(result), 200
    return jsonify(result), 500


@bp.route('/status/<creator_id>', methods=['GET'])
def get_verification_status(creator_id):
    """Get verification status for a creator."""
    return jsonify(cert_service.get_status(creator_id)), 200


@bp.route('/review', methods=['GET'])
def get_pending_requests():
    """List all pending verification requests (moderator view)."""
    pending = cert_service.get_pending_requests()
    return jsonify({'pending_count': len(pending), 'pending_requests': pending}), 200


@bp.route('/review/approve', methods=['POST'])
def approve_verification():
    """Approve a verification request (moderator action)."""
    data = request.get_json(silent=True)
    if not data or 'creator_id' not in data or not isinstance(data['creator_id'], str):
        return jsonify({'error': 'creator_id required'}), 400
    creator_id = data['creator_id'].strip()
    method = data.get('method', 'manual_review')
    notes = data.get('notes')

    result = cert_service.approve_verification(creator_id, method, notes)
    if 'error' in result:
        return jsonify(result), 404
    return jsonify(result), 200


@bp.route('/review/deny', methods=['POST'])
def deny_verification():
    """Deny a verification request (moderator action)."""
    data = request.get_json(silent=True)
    if not data or 'creator_id' not in data or not isinstance(data['creator_id'], str):
        return jsonify({'error': 'creator_id required'}), 400
    creator_id = data['creator_id'].strip()
    reason = data.get('reason')

    result = cert_service.deny_verification(creator_id, reason)
    if 'error' in result:
        return jsonify(result), 404
    return jsonify(result), 200


@bp.route('/revoke/<creator_id>', methods=['POST'])
def revoke_certificate(creator_id):
    """Revoke a verification certificate (admin action)."""
    data = request.get_json(silent=True) or {}
    reason = data.get('reason')
    result = cert_service.revoke_verification(creator_id.strip(), reason)
    if 'error' in result:
        return jsonify(result), 404
    return jsonify(result), 200
