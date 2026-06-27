"""Verified Human / provenance certificate service.

Manages verification credentials for creators. Credentials are NEVER granted
automatically: a creator requests verification (-> pending) and a MODERATOR must
explicitly approve or deny it. Data is persisted to data/certificates.json.

Writes are serialized with a lock and use an atomic temp-file rename, matching
the audit log, so concurrent requests cannot corrupt the file.
"""

import json
import os
import tempfile
import threading
import uuid

from app.utils.helpers import iso_timestamp


class CertificateService:
    def __init__(self, cert_file='data/certificates.json'):
        self.cert_file = cert_file
        self.certificates = {}
        self._lock = threading.Lock()
        self._load_certificates()

    def _load_certificates(self):
        """Load certificates, tolerating a missing or corrupt file."""
        if os.path.exists(self.cert_file):
            try:
                with open(self.cert_file, 'r') as f:
                    data = json.load(f)
                self.certificates = data if isinstance(data, dict) else {}
            except (json.JSONDecodeError, FileNotFoundError):
                self.certificates = {}
        else:
            self.certificates = {}

    def _save_certificates(self):
        """Persist certificates atomically (unique temp file + rename)."""
        directory = os.path.dirname(self.cert_file) or '.'
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(self.certificates, f, indent=2)
            os.replace(tmp_path, self.cert_file)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def request_verification(self, creator_id):
        """Submit a verification request for a creator (-> pending)."""
        with self._lock:
            existing = self.certificates.get(creator_id)
            if existing:
                if existing.get('status') == 'active':
                    return {'status': 'already_verified', 'certificate': existing}
                if existing.get('status') == 'pending':
                    return {'status': 'already_pending',
                            'message': 'Verification request already submitted',
                            'request_id': existing.get('request_id')}

            request_id = f'req-{uuid.uuid4().hex[:8]}'
            self.certificates[creator_id] = {
                'creator_id': creator_id,
                'status': 'pending',
                'request_id': request_id,
                'requested_at': iso_timestamp(),
                'verification_method': 'manual_review',
            }
            self._save_certificates()
            return {
                'status': 'pending',
                'request_id': request_id,
                'message': 'Verification request submitted. A moderator will review your request.',
            }

    def approve_verification(self, creator_id, method='manual_review', notes=None):
        """Approve a creator's verification request (moderator action)."""
        with self._lock:
            if creator_id not in self.certificates:
                return {'error': 'No verification request found'}
            cert = self.certificates[creator_id]
            cert['status'] = 'active'
            cert['verified_at'] = iso_timestamp()
            cert['verification_method'] = method
            cert['verified_by'] = 'moderator'
            cert['review_notes'] = notes
            cert['certificate_id'] = f'cert-{uuid.uuid4().hex[:12]}'
            self._save_certificates()
            return {'status': 'active', 'certificate': cert}

    def deny_verification(self, creator_id, reason=None):
        """Deny a creator's verification request (moderator action)."""
        with self._lock:
            if creator_id not in self.certificates:
                return {'error': 'No verification request found'}
            cert = self.certificates[creator_id]
            cert['status'] = 'denied'
            cert['denied_at'] = iso_timestamp()
            cert['denial_reason'] = reason
            self._save_certificates()
            return {'status': 'denied', 'message': 'Verification request denied.', 'reason': reason}

    def revoke_verification(self, creator_id, reason=None):
        """Revoke an existing certificate (admin action)."""
        with self._lock:
            if creator_id not in self.certificates:
                return {'error': 'No certificate found'}
            cert = self.certificates[creator_id]
            cert['status'] = 'revoked'
            cert['revoked_at'] = iso_timestamp()
            cert['revocation_reason'] = reason
            self._save_certificates()
            return {'status': 'revoked', 'message': 'Certificate revoked.', 'reason': reason}

    def get_status(self, creator_id):
        """Get verification status for a creator (or 'none')."""
        return self.certificates.get(creator_id, {'status': 'none', 'creator_id': creator_id})

    def is_verified(self, creator_id):
        """True only if the creator currently holds an active certificate."""
        return self.get_status(creator_id).get('status') == 'active'

    def get_pending_requests(self):
        """All pending verification requests (for the moderator UI)."""
        return [c for c in self.certificates.values() if c.get('status') == 'pending']


# Shared singleton: one in-memory cache backed by the JSON file, imported by
# both the certificate routes and the /submit route so an approval is
# immediately visible everywhere (avoids divergent per-blueprint caches).
certificate_service = CertificateService()
