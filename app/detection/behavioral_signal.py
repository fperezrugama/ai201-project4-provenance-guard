"""Signal 3: Behavioral / metadata analysis.

This signal looks at behavioral patterns *around* a submission rather than the
linguistic content of the text. It is independent of Signal 1 (Groq, semantic)
and Signal 2 (stylometric, structural).

Score convention (identical to the other two signals so they can be combined):

    0.0 = human-like behavior
    1.0 = AI-like behavior

Behavior is only observable across MULTIPLE submissions, so with no prior
history for a creator the signal is neutral (0.5) and low-confidence. As history
accumulates it becomes more informative and more confident. This is why it
carries the lowest weight in the ensemble — it starts out uninformative.
"""

import difflib
import statistics

# --- Tuning constants (simple, documented heuristics) -----------------------
# Length coefficient-of-variation: human submissions vary in length; uniform
# lengths look automated. CV at/above this reads fully human.
LENGTH_CV_HUMAN = 0.50
# Submission cadence: very short gaps between submissions look automated;
# human-paced gaps are larger.
RAPID_GAP_SECONDS = 10.0    # at/below this -> fully AI-like cadence
SLOW_GAP_SECONDS = 300.0    # at/above this -> fully human-like cadence


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def behavioral_signal(text, creator_id=None, submission_history=None):
    """Analyze behavioral patterns that may indicate automated/AI use.

    Args:
        text: the current submission text.
        creator_id: the submitter (context only; not required).
        submission_history: list of the creator's PRIOR submissions. Each item
            is a dict that may contain 'text' and 'time' (epoch seconds). If
            None/empty, there is not enough history to judge behavior.

    Returns:
        dict: {
            'score': float (0-1, 0=human-like, 1=AI-like),
            'confidence': float (0-1),
            'metrics': {
                'length_consistency': float,
                'submission_frequency': float,
                'similarity_score': float
            }
        }
    """
    history = submission_history or []

    # No prior submissions -> behavior cannot be assessed -> neutral.
    if not history:
        return {
            'score': 0.5,
            'confidence': 0.3,
            'metrics': {
                'length_consistency': 0.5,
                'submission_frequency': 0.5,
                'similarity_score': 0.5,
                'reason': 'Insufficient history',
            },
        }

    prior_texts = [h.get('text', '') for h in history if h.get('text') is not None]
    prior_times = sorted(h['time'] for h in history if h.get('time') is not None)

    # --- Metric 1: length consistency (AI output tends to be uniform) ---
    lengths = [len(t) for t in prior_texts] + [len(text)]
    if len(lengths) >= 2 and statistics.mean(lengths) > 0:
        cv = statistics.stdev(lengths) / statistics.mean(lengths)
        length_consistency = _clamp(1 - cv / LENGTH_CV_HUMAN)  # uniform -> AI-like
    else:
        length_consistency = 0.5

    # --- Metric 2: submission frequency (rapid bursts look automated) ---
    if len(prior_times) >= 2:
        gaps = [b - a for a, b in zip(prior_times, prior_times[1:])]
        median_gap = statistics.median(gaps)
        submission_frequency = _clamp(
            (SLOW_GAP_SECONDS - median_gap) / (SLOW_GAP_SECONDS - RAPID_GAP_SECONDS)
        )
    else:
        submission_frequency = 0.5

    # --- Metric 3: similarity to prior submissions (templated/duplicated) ---
    if prior_texts:
        sims = [difflib.SequenceMatcher(None, text, pt).ratio() for pt in prior_texts]
        similarity_score = _clamp(max(sims))  # near-duplicate content -> AI-like
    else:
        similarity_score = 0.5

    score = statistics.mean([length_consistency, submission_frequency, similarity_score])
    # Confidence grows with how much history we have, capped at 0.9.
    confidence = _clamp(0.3 + 0.15 * len(history), 0.0, 0.9)

    return {
        'score': round(_clamp(score), 4),
        'confidence': round(confidence, 4),
        'metrics': {
            'length_consistency': round(length_consistency, 4),
            'submission_frequency': round(submission_frequency, 4),
            'similarity_score': round(similarity_score, 4),
        },
    }
