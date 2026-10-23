---
title: "[P2][UX] UI/UX gaps vs market leaders — dark mode, search-first home, processing skeletons, citation→PDF jump"
labels: enhancement, medium, mobile, ux
---

## Context
DocSense must compete with polished 2026 document-AI apps. Document_8 (UI/UX Design System) defines the bar; current build meets tokens & accessibility basics but misses the flows that create delight and trust.

## Gaps (each is a sub-task)
1. **Dark theme absent** — `MaterialApp` sets only `lightTheme`; add spec-compliant dark palette + `ThemeMode.system`.
2. **No Search on Home** — spec flow starts with Search; add debounced search sheet wired to ISSUE-013 query params, plus type/status filter chips.
3. **Processing UX violates §8.4** — stage names don't match spec vocabulary ("Reading pages → Identifying document → Extracting facts → Preparing Q&A"), no shimmer/Lottie skeletons, progress fabricated client-side (see ISSUE-003 for backend events).
4. **Citation cards can't jump to source (§8.5)** — no PDF viewer dependency (`pdfx`/Syncfusion); tapping "View in document" does nothing. Implement page-jump + quote highlight; fallback to source-metadata sheet when rendering fails (never fail silently).
5. **Error copy leaks internals** — screens show raw Dart exception strings (`'Processing failed: $e'`); map canonical error envelopes (`code`, `classification`, retry affordance) to human copy per §8.6 edge-case table (LOW_OCR_CONFIDENCE retake flow, QUOTA_EXCEEDED upgrade sheet, password-PDF local prompt).
6. **Empty states lack onboarding CTA** — first-run should teach the value prop with sample-document demo.
7. **Off-spec color tokens** — `0xFFFFEDD5` etc. not in §8.2 palette; audit all widgets against token set; keep risk dual-encoded (icon+color) everywhere.
8. **ConfidenceBadge default branch is red** — unknown enum values render as UNSUPPORTED/alarming; needs exhaustive switch + neutral "Unclassified" fallback (25_AI_CONFIDENCE_POLICY).

## Acceptance criteria
- [ ] Figma-matched implementation of above with widget tests per screen; golden-tests for light+dark.
- [ ] Accessibility re-audit: contrast ratios ≥ 4.5:1 both themes, touch targets ≥ 44dp, screen-reader labels on badges/citations.
