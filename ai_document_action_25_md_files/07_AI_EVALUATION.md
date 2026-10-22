# AI Evaluation

## Golden Dataset

```text
evaluation/
├── documents/
├── expected/
└── scenarios/
```

Include clean, scanned, poor-quality, tabular, multilingual and long documents.

## Metrics
- Classification accuracy
- Field-level extraction accuracy
- Citation correctness
- Retrieval recall
- Answer groundedness
- Hallucination rate
- Unsupported-answer correctness
- Latency
- Token usage
- Cost/document
- Fallback rate

## Suggested Release Gates
- Citation correctness: 100% for critical facts
- PII leakage: 0
- Unsupported factual claims: 0 in mandatory safety scenarios
- Other quality thresholds must be established from a baseline dataset before production.

## Regression
Run evaluation after changes to prompts, models, schemas, embeddings, chunking or retrieval.

## Human Review
High-risk financial/legal interpretations require human review during evaluation.
