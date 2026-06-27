# Provenance Guard - Planning Document

##  Architecture Narrative - Planning Document

A creator submits their text through the POST /submit endpoint.

The submission is first checked against rate limits - if they've submitted too 
many times, they get a 429 error immediately.

If they're under the limit, the submission passes through our detection pipeline:
1. The text goes to Signal 1 (Groq LLM), which returns a score 0-1 
   (0=human, 1=AI-like)
2. Simultaneously, the text goes to Signal 2 (Stylometric Heuristics), 
   which also returns a score 0-1 based on structural patterns

Both scores are collected by the Ensemble Aggregator, which combines them 
using a weighted average (Groq: 60%, Stylometric: 40%).

The combined score goes to the Confidence Calibrator, which adjusts for 
signal agreement - if both signals agree, confidence increases; if they 
disagree, it decreases.

The calibrated score is passed to the Label Generator, which maps it to one 
of three transparency labels:
- 0.8-1.0 → "Likely AI-Generated"
- 0.4-0.79 → "Uncertain - Human Review Recommended"
- 0.0-0.39 → "Likely Human-Written"

The system records everything in the Audit Log: the raw text, both signal 
scores, the combined score, the final label, timestamp, and creator ID.

Finally, the response is returned to the creator containing:
- attribution result (human/ai/uncertain)
- confidence score
- transparency label text
- content_id for future appeals

## Detection signals

### Signal 1: Groq LLM Assessment
What it measures:
Semantic coherence, narrative flow, creative patterns, contextual appropriateness, and overall "naturalness" of the writing. It evaluates whether the text reads like something a human would naturally write.

Why it differs between human and AI:

* Human writing tends to have: authentic emotional resonance, unique perspectives, subtle contradictions, cultural references, and organic thought progression

* AI writing tends to have: consistent style throughout, perfect grammar, predictable patterns, over-explanation, and a neutral emotional tone

What it CAN'T capture:

* Very formal human writing (academic papers, legal documents) might look AI-like

* Creative human writing that deliberately mimics AI style

* Texts in languages other than English

* Short texts (< 50 words) lack enough context

* It can be biased - sometimes flags non-native English speakers' writing as AI

### Signal 2: Stylometric Heuristics
What it measures:
Structural and statistical properties of the text including:

* Sentence length variance: How much sentence lengths vary (human writing varies more)

* Type-Token Ratio (TTR): Vocabulary diversity (human writing has more unique words)

* Punctuation density: Use of varied punctuation (human writing uses more variety)

Why it differs between human and AI:

* Human writing has: inconsistent sentence lengths, wider vocabulary variety, creative punctuation usage, and occasional "imperfections" (sentence fragments, run-ons)

* AI writing has: uniform sentence lengths, repetitive vocabulary, proper but limited punctuation, and perfect structure

What it CAN'T capture:

* Very short texts (< 100 words) lack statistical significance

* Poetry can confuse the metrics (short sentences, unusual vocabulary)

* Purposefully edited text that mimics human patterns

* The semantic meaning of words (only measures structure)

* Different writing styles (some humans naturally write more uniformly)

## False Positive Scenario & Handling

Let's trace what happens when a human writer is falsely flagged as AI:

Scenario:
Sarah, a poet, submits her work. She uses short, rhythmic sentences and repetitive structures for effect. The stylometric signal flags it as AI-like because of low variance and high repetition. The Groq signal is uncertain (0.55).

Submission Flow:
1. Sarah submits text → Groq score: 0.55 (uncertain), Stylometric: 0.85 (AI-like)
2. Ensemble combines: (0.55 × 0.6) + (0.85 × 0.4) = 0.67
3. Confidence Calibrator sees disagreement → reduces confidence: 0.61
4. Label Generator maps 0.61 → "Uncertain - Human Review Recommended"

The system doesn't claim she's definitively AI - it admits uncertainty!

What Sarah Sees:
🔍 Uncertain - Human Review Recommended
Confidence: 61%

Our system could not confidently determine attribution. 
This content shows some patterns associated with AI generation, 
but we aren't certain. Human reviewers will look at this.

[Appeal This Decision]

How She Appeals:
1. Sarah clicks "Appeal This Decision"

2. Provides reasoning: "I'm a poet - the repetition is intentional for rhythm"

3. Content status changes to "Under Review"

4. A human reviewer (or future system) can examine the case

5. The appeal is logged alongside the original decision

Why This Design Helps:
* The confidence score is calibrated downward when signals disagree, protecting against false positives

* The label says "uncertain" not "AI-generated" - admitting we might be wrong

* The appeal path is clear - creators can easily contest

## API Surface Design

### Endpoint 1: POST /submit

Purpose: Submit content for attribution analysis

Request Body:

{
    "text": "The poem or text content to analyze",
    "creator_id": "sarah_poet_123",
    "content_type": "text",  // optional, for future multi-modal support
    "title": "My Poem"       // optional, for analytics
}
Response (200 OK):

{
    "content_id": "abc-123-def-456",
    "attribution": "uncertain",
    "confidence": 0.61,
    "label": "🔍 Uncertain - Human Review Recommended",
    "label_variant": "uncertain",
    "timestamp": "2026-06-25T10:30:00Z",
    "appeal_available": true
}

Error Responses:

* 429: "Rate limit exceeded. Try again in X minutes"
* 400: "Invalid input - text field required"
* 503: "Service temporarily unavailable"

### Endpoint 2: POST /appeal
Purpose: Contest a classification decision

Request Body:
{
    "content_id": "abc-123-def-456",
    "creator_id": "sarah_poet_123",
    "reasoning": "I'm a poet - the repetition is intentional for rhythm"
}

Response (200 OK):

{
    "appeal_id": "app-789-xyz-012",
    "content_id": "abc-123-def-456",
    "status": "under_review",
    "timestamp": "2026-06-25T10:35:00Z",
    "message": "Appeal submitted successfully. A reviewer will examine your content."
}

### Endpoint 3: GET /log (For Development/Documentation)

Purpose: Retrieve audit log entries

Response:

{
    "entries": [
        {
            "content_id": "abc-123-def-456",
            "creator_id": "sarah_poet_123",
            "timestamp": "2026-06-25T10:30:00Z",
            "attribution": "uncertain",
            "confidence": 0.61,
            "groq_score": 0.55,
            "stylometric_score": 0.85,
            "status": "classified"
        }
    ],
    "count": 10
}

### Endpoint 4: GET /analytics (Stretch Feature)
Purpose: Provide dashboard metrics

Response:

{
    "total_submissions": 150,
    "detection_patterns": {
        "human_high_confidence": 45,
        "ai_high_confidence": 60,
        "uncertain": 45
    },
    "appeal_rate": 0.18,
    "avg_confidence": 0.62,
    "signal_correlation": 0.73
}

## Step 5: Architecture Diagram

┌─────────────────────────────────────────────────────────────────────────────┐
│                          PROVENANCE GUARD SYSTEM                           │
└─────────────────────────────────────────────────────────────────────────────┘

                               ┌──────────────────┐
                               │   Client/User    │
                               └────────┬─────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SUBMISSION FLOW                                   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    POST /submit                                     │   │
│  │  Input: {text, creator_id}                                         │   │
│  └──────────────┬──────────────────────────────────────────────────────┘   │
│                 │                                                          │
│                 ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Rate Limiter                                    │   │
│  │  Check: 10 per minute, 100 per day                                 │   │
│  │  If exceeded → 429 Too Many Requests                                │   │
│  └──────────────┬──────────────────────────────────────────────────────┘   │
│                 │                                                          │
│                 ▼                                                          │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐       │
│  │    Signal 1: Groq LLM       │  │  Signal 2: Stylometric        │       │
│  │  ┌────────────────────────┐ │  │  ┌────────────────────────┐  │       │
│  │  │ Semantic Assessment    │ │  │  │ Statistical Analysis   │  │       │
│  │  │ 0-1 Score (AI-like)   │ │  │  │ 0-1 Score (AI-like)    │  │       │
│  │  └────────────┬───────────┘ │  │  └────────────┬───────────┘  │       │
│  └───────────────┼──────────────┘  └───────────────┼──────────────┘       │
│                  │                                  │                       │
│                  └──────────────┬───────────────────┘                       │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   Ensemble Aggregator                               │   │
│  │  Weighted Average: (Groq × 0.6) + (Stylometric × 0.4)              │   │
│  └──────────────────────────┬──────────────────────────────────────────┘   │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                Confidence Calibrator                                │   │
│  │  Adjust based on signal agreement:                                  │   │
│  │  If signals agree → ↑ confidence                                    │   │
│  │  If signals disagree → ↓ confidence                                 │   │
│  └──────────────────────────┬──────────────────────────────────────────┘   │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  Label Generator                                    │   │
│  │  0.8-1.0 → "Likely AI-Generated"                                    │   │
│  │  0.4-0.79 → "Uncertain"                                             │   │
│  │  0.0-0.39 → "Likely Human-Written"                                  │   │
│  └──────────────────────────┬──────────────────────────────────────────┘   │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Audit Log                                      │   │
│  │  Store: content_id, creator_id, scores, label, timestamp           │   │
│  └──────────────────────────┬──────────────────────────────────────────┘   │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Response to Client                               │   │
│  │  {content_id, attribution, confidence, label}                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

                               ┌──────────────────┐
                               │   Client/User    │
                               └────────┬─────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           APPEAL FLOW                                       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    POST /appeal                                     │   │
│  │  Input: {content_id, reasoning}                                    │   │
│  └──────────────────────────┬──────────────────────────────────────────┘   │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  Appeal Processor                                   │   │
│  │  1. Validate content_id exists                                     │   │
│  │  2. Store reasoning                                                │   │
│  │  3. Update status → "under_review"                                 │   │
│  └──────────────────────────┬──────────────────────────────────────────┘   │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Audit Log                                      │   │
│  │  Append: {content_id, appeal_reasoning, status, timestamp}         │   │
│  └──────────────────────────┬──────────────────────────────────────────┘   │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Response to Client                               │   │
│  │  {appeal_id, content_id, status: "under_review"}                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────────┐
                              │   Admin/Reviewer │
                              └────────┬─────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ANALYTICS FLOW (Stretch)                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    GET /analytics                                   │   │
│  └──────────────────────────┬──────────────────────────────────────────┘   │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  Analytics Service                                  │   │
│  │  1. Query audit log                                                │   │
│  │  2. Calculate metrics:                                             │   │
│  │     - Detection patterns (counts)                                  │   │
│  │     - Appeal rates                                                 │   │
│  │     - Average confidence                                           │   │
│  │     - Signal correlation                                           │   │
│  └──────────────────────────┬──────────────────────────────────────────┘   │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Response to Client                               │   │
│  │  {metrics: detection_patterns, appeal_rate, avg_confidence, ...}   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

## Uncertainty Representation

### What a Confidence Score Means

Our confidence score (0-1) represents the system's certainty about whether content is AI-generated, calibrated to be meaningful for non-technical users:

| Score Range | Label | Meaning | User Experience |
|-------------|-------|---------|-----------------|
| 0.80 - 1.00 | High-Confidence AI | Very strong patterns indicate AI generation | Clear warning label |
| 0.60 - 0.79 | Moderate AI Suspicion | Some AI-like patterns but not conclusive | Cautious label with explanation |
| 0.40 - 0.59 | **UNCERTAIN** | System genuinely cannot determine | Neutral label, recommends human review |
| 0.20 - 0.39 | Moderate Human Evidence | Some human-like patterns but not conclusive | Cautious human label |
| 0.00 - 0.19 | High-Confidence Human | Very strong patterns indicate human writing | Confident human label |

### Why 0.5 Isn't Just "Neutral"

A score of 0.5 doesn't mean "50/50 chance" - it means **"our system is genuinely uncertain and can't make a reliable determination."**

**Example 1: 0.5 with signal agreement**
- Groq: 0.52, Stylometric: 0.48
- Both signals are uncertain/neutral
- → Genuinely ambiguous content
- Label: UNCERTAIN

**Example 2: 0.5 with signal disagreement**
- Groq: 0.85 (AI), Stylometric: 0.15 (Human)
- Signals strongly disagree
- → System doesn't know which to trust
- Label: UNCERTAIN (with note about conflicting signals)

### How We Calibrate Scores

#### Step 1: Raw Ensemble Score

raw_score = (groq_score × 0.6) + (stylometric_score × 0.4)

- Groq gets higher weight (60%) because it captures semantic meaning
- Stylometric gets lower weight (40%) because it's purely structural

#### Step 2: Signal Agreement Adjustment

signal_diff = abs(groq_score - stylometric_score)
agreement_penalty = signal_diff × 0.3
calibrated_score = raw_score - agreement_penalty

- If signals agree (diff < 0.15): no penalty → higher confidence
- If signals disagree (diff > 0.30): penalty applied → lower confidence
- This prevents false positives from a single signal error

#### Step 3: LLM Confidence Factor
if groq_confidence < 0.6: # LLM is uncertain
calibrated_score = calibrated_score × 0.9 # 10% reduction

- If Groq says "I'm not sure," we trust it less
- This adds another layer of uncertainty handling

#### Step 4: Final Clamping
final_score = max(0, min(1, calibrated_score)) # Keep between 0-1


### Example Calibration in Action

| Scenario | Groq | Stylometric | Raw | Difference | Penalty | Final | Label |
|----------|------|-------------|-----|------------|---------|-------|-------|
| Clear AI | 0.92 | 0.88 | 0.90 | 0.04 | 0.01 | 0.89 | High AI |
| Clear Human | 0.12 | 0.08 | 0.10 | 0.04 | 0.01 | 0.09 | High Human |
| Disagreement | 0.85 | 0.25 | 0.61 | 0.60 | 0.18 | 0.43 | UNCERTAIN |
| Both Uncertain | 0.55 | 0.45 | 0.51 | 0.10 | 0.03 | 0.48 | UNCERTAIN |

### Thresholds for Label Assignment

```python
def get_label_variant(score):
    if score >= 0.80:
        return "high_ai"
    elif score >= 0.60:
        return "moderate_ai"  
    elif score >= 0.40:
        return "uncertain"
    elif score >= 0.20:
        return "moderate_human"
    else:
        return "high_human"
```
Why These Thresholds:
* 0.80 threshold: High bar for AI labeling (protects against false positives)
* 0.60-0.79 buffer: "Suspected but not certain" zone
* 0.40-0.59 uncertain zone: Wide neutral area for ambiguity
* 0.20-0.39 buffer: "Suspected human but not certain" zone
* 0.20 threshold: Low bar for human labeling (easier to prove human)

Why This Approach Prevents Binary Thinking
1. Five distinct zones (not just AI/Human)
2. Wide uncertain zone (0.40-0.59) to catch edge cases
3. Different labels at different scores (0.51 vs 0.95 look very different)
4. Calibration based on disagreement (signals fighting = uncertainty)


---

### Section: Transparency Label Design

```markdown
## Transparency Label Design

### Label Variant 1: High-Confidence AI (score ≥ 0.80)

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


### Label Variant 2: Moderate AI Suspicion (0.60 - 0.79)
⚡ AI-GENERATED CONTENT LIKELY

Our analysis suggests this content may have been AI-generated.

Confidence: {confidence}%

What this means:
• The writing shows several patterns associated with AI generation
• However, we're not completely certain
• There's a possibility this is human writing with some AI-like patterns

What you can do:
• If you believe this is a mistake, you can appeal below
• We recommend submitting additional context about your writing process

[🔽 Appeal This Decision]


### Label Variant 3: Uncertain (0.40 - 0.59)

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


### Label Variant 4: Moderate Human Evidence (0.20 - 0.39)

📝 LIKELY HUMAN-WRITTEN CONTENT

Our analysis suggests this content was written by a human.

Confidence: {confidence}%

What this means:
• The writing shows several patterns consistent with human authorship
• However, we're not completely certain
• Some AI-like patterns were detected but not strongly

What you can do:
• You can still appeal if you believe this is incorrect
• Continue creating and sharing your work

[🔽 Appeal This Decision]


### Label Variant 5: High-Confidence Human (score ≤ 0.19)
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


### Design Rationale

**1. Visual Indicators**
- ⚠️ Red warning = clear AI detection
- ⚡ Yellow warning = suspicious but not certain
- 🔍 Neutral magnifying glass = uncertain
- 📝 Blue document = likely human
- ✅ Green check = confirmed human

**2. Progressive Detail**
Each label provides:
- Clear result statement
- Confidence percentage
- Explanation of what the score means
- Actionable next steps

**3. False Positive Protection**
- Labels emphasize "strongly suggests" not "definitely"
- Even "High-Confidence AI" leaves room for appeal
- The "uncertain" label is prominent and actionable
- Consistent appeal option across all labels

**4. Non-Technical Language**
- No jargon like "neural networks" or "stylometric analysis"
- Plain English explanations
- Clear, scannable structure

**5. User Empowerment**
- Every label includes an appeal option
- Clear what the user should do next
- Reassuring tone even when flagged as AI

## Appeals Workflow

### Who Can Submit an Appeal?

- Only the **original creator** (identified by `creator_id`)
- Must match the creator_id from the original submission
- Must provide `content_id` from the original response
- No anonymous appeals (to prevent gaming)

### What Information Must They Provide?

**Required:**
```json
{
    "content_id": "abc-123-def-456",
    "creator_id": "sarah_poet_123",
    "reasoning": "I'm a poet - the repetition is intentional for rhythm"
}

```
Why We Require Reasoning:

* Helps human reviewers understand context
* Provides insight into potential edge cases
* Creates accountability
* Helps improve the system

System Actions When Appeal Received

``` python 
def process_appeal(content_id, creator_id, reasoning):
    # 1. Validate the content exists
    content = get_content(content_id)
    if not content:
        return {"error": "Content not found"}
    
    # 2. Verify creator identity
    if content['creator_id'] != creator_id:
        return {"error": "You can only appeal your own content"}
    
    # 3. Check if already appealed
    if content['status'] == 'under_review':
        return {"error": "This content is already under review"}
    
    # 4. Update content status
    content['status'] = 'under_review'
    content['appeal_reasoning'] = reasoning
    content['appeal_timestamp'] = datetime.now().isoformat()
    
    # 5. Log the appeal
    audit_log.append({
        'content_id': content_id,
        'event': 'appeal_submitted',
        'reasoning': reasoning,
        'timestamp': datetime.now().isoformat(),
        'original_decision': content['original_decision'],
        'creator_id': creator_id
    })
    
    # 6. Generate appeal ID
    appeal_id = f"app-{uuid.uuid4().hex[:12]}"
    
    return {
        'appeal_id': appeal_id,
        'status': 'under_review',
        'message': 'Appeal submitted successfully'
    }
```

Status Flow

┌─────────────┐
│  classified │  ← Initial state after submission
└──────┬──────┘
       │
       │ (creator appeals)
       ▼
┌─────────────┐
│under_review │  ← Appeal submitted, awaiting human review
└──────┬──────┘
       │
       │ (human reviewer decides)
       ▼
┌─────────────────────┐
│   human_approved    │  ← Reclassified as human
│   human_rejected    │  ← Classification confirmed as AI
│   ai_approved       │  ← Reclassified as AI
│   ai_rejected       │  ← Classification confirmed as human
└─────────────────────┘

What a Human Reviewer Sees

╔══════════════════════════════════════════════════════════════╗
║                     APPEAL REVIEW QUEUE                      ║
╚══════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────┐
│ Appeal ID: app-a1b2c3d4e5f6                                │
│ Content ID: abc-123-def-456                               │
│ Creator: sarah_poet_123                                   │
│ Original Classification: UNCERTAIN (score: 0.61)          │
│                                                           │
│ ═══ SIGNAL BREAKDOWN ═══                                 │
│ • Groq Score: 0.55                                       │
│ • Stylometric Score: 0.85                                │
│ • Signal Agreement: Disagreement                         │
│                                                           │
│ ═══ ORIGINAL CONTENT ═══                                 │
│ "Rain falls, falls, falls                               │
│  On the roof, on the street, on my soul                  │
│  Drip, drop, drip, drop                                 │
│  Never stopping, never stopping"                         │
│                                                           │
│ ═══ CREATOR'S APPEAL ═══                                 │
│ "I'm a poet - the repetition is intentional for rhythm"  │
│                                                           │
│ ═══ REVIEWER ACTIONS ═══                                 │
│ [ ] Accept Appeal → Reclassify as HUMAN                  │
│ [ ] Reject Appeal → Keep Classification                  │
│ [ ] Request More Information                             │
│ [ ] Mark as Under Review                                 │
│                                                           │
│ Review Comments:                                         │
│ __________________________________________________       │
│                                                           │
│ [Submit Decision]                                        │
└─────────────────────────────────────────────────────────────┘

``` json
{
    "appeal_id": "app-a1b2c3d4e5f6",
    "content_id": "abc-123-def-456",
    "creator_id": "sarah_poet_123",
    "timestamp": "2026-06-25T10:35:00Z",
    "event": "appeal_submitted",
    "reasoning": "I'm a poet - the repetition is intentional for rhythm",
    "original_decision": {
        "attribution": "uncertain",
        "confidence": 0.61,
        "groq_score": 0.55,
        "stylometric_score": 0.85
    },
    "status": "under_review",
    "reviewer_notes": null,
    "final_decision": null
}
```


---

### Section: Anticipated Edge Cases

```markdown
## Anticipated Edge Cases

### Edge Case 1: Poetry with Intentional Repetition

**Scenario:**
A poet uses deliberate repetition and short, rhythmic lines for artistic effect.

**Example Text:**

"Rain falls, falls, falls
On the roof, on the street, on my soul
Drip, drop, drip, drop
Never stopping, never stopping"


**Why Our System Will Likely Struggle:**
- **Stylometric**: High repetition = low TTR (Type-Token Ratio) → scores as AI-like
- **Stylometric**: Short sentences = low variance → scores as AI-like
- **Groq**: Might see the repetition as a pattern → flags as AI
- **Combined**: Could easily score 0.70+, despite being clearly human

**How We Mitigate:**
- The uncertain zone (0.40-0.59) provides a buffer
- Calibration reduces score when signals disagree
- Poetry detection could be a future improvement
- Clear appeal path for poets explains their process

**Actual Implementation:**
Groq: 0.55 (uncertain - sees intentional repetition)
Stylometric: 0.85 (low variance, low TTR)
Raw: 0.67 → Calibrated: 0.61 → Label: UNCERTAIN

The poet sees "UNCERTAIN" not "AI-GENERATED" - a better outcome.

### Edge Case 2: Very Short Texts (< 50 words)

**Scenario:**
A user submits micro-fiction, a tweet, or a short poem.

**Example Text:**

"The coffee is cold. The day is long. I am tired. I wait."


**Why Our System Will Likely Struggle:**
- **Stylometric**: Not enough sentences for meaningful variance calculation
- **Stylometric**: Low word count = TTR is statistically unreliable
- **Groq**: Not enough context for meaningful semantic analysis
- **Combined**: Both signals return uncertain or random results

**How We Mitigate:**
- Detect short text (< 50 words) and handle specially
- Return "UNCERTAIN" with explanation: "Text too short for confident analysis"
- Flag in audit log with `insufficient_data: true`
- Suggest user submits longer sample if possible
- Appeal path remains available

**Actual Implementation:**
```python
if len(text.split()) < 50:
    return {
        'attribution': 'uncertain',
        'confidence': 0.50,
        'label': '🔍 UNCERTAIN - Text Too Short for Analysis',
        'explanation': 'Very short texts lack enough data for reliable detection'
    }
```

Edge Case 3: Non-Native English Writers

Scenario:
An ESL (English as Second Language) writer submits formal, academic-style English.

Example Text:

"I would like to submit my research paper about artificial intelligence. 
It discusses the ethics of AI in modern society and the challenges we 
face in implementing ethical frameworks."

Why Our System Will Likely Struggle:

Stylometric: Simple vocabulary = lower TTR → flags as AI

Stylometric: Uniform sentence structure = low variance → flags as AI

Groq: Might see formal, simple structure as AI-like

Combined: Could score 0.60-0.70 despite being human

How We Mitigate:

"Moderate AI suspicion" label (0.60-0.79) says "suggests" not "definitely"

Clear appeal path with reasoning field for this context

Future improvement: ESL writing detection

Labels emphasize "patterns suggest" not "definitively"

Actual Implementation:

Groq: 0.65 (formal style, some AI-like patterns)
Stylometric: 0.72 (low TTR, low variance)
Raw: 0.68 → Calibrated: 0.65 → Label: "⚠️ AI-GENERATED CONTENT LIKELY"

Appeal: "I'm a non-native English speaker writing in a formal academic style"
→ Under review, human reviewer reclassifies as human

Edge Case 4: Mixed Human/AI Content
Scenario:
A writer uses AI for brainstorming or editing but writes the core content.

Example:

- Human writes: "I think we should focus on climate change"
- AI rewrites: "Our organization should prioritize climate change mitigation strategies"
- Human edits: "But we need to be practical about what's achievable"

Why Our System Will Struggle:

- It's genuinely ambiguous - not just a detection error
- Both human and AI elements are present
- Stylometrics may pick up AI patterns in some sections
- Groq may detect inconsistent style

How We Handle It:

- UNCERTAIN label is appropriate here - it's the truth
- Label explains: "Mixed patterns detected"
- Appeals can explain the writing process
- Human review recommended for ambiguous cases

What the Label Would Say:

🔍 UNCERTAIN - MIXED PATTERNS DETECTED

Confidence: 48%

What this means:
• The writing shows both human and AI-like patterns
• This could be AI-assisted writing or a mix of sources
• We cannot confidently determine attribution

What you can do:
• If this is your original work, please appeal and explain your process
• If you used AI assistance, please disclose that for transparency

Edge Case 5: Academic Writing (Formal, Structured)
Scenario:
A researcher submits a formal academic paper with rigid structure.

Why It's Problematic:

- Formal academic writing = uniform sentences, technical vocabulary
- Very similar to AI-generated content patterns
- Stylometrics will likely flag as AI
- Groq might see the formal style as AI

How We Handle:

- The "moderate AI suspicion" zone (0.60-0.79) gives benefit of doubt
- Academic writing detection could be a future improvement
- Appeal path available with context about academic writing

### Edge Case Summary Table

| 🎯 Edge Case | 📊 Likely Score Range | 🏷️ System Response | 👤 User Experience |
|--------------|----------------------|-------------------|-------------------|
| 🎭 Poetry with repetition | 0.55 - 0.70 | 🔍 UNCERTAIN or ⚡ Moderate AI | 📝 Clear appeal path |
| 📏 Very short text (<50 words) | 0.45 - 0.55 | 🔍 UNCERTAIN (with explanation) | 💬 Told: "too short for analysis" |
| 🌍 Non-native English writer | 0.60 - 0.75 | ⚡ Moderate AI Suspicion | 🗣️ Appeal with context |
| 🤝 Mixed human/AI content | 0.40 - 0.60 | 🔍 UNCERTAIN | ✅ Honest about ambiguity |
| 📚 Academic writing | 0.55 - 0.70 | ⚡ Moderate AI Suspicion | 📖 Appeal for academic context |


---

### Section: AI Tool Plan

```markdown
## AI Tool Plan

### Milestone 3: Submission Endpoint + First Signal

**Sections to Provide to AI Tool:**
- Detection Signals (from this document)
- Architecture Diagram (from this document)
- API Surface Design (from this document)

**What to Ask AI to Generate:**
1. Flask app skeleton with `/submit` route stub
2. Groq signal function (Signal 1)
3. Basic audit logging setup
4. Error handling structure

**Example Prompt:**

"Using the detection signals specification and architecture diagram provided,
generate a Flask application skeleton with:

A POST /submit endpoint that accepts {text, creator_id}

A Groq LLM signal function that returns a score 0-1

Basic audit logging structure

Placeholder for confidence scoring (to be implemented in M4)
The code should be modular and follow the architecture diagram."


**How to Verify Output:**
1. Test Groq function independently:
   ```python
   text = "This is a test"
   result = groq_signal(text)
   assert 0 <= result['score'] <= 1
   assert 'confidence' in result
   assert 'reasoning' in result

   ```
2. Test /submit endpoint with curl:
``` bash
curl -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "Test content", "creator_id": "test-user"}'
```
Response should include: content_id, attribution, confidence, label

3. Check audit log:

``` bash
curl http://localhost:5000/log
```

Should show at least one entry

Milestone 4: Second Signal + Confidence Scoring
Sections to Provide to AI Tool:

- Detection Signals (this document)
- Uncertainty Representation (this document)
- Architecture Diagram (this document)

What to Ask AI to Generate:

1. Stylometric signal function (Signal 2)
2. Ensemble aggregator logic
3. Confidence calibration function
4. Updated audit logging with both signals

Example Prompt:

"Using the detection signals and uncertainty representation sections, 
generate:
1. A stylometric signal function that calculates:
   - Sentence length variance
   - Type-Token Ratio
   - Punctuation density
   And returns a score 0-1
2. An ensemble aggregator that combines both signals with weights (Groq 60%, Stylometric 40%)
3. A confidence calibrator that adjusts based on signal agreement
4. Updated audit logging to capture both signal scores"

How to Verify Output:

``` python
human_text = "This is human writing. It varies in style."
ai_text = "AI text is uniform and consistent throughout."

human_score = stylometric_signal(human_text)
ai_score = stylometric_signal(ai_text)
assert human_score < ai_score  # Human should score lower (more human-like)
``` 

2. Test with 4 deliberate inputs:
- Clearly AI-generated
- Clearly human-written
- Formal human writing (borderline)
- Lightly edited AI (borderline)

3. Verify score ranges:
- Clear AI: 0.80+
- Clear human: < 0.20
- Borderline: 0.40-0.60

4. Check audit log now includes both scores:

``` bash
curl http://localhost:5000/log
```

Milestone 5: Production Layer

Sections to Provide to AI Tool:

- Transparency Label Design (this document)
- Appeals Workflow (this document)
- Architecture Diagram (this document)

What to Ask AI to Generate:

1. Label generator function (maps scores to 5 variants)
2. POST /appeal endpoint
3. Rate limiting implementation (Flask-Limiter)
4. Complete audit log with all fields

Example Prompt:

"Using the transparency label design and appeals workflow sections, 
generate:
1. A label generator that maps confidence scores to the 5 label variants
2. A POST /appeal endpoint with validation and status updates
3. Rate limiting on the /submit endpoint (10 per minute, 100 per day)
4. Complete audit logging with all required fields"

How to Verify Output:

1. Test all 5 label variants:

``` python
assert get_label(0.95) == "high_ai"
assert get_label(0.75) == "moderate_ai"
assert get_label(0.55) == "uncertain"
assert get_label(0.35) == "moderate_human"
assert get_label(0.15) == "high_human"

```
2. Test appeal workflow:

``` bash
# First, submit content and save content_id
curl -X POST http://localhost:5000/submit ...

# Then, appeal
curl -X POST http://localhost:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "SAVED_ID", "reasoning": "This is my original work"}'
```
Response should show status: "under_review"

3. Test rate limiting:

``` bash
for i in {1..12}; do
  curl -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    -d '{"text": "test", "creator_id": "test"}' \
    -w "%{http_code}\n" -o /dev/null -s
done

```
Should return: first 10 = 200, last 2 = 429

4. Verify audit log includes:

``` bash
curl http://localhost:5000/log
```

Should show: timestamp, content_id, creator_id, both signal scores, confidence, attribution, label, status


## Ensemble Detection (3 Signals)

Stretch feature: a third, independent signal was added so the system combines
3+ signals into one final score.

### Third signal: Behavioral Analysis (`app/detection/behavioral_signal.py`)
- **What it measures:** patterns *around* a submission rather than its text —
  length consistency across a creator's submissions, submission frequency
  (cadence), and similarity to the creator's previous submissions.
- **Why it's valuable:** adds a behavioral dimension orthogonal to the semantic
  (Groq) and structural (stylometric) signals — e.g. rapid near-duplicate
  submissions look automated even when each piece of text reads fine.
- **Limitations:** needs history (returns a neutral 0.5 with low confidence for a
  creator's first submission), and can be gamed (varying length/timing).
  History here is in-memory and process-local.

### Weighting (3 signals)
| Signal | Weight | Rationale |
|--------|--------|-----------|
| Groq LLM | 40% | Best at understanding context and meaning |
| Stylometric | 35% | Good at structural analysis |
| Behavioral | 25% | New signal, lowest confidence initially |

`combined_score = 0.40*groq + 0.35*stylometric + 0.25*behavioral`

### Confidence (agreement-based)
`confidence = clamp(1 - stdev([groq, stylometric, behavioral]) * 1.5, 0, 1)`
- Signals that agree (low standard deviation) → high confidence.
- Signals that disagree (high standard deviation) → low confidence.
- Uses the sample standard deviation. Examples: [0.8,0.75,0.7] → ~0.92;
  [0.9,0.4,0.6] → ~0.62.

### Decision rules (unchanged, conservative — false positives are worse)
- ≥ 0.80 High-confidence AI · 0.60–0.79 Moderate AI · 0.40–0.59 Uncertain ·
  0.20–0.39 Moderate human · < 0.20 High-confidence human.
- Appeals remain available for every label, including high-confidence AI.

The two-signal ensemble (Groq 60% / Stylometric 40%) is retained in
`EnsembleDetector.detect_two_signal` for backward compatibility.

## Stretch Feature: Analytics Dashboard

A read-only analytics layer (`app/services/analytics.py`, exposed at
`GET /analytics/metrics` and `GET /analytics/summary`) that derives metrics from
the audit log. It never writes to the log or touches detection.

### Metrics tracked & why
- **total_submissions** — overall volume processed.
- **detection_counts** — how many `ai_generated` / `uncertain` / `human_written`
  predictions were made; shows the distribution of outcomes.
- **avg_confidence** — how confident the ensemble is on average; a low value
  flags lots of signal disagreement.
- **appeal_count / appeal_rate** — how often creators contest results; a high
  rate is an early warning of false positives (the system's core risk).
- **appeal_status** — pending / approved / denied breakdown of appeals.
- **Additional metric A — confidence_timeline:** average confidence per day for
  the last 7 days, to spot trends/drift over time.
- **Additional metric B — avg_signal_scores:** mean score per signal
  (Groq / stylometric / behavioral), revealing which signal drives decisions.
- **recent_entries** — last 10 entries for a detail view.

### How the dashboard works
The dashboard page (`GET /`) fetches `/analytics/metrics` via JavaScript on load
and on a "Refresh Analytics" click, then renders summary cards, a detection
breakdown, per-signal averages, a 7-day confidence trend (div-based bars, no
chart library), appeal details, and recent activity. The service is defensive:
missing file, missing fields, and unparseable timestamps all degrade gracefully
instead of erroring.

## Stretch Feature: Verified Human / Provenance Certificate

A credential system (`app/services/certificate.py`, exposed under
`/certificate`) that lets a creator earn a "Verified Human" badge.

### What the badge means
The creator completed an additional, human-reviewed verification step. It is a
**display annotation only** — it never changes detection scores, the prediction,
or confidence. A verified creator's transparency label simply gains a 👤 badge
and the note "This creator has a Verified Human credential."

### Workflow (request → review → approve/deny)
1. **Request** — `POST /certificate/request` with `{creator_id}` creates a
   `pending` record. Credentials are **never** granted automatically.
2. **Review** — a moderator lists pending requests with `GET /certificate/review`.
3. **Approve / Deny** — `POST /certificate/review/approve` sets status `active`
   and mints a `certificate_id`; `POST /certificate/review/deny` sets `denied`.
   Both are explicit moderator actions (no self-approval).
4. **Revoke** — `POST /certificate/revoke/<creator_id>` sets status `revoked`.

Statuses: `none → pending → active | denied`, and `active → revoked`.

### API endpoints
- `POST /certificate/request` — request verification (202 pending).
- `GET  /certificate/status/<creator_id>` — current status.
- `GET  /certificate/review` — pending requests (moderator).
- `POST /certificate/review/approve` — approve (moderator).
- `POST /certificate/review/deny` — deny (moderator).
- `POST /certificate/revoke/<creator_id>` — revoke (admin).

`POST /submit` now returns an `is_verified` boolean and, for verified creators,
the badge on `transparency_label`. Data persists to `data/certificates.json`
(atomic writes, like the audit log).

## Stretch Feature: Multi-Modal Support (Image Descriptions)

`POST /submit` accepts a `content_type` field and now supports a second type,
`image_description`, alongside the default `text`.

### Architecture
- `app/detection/base.py` — a `Detector` interface (`detect`, `get_supported_type`).
- `app/detection/text_detector.py` — wraps the existing 3-signal text pipeline
  behind the interface (reuses the same signal functions; no duplication).
- `app/detection/image_description_detector.py` — a deterministic, heuristic
  detector for image descriptions (no LLM, no image processing).
- `app/detection/registry.py` — maps `content_type` -> detector.

The existing text path is **unchanged**: `content_type` defaults to `text` and
falls through to the original inline logic, so the rate limiter, behavioral
history, validators, response shape, and tests are all preserved. Only
`image_description` is routed to the new detector; unknown types return 400 with
the supported-types list.

### Image-description signals (each 0-1, 1 = AI-like)
- **template_detection (40%)** — AI-style phrasing ("image shows", "picture of").
- **complexity (30%)** — sentence-length variance + vocabulary diversity (low
  variance / low diversity -> AI-like).
- **metadata_consistency (20%)** — specific width/height/format/objects look
  human; generic/unknown looks AI.
- **emotion (10%)** — emotive language ("beautiful", "I feel") looks human.

Confidence is agreement-based (`1 - stdev(signals) * 1.5`). Attribution is
standardized to the same 3 values as text (`ai_generated` / `uncertain` /
`human_written`), and the certificate badge + transparency label apply
identically. Submissions are logged with `content_type` and the per-signal
`signal_scores`.

Request example:
```json
{ "content_type": "image_description", "creator_id": "u1",
  "description": "I think this is gorgeous ...", "width": 1920,
  "height": 1080, "format": "jpg", "objects": ["sun", "field"] }
```


