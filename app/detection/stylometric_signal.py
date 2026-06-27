"""Signal 2: Stylometric heuristics (recalibrated).

A purely structural, rule-based detector that estimates how "AI-like" a piece
of text is from its surface statistics alone. It never calls an LLM or any
network service, which makes it fast, deterministic, free, and completely
independent of Signal 1 (the Groq LLM assessment in groq_signal.py).

Score convention (identical to the Groq signal so the two can be combined
later in Milestone 4):

    0.0 = strongly human-like
    1.0 = strongly AI-like

------------------------------------------------------------------------------
WHY THIS WAS RECALIBRATED
------------------------------------------------------------------------------
The previous version had four problems, all traceable to two root causes:

  Root cause A — sentence-length variance was over-weighted (0.50) and so
  dominated the final score. A text with very uneven sentence lengths collapsed
  to ~0.02; a uniform text was pulled hard toward AI.

  Root cause B — variance was computed as 0.0 for any single-sentence input,
  which the old code then read as "perfectly uniform" => maximally AI. That one
  artifact (a 0.50 contribution) is what actually pushed a single long sentence
  to ~0.65 and a rich single sentence to ~0.58 — NOT average length or lexical
  diversity, which were behaving correctly. The surface diagnosis blamed the
  wrong metrics.

Fixes:
  * Five balanced metrics instead of three lop-sided ones; no metric weighs
    more than 0.25, so none can dominate.
  * Variance is scored from the coefficient of variation (scale-free) and is
    treated as NEUTRAL (0.5) when there are too few sentences to measure it,
    killing the single-sentence artifact.
  * Lexical diversity is scored with a moving-average TTR (MATTR) so that long
    texts are not penalised merely for being long.
  * Two new human-positive cues (punctuation variety, contraction frequency):
    their presence pulls toward human; their absence is neutral, never a
    penalty — so formal/clean writing is not falsely flagged.
"""

import re
import statistics

# --- Weights (sum to 1.0; max single weight 0.25 => no metric dominates) -----
WEIGHT_VARIANCE = 0.25       # sentence-length variation (coefficient of variation)
WEIGHT_DIVERSITY = 0.25      # lexical diversity (moving-average TTR)
WEIGHT_PUNCTUATION = 0.20    # variety of punctuation used
WEIGHT_CONTRACTION = 0.20    # frequency of contractions
WEIGHT_AVG_LENGTH = 0.10     # average sentence length (weakest cue -> lowest weight)

# --- Tuning constants --------------------------------------------------------
# Inputs shorter than this carry no statistical signal -> return neutral 0.5.
MIN_WORDS = 8

# Metric 1 — sentence-length variation, measured as coefficient of variation
# (CV = stddev / mean), which is scale-free. Human prose is "bursty": CV is
# typically >= ~0.30. Machine-uniform prose has CV near zero.
CV_HUMAN = 0.30   # CV at/above this -> fully human-like on this axis
CV_AI = 0.15      # CV at/below this -> fully AI-like

# Metric 2 — lexical diversity via MATTR (moving-average type-token ratio over a
# fixed window, so length does not bias the result). High diversity = human.
MATTR_WINDOW = 25
DIVERSITY_HUMAN = 0.80   # MATTR at/above this -> fully human-like
DIVERSITY_AI = 0.40      # MATTR at/below this -> fully AI-like

# Metric 3 — average sentence length (words). Mild, low-weight cue: longer
# averages lean AI, but length alone is NOT strong evidence of AI authorship.
AVG_LEN_HUMAN = 12.0   # at/below this -> human-like
AVG_LEN_AI = 26.0      # at/above this -> AI-like

# Metric 4 — punctuation variety. We count how many distinct punctuation
# *categories* appear. Using several is a positive human signal; using few is
# simply uninformative (neutral), never a penalty.
PUNCT_HUMAN_CATEGORIES = 3

# Metric 5 — contraction frequency (contractions / words). Contractions are a
# positive human signal; their absence is neutral (formal humans omit them too).
CONTRACTION_HUMAN_RATE = 0.02

# Punctuation grouped into categories; humans tend to mix several of these.
_PUNCT_CATEGORIES = [
    r'[,]',          # comma
    r'[;:]',         # semicolon / colon
    r'[—–]|\s-\s',   # em/en dashes or spaced hyphens (not intra-word hyphens)
    r'[()\[\]]',     # brackets / parentheses
    r'["“”\'‘’]',    # quotation marks
    r'[!?]',         # exclamation / question
]


def _clamp(value, low=0.0, high=1.0):
    """Constrain a value to the [low, high] range."""
    return max(low, min(high, value))


def _split_sentences(text):
    """Split text into non-empty sentences on ., ! and ? boundaries."""
    parts = re.split(r'[.!?]+', text)
    return [p.strip() for p in parts if p.strip()]


def _tokenize_words(text):
    """Return lowercased word tokens so 'The' and 'the' count as one type."""
    return re.findall(r"\b\w+\b", text.lower())


def _moving_average_ttr(words, window=MATTR_WINDOW):
    """Moving-average type-token ratio: mean TTR over sliding word windows.

    For texts shorter than the window this is just the plain TTR. Averaging
    over fixed-size windows removes the length bias of raw TTR (raw TTR always
    falls as a text gets longer, which would wrongly make long human prose look
    repetitive/AI-like).
    """
    n = len(words)
    if n <= window:
        return len(set(words)) / n
    ratios = [
        len(set(words[i:i + window])) / window
        for i in range(n - window + 1)
    ]
    return sum(ratios) / len(ratios)


def _count_contractions(text):
    """Count contraction tokens such as don't, it's, I'm (straight or curly ')."""
    return len(re.findall(r"\b\w+['’]\w+\b", text))


def _count_punctuation_categories(text):
    """Count how many distinct punctuation categories appear in the text."""
    return sum(1 for pattern in _PUNCT_CATEGORIES if re.search(pattern, text))


def stylometric_signal(text):
    """Score text using stylometric heuristics only (no LLM).

    Returns:
        {
            "score": float,   # 0.0 human-like .. 1.0 AI-like
            "metrics": {
                "sentence_variance": float,        # variance of sentence lengths (words^2)
                "average_sentence_length": float,  # mean words per sentence
                "type_token_ratio": float,         # raw unique/total words (reported)
                "moving_average_ttr": float,       # length-robust TTR used for scoring
                "punctuation_categories": int,     # distinct punctuation categories
                "contraction_rate": float          # contractions / words
            }
        }

    Very short inputs (fewer than MIN_WORDS words) return a neutral 0.5: there
    is not enough text to analyse, so we report uncertainty rather than guess.
    """
    words = _tokenize_words(text)
    sentences = _split_sentences(text)
    word_count = len(words)

    # Guard: too little text to analyse -> neutral, not a fabricated score.
    if word_count < MIN_WORDS or not sentences:
        return {
            "score": 0.5,
            "metrics": {
                "sentence_variance": 0.0,
                "average_sentence_length": float(word_count),
                "type_token_ratio": 0.0,
                "moving_average_ttr": 0.0,
                "punctuation_categories": 0,
                "contraction_rate": 0.0,
            },
        }

    sentence_lengths = [len(_tokenize_words(s)) for s in sentences]
    average_sentence_length = statistics.mean(sentence_lengths)
    sentence_variance = (
        statistics.pvariance(sentence_lengths) if len(sentence_lengths) > 1 else 0.0
    )

    # --- Metric 1: sentence-length variation (coefficient of variation) ---
    if len(sentence_lengths) < 2 or average_sentence_length == 0:
        # Only one sentence -> variance is undefined as a *style* cue. Stay
        # neutral instead of mistaking "no data" for "perfectly uniform".
        variance_ai = 0.5
    else:
        cv = (sentence_variance ** 0.5) / average_sentence_length
        variance_ai = _clamp((CV_HUMAN - cv) / (CV_HUMAN - CV_AI))

    # --- Metric 2: lexical diversity (length-robust MATTR) ---
    mattr = _moving_average_ttr(words)
    diversity_ai = _clamp(
        (DIVERSITY_HUMAN - mattr) / (DIVERSITY_HUMAN - DIVERSITY_AI)
    )

    # --- Metric 3: average sentence length (gentle, low weight) ---
    avg_len_ai = _clamp(
        (average_sentence_length - AVG_LEN_HUMAN) / (AVG_LEN_AI - AVG_LEN_HUMAN)
    )

    # --- Metric 4: punctuation variety (human-positive: absence is neutral) ---
    punct_categories = _count_punctuation_categories(text)
    punctuation_ai = 0.5 * (1.0 - min(punct_categories / PUNCT_HUMAN_CATEGORIES, 1.0))

    # --- Metric 5: contraction frequency (human-positive: absence is neutral) ---
    contraction_rate = _count_contractions(text) / word_count
    contraction_ai = 0.5 * (1.0 - min(contraction_rate / CONTRACTION_HUMAN_RATE, 1.0))

    score = (
        WEIGHT_VARIANCE * variance_ai
        + WEIGHT_DIVERSITY * diversity_ai
        + WEIGHT_AVG_LENGTH * avg_len_ai
        + WEIGHT_PUNCTUATION * punctuation_ai
        + WEIGHT_CONTRACTION * contraction_ai
    )

    return {
        "score": round(_clamp(score), 4),
        "metrics": {
            "sentence_variance": round(sentence_variance, 4),
            "average_sentence_length": round(average_sentence_length, 4),
            "type_token_ratio": round(len(set(words)) / word_count, 4),
            "moving_average_ttr": round(mattr, 4),
            "punctuation_categories": punct_categories,
            "contraction_rate": round(contraction_rate, 4),
        },
    }
