# DocSense AI Evaluation & Golden Set Methodology

This document details the automated AI evaluation framework, dataset fixtures, quality metrics, and PR-blocking release gates per `07_AI_EVALUATION.md`.

## 1. Overview & Golden Dataset

DocSense uses a canonical golden evaluation harness (`backend/evaluation/golden_set/fixtures.json`) evaluated by `backend/scripts/eval_ai_golden_set.py` to ensure that prompt, model, or retrieval changes do not cause quality regressions, hallucinations, or data leakage.

### Test Scenarios
- **Insurance Policies**: Verifies coverage, room rent limits, pre-existing disease waiting periods, and exact quote citations.
- **Tax Invoices**: Verifies GSTIN, invoice identifiers, payment due dates, and tax line item precision.
- **Identity & Compliance**: Asserts strict DPDP compliance and zero PII leakage (Aadhaar, PAN, Bank Accounts, Phone numbers).
- **Adversarial / Unsupported Questions**: Asserts refusal correctness (the model must explicitly refuse to fabricate unsupported facts).

## 2. Release Gates & PR-Blocking Thresholds

Every PR and nightly CI run must meet or exceed the following quality thresholds:

| Metric | Target / Gate | Enforcement | Description |
| :--- | :--- | :--- | :--- |
| **Citation Correctness** | **100.0%** (critical facts) | **PR-blocking** | All extracted citations must be verified verbatim against the document text (normalized for unicode and whitespace). |
| **PII Leakage Count** | **0** | **PR-blocking** | Zero raw Aadhaar, PAN, Bank Account, or other Indian financial identifiers may appear in prompt logs or outputs. |
| **Refusal Correctness** | **100.0%** | **PR-blocking** | Factual claims not grounded in the document text must be refused without hallucination. |
| **Extraction Accuracy** | **>= 85.0%** | **PR-blocking** | Key field entity extraction precision and recall against canonical golden labels. |

## 3. Running the Evaluation Harness

### Locally
```bash
cd backend
uv run python scripts/eval_ai_golden_set.py
```
or via the test suite:
```bash
uv run pytest tests/test_ai_evaluation.py
```

### In CI / Automation
The evaluation harness runs automatically:
1. On every push and pull request via the backend CI workflow.
2. Nightly at 02:00 UTC via `.github/workflows/ai-eval-nightly.yml`.
