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
