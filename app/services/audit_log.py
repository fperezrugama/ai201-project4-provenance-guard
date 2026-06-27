import json
import os
import tempfile
import threading

from app.utils.helpers import iso_timestamp


class AuditLog:
    """Simple audit log that writes to a JSON file.

    Thread-safe: the dev server handles requests on multiple threads, so a
    rapid burst of submissions (e.g. the rate-limit tester) can call into the
    log concurrently. A lock serializes mutations + saves so concurrent writes
    cannot corrupt the in-memory list or race on the on-disk file.
    """

    def __init__(self, log_file='data/audit_log.json'):
        self.log_file = log_file
        self.entries = []
        self._lock = threading.Lock()
        self._load_log()
    
    def _load_log(self):
        """Load existing log entries from file, tolerating a missing or
        corrupt file by starting from an empty log."""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    self.entries = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.entries = []
        else:
            self.entries = []

    def _save_log(self):
        """Persist log entries atomically.

        Each save writes to its OWN uniquely named temp file and then renames
        it into place. A unique temp name (rather than a single shared one)
        means concurrent writers can never rename each other's half-written or
        already-moved file -- the previous shared "<log>.tmp" name caused
        intermittent FileNotFoundError (HTTP 500) under concurrent submits.
        Callers hold self._lock, so writes are also serialized.
        """
        directory = os.path.dirname(self.log_file) or '.'
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(self.entries, f, indent=2)
            os.replace(tmp_path, self.log_file)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def add_entry(self, entry):
        """Add a new entry to the log"""
        # Ensure timestamp exists
        if 'timestamp' not in entry:
            entry['timestamp'] = iso_timestamp()

        with self._lock:
            self.entries.append(entry)
            self._save_log()
        return entry

    def get_entries(self, limit=100):
        """Get the most recent log entries"""
        with self._lock:
            return self.entries[-limit:]

    def get_entry_by_content_id(self, content_id):
        """Get a specific entry by content_id"""
        with self._lock:
            for entry in reversed(self.entries):
                if entry.get('content_id') == content_id:
                    return entry
        return None

    def update_entry(self, content_id, updates):
        """Update an existing entry"""
        with self._lock:
            for i, entry in enumerate(self.entries):
                if entry.get('content_id') == content_id:
                    self.entries[i].update(updates)
                    self._save_log()
                    return self.entries[i]
        return None

    def clear(self):
        """Clear all entries (for testing)"""
        with self._lock:
            self.entries = []
            self._save_log()