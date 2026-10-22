# Document 8: UI/UX Design System & Edge-Case Handling

> Parent Blueprint: AI Document → Action: Complete Product & Technical Blueprint  
> Audience: AI Coding Agents, Flutter Engineers, UI/UX Designers

## 8.1 Design Principles

1. Evidence and trust must be visually obvious.
2. Never hide missing information.
3. High-risk findings require clear severity indicators.
4. Every citation is actionable.
5. Offline behavior must be explicit.
6. Loading states communicate processing stage.
7. Accessibility is a product requirement.

## 8.2 Design Tokens

### Color

```text
Primary:       #2563EB
Primary dark:  #1D4ED8
Primary light: #DBEAFE
Canvas:        #F3F4F6
Card:          #FFFFFF
Elevated:      #F9FAFB
Text primary:  #111827
Text secondary:#6B7280
Text tertiary: #9CA3AF
Risk high:     #DC2626
Risk medium:   #F59E0B
Success:       #16A34A
Info:          #3B82F6
```

Risk must never be communicated by color alone.

### Typography

```text
H1 24/700
H2 20/600
H3 17/600
Body 15/400
Body small 13/400
Metric large 28/800
Metric medium 22/700
Caption 12/500
Label 11/600
```

### Spacing

```text
xs=4  sm=8  md=12  lg=16  xl=24  xxl=32
```

## 8.3 Core Flutter Components

| Component | Purpose |
|---|---|
| Riverpod | Application state |
| Freezed + json_serializable | Typed API models |
| Dio | HTTP/JWT/retry/SSE |
| Syncfusion PDF Viewer | PDF rendering and page navigation |
| ML Kit Document Scanner | Camera scanning |
| File Picker | Local file selection |
| Shimmer/Lottie | Processing states |
| Hive or equivalent | Offline cache |
| connectivity_plus | Connectivity detection |
| Firebase Messaging | Push notifications |
| device_calendar | Calendar export |
| RevenueCat | Subscription management |

Package versions must be verified against the repository's actual Flutter/Dart version.

## 8.4 Core UX Flows

### Home

```text
Search
 ↓
Upload CTA
 ↓
Recent documents
 ↓
Bottom navigation
```

Upload options:
- Scan with Camera
- Choose PDF
- Choose Image
- Cloud import where entitlement allows

### Processing

```text
Upload
 ↓
Reading pages
 ↓
Identifying document
 ↓
Extracting facts
 ↓
Preparing Q&A
 ↓
Completed
```

Progress should come from backend events rather than fabricated client-side progress.

### Summary

Show document type, important facts, alerts, limitations/exclusions, citations, Q&A and available actions.

## 8.5 Citation Interaction

```text
Citation
 ↓
Open PDF
 ↓
Jump to source page
 ↓
Highlight exact quote where possible
```

If the source page cannot be opened, show the source metadata instead of failing silently.

## 8.6 Mandatory Edge Cases

| Scenario | UI | Backend |
|---|---|---|
| Low OCR confidence | Request retake and identify page | `LOW_OCR_CONFIDENCE` |
| Password PDF | Request password locally | Do not upload locked binary |
| Null field | `[Not specified in document]` | Preserve `null` |
| Offline | Allow cached reading; disable network actions | Reject/queue appropriately |
| Upload timeout | Retry/cancel | Idempotent initiation |
| SSE lost | Reconnect with bounded backoff | Recover current state |
| Unsupported document | Explain limitation | `UNSUPPORTED_GENERAL` |
| Quota exceeded | Show usage/upgrade | `QUOTA_EXCEEDED` |
| Invalid comparison | Disable/validate | Server-side validation |
| Empty list | Onboarding CTA | Empty response |

## 8.7 Animation

Animations should communicate state without blocking interaction.

Examples:
- card entrance: ~300ms
- citation interaction: ~150ms
- processing shimmer: ~1500ms loop
- page transition: ~300ms

## 8.8 Accessibility

Target WCAG 2.1 AA principles:

- adequate contrast
- 44x44dp minimum touch targets
- semantic labels
- dynamic text scaling
- no color-only meaning
- screen-reader support

## 8.9 Indian Localization

MVP:
- English
- `en_IN` currency formatting
- ISO 8601 internal dates
- `DD-MMM-YYYY` display where specified
- Indian phone validation
- GSTIN validation

Phase 2 may add Hindi summaries and alerts.

## 8.10 UX Security

Never expose provider keys, service-role credentials, stack traces, hidden prompts or internal security rules. Client caching must obey the documented data-retention policy.
