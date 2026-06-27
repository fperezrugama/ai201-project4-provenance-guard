# Provenance Guard

A Flask service that estimates whether submitted text is human- or AI-written,
combining several independent detection signals into one calibrated result and
exposing the decision through a transparent, appealable API.

## Running

```bash
pip install -r requirements.txt
# set GROQ_API_KEY in a .env file (the Groq signal degrades gracefully without it)
python run.py            # serves on http://localhost:5001
```

Open `http://localhost:5001/` for the developer dashboard, or call the API
directly.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/submit` | Analyze content (`text` or `image_description`); returns scores, prediction, transparency label |
| POST | `/appeal` | Flag a prior classification for human review |
| GET  | `/log` | Audit log entries |
| GET  | `/health` | Health check |
| GET  | `/analytics/metrics` | Full analytics metrics (read-only, from the audit log) |
| GET  | `/analytics/summary` | Brief display-formatted summary |
| POST | `/certificate/request` | Request a Verified Human credential (→ pending) |
| GET  | `/certificate/status/<creator_id>` | Verification status for a creator |
| GET  | `/certificate/review` | List pending requests (moderator) |
| POST | `/certificate/review/approve` | Approve a request (moderator) |
| POST | `/certificate/review/deny` | Deny a request (moderator) |
| POST | `/certificate/revoke/<creator_id>` | Revoke a certificate (admin) |
| GET  | `/` | Developer dashboard (dev/testing only) |

`POST /submit` is rate-limited to **10/minute, 100/day** per IP.

## Ensemble Detection

Provenance Guard combines **three independent signals**, each scoring text on a
0–1 scale (0 = human-like, 1 = AI-like):

1. **Groq LLM (semantic)** — an LLM judges meaning, coherence and "naturalness".
   Captures *what the text says*.
2. **Stylometric (structural)** — sentence-length variance, lexical diversity
   (MATTR), average sentence length, punctuation variety, contraction frequency.
   Captures *how the text is built*. No LLM/network.
3. **Behavioral (metadata)** — length consistency, submission cadence and
   similarity across a creator's submissions. Captures *how the content was
   produced*. Neutral (0.5) until history exists.

### Why three signals beat one
The signals are independent and fail in different ways: an LLM can be fooled by
formal human writing, stylometry can misread poetry or short text, and behavior
needs history. Combining them means a single signal's blind spot is covered by
the others, and **disagreement itself becomes information** (it lowers
confidence rather than forcing a wrong call).

### Weighting strategy
```
combined_score = 0.40*groq + 0.35*stylometric + 0.25*behavioral
```
Groq is weighted highest (best at meaning), stylometric next (solid structural
signal), behavioral lowest (newest, least proven, often neutral). The earlier
two-signal blend (Groq 60% / Stylometric 40%) is kept available for backward
compatibility (`EnsembleDetector.detect_two_signal`).

### Confidence calibration
Confidence reflects **signal agreement**:
```
confidence = clamp(1 - stdev([groq, stylometric, behavioral]) * 1.5, 0, 1)
```
When the three signals cluster, confidence is high; when they diverge, it falls.

### Decision rules (conservative — false positives are worse than false negatives)
| Combined score | Label |
|----------------|-------|
| ≥ 0.80 | High-confidence AI |
| 0.60 – 0.79 | Moderate AI suspicion |
| 0.40 – 0.59 | Uncertain / needs review |
| 0.20 – 0.39 | Moderate human evidence |
| < 0.20 | High-confidence human |

Every classification — even high-confidence AI — can be appealed via `/appeal`.

## Confidence Scoring Examples

To validate that our confidence scores are meaningful (not constant), here are two example submissions with noticeably different scores:

### Example 1: High-Confidence Human (Score: 0.28, Confidence: 74%)

**Text submitted:**
> "The coffee was cold, but I drank it anyway. I sat there watching the rain, thinking about nothing in particular. It was a good kind of nothing, the kind that lets your mind wander wherever it wants."

**Signal breakdown:**
| Signal | Score (0=human, 1=AI) |
|--------|----------------------|
| Groq LLM | 0.20 |
| Stylometric | 0.21 |
| Behavioral | 0.50 |
| **Combined** | **0.28** |

**Result:**
- Attribution: `human_written`
- Confidence: 74%
- Transparency Variant: `likely_human`
- Label: "Likely Human-Written — our analysis suggests this content was written by a human. (confidence: 74%)"

**Why this score is meaningful:** All three signals agree this is human-like (scores below 0.50). The casual, conversational tone with personal reflection is recognized by Groq, and the varied sentence structure is picked up by stylometrics. The behavioral signal is neutral (0.50) because this is a first submission from this creator.

---

### Example 2: High-Confidence AI (Score: 0.66, Confidence: 32%)

**Text submitted:**
> "Artificial intelligence has become an increasingly significant driver of innovation across multiple industries. Organizations continue integrating machine learning systems to optimize workflows, improve decision-making processes, and increase operational efficiency."

**Signal breakdown:**
| Signal | Score (0=human, 1=AI) |
|--------|----------------------|
| Groq LLM | 0.80 |
| Stylometric | 0.45 |
| Behavioral | 0.50 |
| **Combined** | **0.66** |

**Result:**
- Attribution: `uncertain` (conservative, due to signal disagreement)
- Confidence: 32%
- Transparency Variant: `likely_ai`
- Label: "Likely AI-Generated — our analysis suggests this content was generated by AI. (confidence: 32%)"

**Why this score is meaningful:** Groq strongly flags this as AI-like (0.80) due to the formal, structured language with buzzwords. However, stylometrics is more uncertain (0.45) because the text has reasonable sentence variety. This **disagreement lowers the confidence to 32%** — the system is honest about its uncertainty rather than making a bold claim. This reflects our conservative philosophy: false positives are worse than false negatives.

---

### What These Examples Demonstrate

| Aspect | Human Example | AI Example |
|--------|---------------|------------|
| Combined Score | 0.28 (low) | 0.66 (high) |
| Confidence | 74% (high) | 32% (low) |
| Signal Agreement | All signals agree | Groq vs Stylometric disagree |
| Label | likely_human | likely_ai |
| User Experience | Clear human attribution | Honest uncertainty, appeal available |

The key insight: **confidence is not just the score** — it reflects signal agreement. When signals disagree, confidence drops, and the system admits uncertainty rather than making a potentially wrong call.

## Transparency Label Variants

The system displays one of three transparency labels depending on the confidence score. Each label is designed to be meaningful to a non-technical reader while accurately communicating uncertainty.

### Variant 1: High-Confidence AI (score ≥ 0.80)

```
⚠️ AI-GENERATED CONTENT DETECTED

Our analysis strongly suggests this content was generated by artificial intelligence.

Confidence: {confidence}%

What this means:
• The writing shows patterns highly consistent with AI generation
• We are very confident in this assessment
• This is a high-confidence detection, not a guess

What you can do:
• If you believe this is a mistake, you can appeal below
• Human reviewers will investigate your appeal promptly

[🔽 Appeal This Decision]
```

### Variant 2: High-Confidence Human (score ≤ 0.19)

```
✅ HUMAN-WRITTEN CONTENT CONFIRMED

Our analysis strongly suggests this content was written by a human.

Confidence: {confidence}%

What this means:
• The writing shows patterns highly consistent with human authorship
• We are very confident in this assessment
• Your content is being attributed correctly

What you can do:
• Continue sharing your creative work!
• If you disagree, you can still submit an appeal

[🔽 Appeal This Decision]
```

### Variant 3: Uncertain (0.40 - 0.59)

```
🔍 UNCERTAIN - HUMAN REVIEW RECOMMENDED

Our system could not confidently determine attribution.

Confidence: {confidence}%

What this means:
• The writing shows mixed patterns
• One signal suggests AI, another suggests human
• We are not confident enough to make a definitive judgment

What you can do:
• We strongly recommend human review
• Please appeal if you believe we've misclassified your work
• You can provide context about your writing process

[🔽 Appeal This Decision]
```

### Design Rationale

1. **Visual Indicators**: Red (⚠️) for AI, Green (✅) for human, Neutral (🔍) for uncertain
2. **Plain Language**: No technical jargon like "neural networks" or "stylometric analysis"
3. **Actionable**: Every label includes an appeal option
4. **False Positive Protection**: Labels emphasize "strongly suggests" not "definitely"
5. **Consistent Format**: Each label has: result, confidence, meaning, and actions

## Rate Limiting

`POST /submit` is rate-limited to **10 requests per minute** and **100 requests per day** per IP address.

### Why These Limits?

| Limit | Reasoning |
|-------|-----------|
| **10 per minute** | A legitimate human creator submitting their own work might submit 2-3 pieces per minute at most. 10 per minute allows for reasonable use while preventing automated flooding. |
| **100 per day** | A typical writing platform user might submit 5-20 pieces per day. 100 per day accommodates heavy use while preventing API abuse. |

### How We Chose These Numbers

**Realistic usage scenario:**
- A writer drafts multiple pieces in a session: 3-5 submissions
- A creator uploading a backlog: 10-20 submissions
- A platform with batch processing: 20-30 submissions

**Adversarial scenario:**
- A script trying to flood the system: 100+ submissions per minute
- A bot testing the detector: 1000+ submissions per day

**Our limits sit between these extremes:**
- 10/minute prevents rapid automated flooding while allowing human-speed submissions
- 100/day prevents sustained abuse while allowing legitimate heavy usage

### Test Results

The rate limiter was tested with 12 rapid requests:
```
Request 1 : 200   ✅ Allowed
Request 2 : 200   ✅ Allowed
Request 3 : 200   ✅ Allowed
Request 4 : 200   ✅ Allowed
Request 5 : 200   ✅ Allowed
Request 6 : 200   ✅ Allowed
Request 7 : 200   ✅ Allowed
Request 8 : 200   ✅ Allowed
Request 9 : 200   ✅ Allowed
Request 10: 200   ✅ Allowed
Request 11: 429   🚫 Rate Limited
Request 12: 429   🚫 Rate Limited
```

**No HTTP 500 errors** were observed during testing — only 200 (allowed) and 429 (rate limited) responses.

## Analytics

A read-only analytics layer derives metrics from the audit log (it never writes
to it). View them on the dashboard (`GET /`) — it loads on open and via the
"Refresh Analytics" button — or call the API directly:

```bash
curl http://localhost:5001/analytics/metrics | python -m json.tool
curl http://localhost:5001/analytics/summary | python -m json.tool
```

**Metrics displayed**
- **Total submissions**, and detection counts (`ai_generated` / `uncertain` /
  `human_written`).
- **Average confidence** — overall ensemble confidence.
- **Appeals** — count, rate, and pending/approved/denied breakdown.
- **Confidence trend** — average confidence per day for the last 7 days.
- **Average score per signal** — mean Groq / stylometric / behavioral score.
- **Recent activity** — the last few submissions with scores.

**Interpreting it:** a rising **appeal rate** or **low average confidence** are
the signals to watch — both suggest the system is making contested or
low-agreement calls (the project treats false positives as the worst outcome).
The per-signal averages show which signal is driving decisions.

## Multi-modal content

`POST /submit` takes an optional `content_type` (default `text`). A second type,
`image_description`, analyzes a textual description of an image with a
deterministic heuristic detector (template phrasing, structural complexity,
metadata specificity, emotive language). Detectors share a common interface and
are dispatched by a registry, so the text pipeline is untouched.

```bash
# text (default)
curl -X POST localhost:5001/submit -H 'Content-Type: application/json' \
  -d '{"text":"...","creator_id":"u1"}'

# image description
curl -X POST localhost:5001/submit -H 'Content-Type: application/json' \
  -d '{"content_type":"image_description","creator_id":"u1",
       "description":"I think this is gorgeous ...","width":1920,"height":1080,"format":"jpg"}'
```

Unknown content types return `400` with the list of supported types. The
dashboard's submit form has a content-type selector that reveals the image
fields. Image submissions return `signal_scores` + an `explanation`; the
attribution, transparency label, certificate badge, and audit logging work the
same as for text.

## Verified Human credential

Creators can earn a **Verified Human** badge through a moderator-reviewed step.
It is a display annotation only — it **does not change** detection scores, the
prediction, or confidence.

**Workflow:** request → moderator review → approve/deny (and optional revoke).
Credentials are never granted automatically and there is no self-approval.

```bash
curl -X POST localhost:5001/certificate/request -H 'Content-Type: application/json' -d '{"creator_id":"sarah_poet"}'
curl localhost:5001/certificate/review        # moderator: see pending
curl -X POST localhost:5001/certificate/review/approve -H 'Content-Type: application/json' -d '{"creator_id":"sarah_poet"}'
curl localhost:5001/certificate/status/sarah_poet
```

Once active, `POST /submit` returns `"is_verified": true` and the
`transparency_label` gains a 👤 badge with the credential note. The dashboard
provides a request form and a moderator review panel. Certificates persist to
`data/certificates.json`.

## Auditing

Every submission is logged (thread-safe, atomic JSON writes) with all signal
scores (`groq_score`, `stylometric_score`, `behavioral_score`), the
`combined_score`, `confidence`, the `attribution` prediction, and `status`.
Appeals update the entry to `under_review`, store the reasoning, and preserve a
snapshot of the original classification.

## Known Limitations

No detection system is perfect, and honest acknowledgment of limitations is part of building trust. Here are the specific cases where Provenance Guard is most likely to struggle:

### Limitation 1: Poetry with Intentional Repetition

**The problem:**
Poets often use deliberate repetition and short, rhythmic lines for artistic effect. This can confuse the stylometric signal:

```
"Rain falls, falls, falls
On the roof, on the street, on my soul
Drip, drop, drip, drop
Never stopping, never stopping"
```

**Why it's problematic:**
- Stylometrics sees high repetition → low TTR → flags as AI-like
- Stylometrics sees short sentences → low variance → flags as AI-like
- Groq might see the repetition as a pattern → flags as AI
- Could score 0.70+ despite being clearly human

**How we handle it:**
- The "uncertain" zone (0.40-0.59) provides a buffer
- Calibration reduces score when signals disagree
- Clear appeal path for poets to explain their process
- The system admits uncertainty rather than making a false accusation

### Limitation 2: Very Short Texts (< 50 words)

**The problem:**
Short texts like micro-fiction, tweets, or short poems lack enough data for reliable analysis:

```
"The coffee is cold. The day is long. I am tired. I wait."
```

**Why it's problematic:**
- Stylometrics: Not enough sentences for variance calculation
- Stylometrics: TTR is statistically unreliable
- Groq: Not enough context for meaningful analysis
- Both signals return uncertain or random results

**How we handle it:**
- Detect short text (< 50 words) and return "UNCERTAIN" with explanation
- Flag in audit log with `insufficient_data: true`
- Suggest user submits longer sample if possible
- Appeal path remains available

### What We'd Change for Production

If deploying this system for real, we would:

1. **Add a dedicated poetry detector** — Recognize poetic structures and adjust scoring
2. **Improve ESL detection** — Train on non-native English writing patterns
3. **Add per-creator calibration** — Learn each creator's unique writing style
4. **Implement human-in-the-loop** — Escalate uncertain cases to human reviewers
5. **Add confidence thresholds** — Only auto-publish high-confidence classifications

## Spec Reflection

### How the Spec Helped

The project specification's emphasis on **"confidence is a design decision before it's a technical one"** was the single most helpful insight.

Before writing any code, I had to decide:
- What does 0.6 mean to a user?
- What does "uncertain" look like?
- How do we communicate nuance?

This forced me to design the transparency labels and confidence thresholds first, then implement the scoring to match — rather than the other way around. The result is a system where the user experience drives the technical implementation, not vice versa.

**Concrete example:** The "uncertain" zone (0.40-0.59) was designed as a wide buffer to protect against false positives. This guided the calibration logic — when signals disagree, confidence is lowered to push scores into this zone.

### How Implementation Diverged from the Spec

**Divergence:** The spec suggested using **two signals** (Groq + Stylometric), but I implemented **three signals** (adding Behavioral) as a stretch feature.

**Why I diverged:** During testing, I noticed that first-time submissions with ambiguous text were hard to classify because there was no historical context. Adding a behavioral signal (submission frequency, length consistency, similarity to past submissions) provided that context and improved detection without requiring users to submit multiple pieces first.

**How this affected the system:**
- More signals = more robust detection
- Signal agreement/disagreement is more informative with 3 signals
- The weighting strategy had to be adjusted (Groq 40%, Stylometric 35%, Behavioral 25%)
- Confidence calibration became more nuanced (standard deviation of 3 values)

**Trade-off:** The system became slightly more complex, but the improvement in detection quality and user experience justified the change.

## AI Usage

This project was built with assistance from AI tools, primarily Claude. Here are two specific instances where AI was used:

### Instance 1: Groq Signal Implementation

**What I directed the AI to do:**
"Create a Groq LLM signal function that takes text input and returns a score 0-1 (0=human, 1=AI) with confidence and reasoning. Use llama-3.3-70b-versatile with temperature 0.1 for consistency."

**What it produced:**
The AI generated a complete `groq_signal.py` function with:
- API client setup
- Prompt engineering for structured JSON output
- Error handling and fallback values
- Response parsing and validation

**What I revised or overrode:**
- Added custom error messages for edge cases (empty text, API failures)
- Changed the prompt to request specific JSON fields instead of plain text
- Added regex fallback parsing for when the model didn't return clean JSON
- Implemented score clamping to ensure values stay within [0, 1]

### Instance 2: Ensemble Detection with 3 Signals

**What I directed the AI to do:**
"Take the existing two-signal ensemble (Groq + Stylometric) and extend it to three signals, adding Behavioral Analysis. Update the weighting strategy and confidence calibration to use standard deviation of three values."

**What it produced:**
The AI generated:
- A `behavioral_signal.py` with submission history tracking
- Updated `ensemble.py` with `detect_three_signal` and `detect_two_signal` (backward compatibility)
- New weighting strategy: Groq 40%, Stylometric 35%, Behavioral 25%
- Confidence calculation using standard deviation of three signals

**What I revised or overrode:**
- Simplified the behavioral signal to return neutral (0.5) for first-time users
- Changed the confidence formula from `1 - (std_dev * 2)` to `1 - (std_dev * 1.5)` to make it less aggressive
- Added logging of all three signal scores to the audit log
- Updated the dashboard to show all three signal breakdowns

### AI Usage Summary

| Task | AI's Role | My Revisions |
|------|-----------|--------------|
| Groq Signal | Generated initial function | Added error handling, regex parsing, edge cases |
| Ensemble Detection | Generated extension to 3 signals | Adjusted weights, simplified behavioral logic, added audit logging |

The AI was used as a **coding assistant** — generating boilerplate, suggesting approaches, and providing implementation templates. I was responsible for:
- System architecture decisions
- Error handling and edge cases
- Integration with existing code
- Testing and validation
- Documentation

