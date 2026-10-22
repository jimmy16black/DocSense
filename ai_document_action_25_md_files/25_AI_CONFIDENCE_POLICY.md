# AI Confidence & Decision Policy

## Evidence-Based Confidence

### HIGH
Direct structured fact or strongly verified citation.

### MEDIUM
Multiple relevant pieces of evidence with minor ambiguity.

### LOW
Weak or incomplete evidence.

### UNSUPPORTED
No sufficient evidence.

## UI Behavior

```text
HIGH → normal answer
MEDIUM → answer + evidence emphasis
LOW → cautious answer + source
UNSUPPORTED → explicit inability to answer
```

## Important Rule
Do not present raw LLM self-reported confidence as factual confidence.

Confidence must be derived from evidence, retrieval quality, schema validation and rule checks.

## Consequential Actions
Low-confidence or conflicting information cannot directly trigger consequential actions.
