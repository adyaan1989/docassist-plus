# Sample Inputs & Outputs

Real examples showing the system working end-to-end.

---

## DocAssist+ RAG Queries

### Example 1 — Normal Question (neutral emotion)

**Request:**
```json
{
  "query": "What is your return policy?",
  "user_id": "user_123"
}
```

**Response:**
```json
{
  "intent": { "intent": "question", "confidence": 0.91, "is_low_confidence": false },
  "emotion": { "emotion": "neutral", "confidence": 0.85, "is_low_confidence": false },
  "response_tone": "formal",
  "answer": "According to the return policy document: Returns are accepted within 7 days of delivery. Refunds are processed within 5 business days after the return is received and approved.",
  "retrieved_chunks": [
    {
      "filename": "policy.pdf",
      "content": "Returns are accepted within 7 days of delivery. Refunds are processed within 5 business days.",
      "score": 0.94,
      "page": 1
    }
  ],
  "fallback_triggered": false,
  "latency_ms": 312
}
```

**What happened:**
- Intent detected as `question` (contains "what")
- Emotion detected as `neutral` (no emotional language)
- Tone selected: `formal`
- GPT answered using only the retrieved chunk

---

### Example 2 — Complaint (frustrated emotion)

**Request:**
```json
{
  "query": "This is ridiculous, my refund is still not processed",
  "user_id": "user_123"
}
```

**Response:**
```json
{
  "intent": { "intent": "complaint", "confidence": 0.88, "is_low_confidence": false },
  "emotion": { "emotion": "frustrated", "confidence": 0.82, "is_low_confidence": false },
  "response_tone": "empathetic",
  "answer": "I completely understand your frustration, and I sincerely apologize for the delay. According to our policy, refunds are processed within 5 business days. If this timeline has passed, I recommend contacting our support team directly so we can prioritize your case immediately.",
  "retrieved_chunks": [
    {
      "filename": "policy.pdf",
      "content": "Refunds are processed within 5 business days.",
      "score": 0.89,
      "page": 1
    }
  ],
  "fallback_triggered": false,
  "latency_ms": 428
}
```

**What happened:**
- Intent: `complaint` (matched "ridiculous", "still not")
- Emotion: `frustrated` (matched "still not processed")
- Tone matrix: complaint + frustrated → `empathetic`
- GPT received instruction to validate feelings first, then answer

---

---

## VoiceBot Scenarios

### Scenario 1 — Slot Filling

The bot collects missing information before answering.

---

**Turn 1**

Request:
```json
{ "user_id": "user_123", "message": "Check my loan status" }
```

Response:
```json
{
  "session_id": "sess_abc123",
  "message": "I can help you check your loan status. Could you please provide your Loan ID?",
  "intent": "check_status",
  "emotion": "neutral",
  "slots": {},
  "turn_count": 1,
  "context_switched": false
}
```

---

**Turn 2**

Request:
```json
{ "user_id": "user_123", "session_id": "sess_abc123", "message": "12345" }
```

Response:
```json
{
  "session_id": "sess_abc123",
  "message": "Your loan #12345 is currently Approved ✓. Disbursement is scheduled within 2 business days. Is there anything else I can help you with?",
  "intent": "check_status",
  "emotion": "neutral",
  "slots": { "loan_id": "12345" },
  "turn_count": 2,
  "context_switched": false
}
```

**What happened:**
- Turn 1: Bot detected `check_status` intent but `loan_id` slot was empty → asked for it
- Turn 2: Regex extracted `loan_id = "12345"` from the bare number → stored in session → answered

---

### Scenario 2 — Context Continuity

The bot remembers previous turns and links them together.

---

**Turn 1**

Request:
```json
{ "user_id": "user_123", "message": "I want to raise a complaint" }
```

Response:
```json
{
  "session_id": "sess_def456",
  "message": "I'm sorry to hear you're having an issue. Please describe your problem in detail and I'll register a complaint for you.",
  "intent": "complaint",
  "slots": {},
  "turn_count": 1
}
```

---

**Turn 2**

Request:
```json
{ "user_id": "user_123", "session_id": "sess_def456", "message": "Payment failed" }
```

Response:
```json
{
  "session_id": "sess_def456",
  "message": "I've registered your complaint. Your Ticket ID is TKT-5678. Our support team will investigate and contact you within 24 hours.",
  "intent": "complaint",
  "slots": { "complaint_id": "TKT-5678" },
  "turn_count": 2
}
```

---

**Turn 3**

Request:
```json
{ "user_id": "user_123", "session_id": "sess_def456", "message": "What is the status?" }
```

Response:
```json
{
  "session_id": "sess_def456",
  "message": "Your complaint (Ticket TKT-5678) is currently In Progress. Our support team is actively working on it and will update you within 48 hours.",
  "intent": "check_status",
  "slots": { "complaint_id": "TKT-5678" },
  "turn_count": 3
}
```

**What happened:**
- Turn 2 stored `complaint_id = TKT-5678` in the session
- Turn 3 said "What is the status?" with no ticket number — the bot found it from session memory and referenced it automatically

---

### Scenario 3 — Context Switch

User changes their mind mid-conversation — the bot gracefully resets.

---

**Turn 1**

Request:
```json
{ "user_id": "user_123", "message": "Check my loan status" }
```

Response:
```json
{
  "session_id": "sess_ghi789",
  "message": "I can help you check your loan status. Could you please provide your Loan ID?",
  "intent": "check_status",
  "slots": {},
  "turn_count": 1,
  "context_switched": false
}
```

---

**Turn 2**

Request:
```json
{ "user_id": "user_123", "session_id": "sess_ghi789", "message": "Actually I want to raise a complaint" }
```

Response:
```json
{
  "session_id": "sess_ghi789",
  "message": "No problem at all! Please describe your issue and I'll register a complaint for you right away.",
  "intent": "complaint",
  "slots": {},
  "turn_count": 2,
  "context_switched": true
}
```

**What happened:**
- Bot was collecting `loan_id` for `check_status`
- User said "Actually" → context switch detected
- Slots cleared, intent reset to `complaint`
- `context_switched: true` in the response

---

## Edge Cases

### No relevant document found

**Request:**
```json
{ "query": "What is the cancellation fee for flights?", "user_id": "user_123" }
```

**Response:**
```json
{
  "answer": "I'm sorry, I don't have enough information to answer that accurately. The uploaded documents don't contain details about flight cancellation fees. Please contact support for more details.",
  "fallback_triggered": true,
  "retrieved_chunks": []
}
```

---

### Angry user — escalation triggered

**Request:**
```json
{ "user_id": "user_123", "message": "This is absolutely unacceptable! I demand to speak to a manager immediately!" }
```

**Response:**
```json
{
  "message": "I completely understand your frustration and I sincerely apologize. I'm escalating this to a senior support agent who will contact you within the hour.",
  "intent": "complaint",
  "emotion": "angry",
  "escalate_to_agent": true,
  "turn_count": 1
}
```

---

### Low confidence intent — LLM fallback used

**Request:**
```json
{ "query": "The thing with my account is not quite right", "user_id": "user_123" }
```

**What happened internally:**
```
Rule-based confidence: 0.32 (below threshold 0.6)
→ LLM fallback triggered
→ GPT classified as: complaint (confidence: 0.74)
→ Used LLM result
```

**Response:**
```json
{
  "intent": { "intent": "complaint", "confidence": 0.74, "is_low_confidence": false },
  "emotion": { "emotion": "neutral", "confidence": 0.71, "is_low_confidence": false },
  "response_tone": "formal"
}
```
