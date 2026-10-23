"""ISSUE-016: AI Evaluation Golden Set Test Suite.

Ensures the golden set evaluation harness runs and passes all release gates.
"""

from scripts.eval_ai_golden_set import run_evaluation


def test_ai_golden_set_evaluation():
    success = run_evaluation()
    assert success is True, "AI Evaluation Golden Set failed one or more release gates"
