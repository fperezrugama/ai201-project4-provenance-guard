"""Analytics service: read-only metrics derived from the audit log.

This service ONLY reads the audit-log JSON file. It never writes to it and does
not touch the detection pipeline. It is defensive about missing files, missing
fields, and unparseable timestamps so a malformed entry can never crash a
metrics request.
"""

import json
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone


class AnalyticsService:
    def __init__(self, log_file='data/audit_log.json'):
        self.log_file = log_file

    def _load_log(self):
        """Load audit log entries, tolerating a missing or corrupt file."""
        try:
            with open(self.log_file, 'r') as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    @staticmethod
    def _parse_timestamp(value):
        """Parse an ISO-8601 timestamp into a tz-aware datetime, or None."""
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (AttributeError, TypeError, ValueError):
            return None

    @staticmethod
    def _mean(values):
        return statistics.mean(values) if values else 0

    def get_metrics(self):
        """Calculate all analytics metrics."""
        entries = self._load_log()
        if not entries:
            return self._empty_metrics()

        total = len(entries)

        # 1. Detection summary (uses the standardized 3-value attribution).
        attributions = [e.get('attribution') for e in entries if e.get('attribution')]
        detection_counts = dict(Counter(attributions))

        # 2. Average confidence.
        confidences = [e['confidence'] for e in entries if isinstance(e.get('confidence'), (int, float))]
        avg_confidence = self._mean(confidences)

        # 3. Appeals.
        appeals = [e for e in entries if e.get('appeal_reasoning')]
        appeal_count = len(appeals)
        appeal_rate = appeal_count / total if total else 0
        appeal_status = {
            'pending': sum(1 for a in appeals if a.get('status') == 'under_review'),
            'approved': sum(1 for a in appeals if a.get('status') == 'human_approved'),
            'denied': sum(1 for a in appeals if a.get('status') == 'human_rejected'),
        }

        # 4. Additional metric A: average confidence per day for the last 7 days
        #    (chronological, oldest first). Days with no data report None.
        now = datetime.now(timezone.utc)
        confidence_timeline = []
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
            day_confidences = [
                e['confidence'] for e in entries
                if isinstance(e.get('confidence'), (int, float))
                and (ts := self._parse_timestamp(e.get('timestamp'))) is not None
                and day_start <= ts <= day_end
            ]
            confidence_timeline.append({
                'date': day.strftime('%Y-%m-%d'),
                'avg_confidence': round(self._mean(day_confidences), 3) if day_confidences else None,
            })

        # 5. Additional metric B: average score per signal (this is a 3-signal
        #    system, so the per-signal averages reveal which signal drives
        #    decisions and how the behavioral signal compares).
        avg_signal_scores = {
            'groq': round(self._mean([e['groq_score'] for e in entries if isinstance(e.get('groq_score'), (int, float))]), 3),
            'stylometric': round(self._mean([e['stylometric_score'] for e in entries if isinstance(e.get('stylometric_score'), (int, float))]), 3),
            'behavioral': round(self._mean([e['behavioral_score'] for e in entries if isinstance(e.get('behavioral_score'), (int, float))]), 3),
        }

        return {
            'total_submissions': total,
            'detection_counts': detection_counts,
            'avg_confidence': round(avg_confidence, 3),
            'appeal_count': appeal_count,
            'appeal_rate': round(appeal_rate, 3),
            'appeal_status': appeal_status,
            'confidence_timeline': confidence_timeline,
            'avg_signal_scores': avg_signal_scores,
            'recent_entries': entries[-10:],
        }

    def _empty_metrics(self):
        """Return zeroed metrics when no data exists."""
        return {
            'total_submissions': 0,
            'detection_counts': {},
            'avg_confidence': 0,
            'appeal_count': 0,
            'appeal_rate': 0,
            'appeal_status': {'pending': 0, 'approved': 0, 'denied': 0},
            'confidence_timeline': [],
            'avg_signal_scores': {'groq': 0, 'stylometric': 0, 'behavioral': 0},
            'recent_entries': [],
        }
