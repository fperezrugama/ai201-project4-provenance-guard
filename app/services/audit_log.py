import json
import os

from app.utils.helpers import iso_timestamp


class AuditLog:
    """Simple audit log that writes to a JSON file"""
    
    def __init__(self, log_file='data/audit_log.json'):
        self.log_file = log_file
        self.entries = []
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

        Writing to a temporary file and then renaming it means a crash
        mid-write can never leave a half-written, corrupt audit log: the
        real file is only ever replaced once the new copy is fully on disk.
        """
        directory = os.path.dirname(self.log_file)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp_file = self.log_file + '.tmp'
        with open(tmp_file, 'w') as f:
            json.dump(self.entries, f, indent=2)
        os.replace(tmp_file, self.log_file)
    
    def add_entry(self, entry):
        """Add a new entry to the log"""
        # Ensure timestamp exists
        if 'timestamp' not in entry:
            entry['timestamp'] = iso_timestamp()
        
        self.entries.append(entry)
        self._save_log()
        return entry
    
    def get_entries(self, limit=100):
        """Get the most recent log entries"""
        return self.entries[-limit:]
    
    def get_entry_by_content_id(self, content_id):
        """Get a specific entry by content_id"""
        for entry in reversed(self.entries):
            if entry.get('content_id') == content_id:
                return entry
        return None
    
    def update_entry(self, content_id, updates):
        """Update an existing entry"""
        for i, entry in enumerate(self.entries):
            if entry.get('content_id') == content_id:
                self.entries[i].update(updates)
                self._save_log()
                return self.entries[i]
        return None
    
    def clear(self):
        """Clear all entries (for testing)"""
        self.entries = []
        self._save_log()