# DocSense Mobile (Flutter)

DocSense Mobile is the Flutter client for iOS and Android, built strictly according to `Document_8_UI_UX_Design_System.md`.

## Features

- **Document Ingestion**: File picker for PDFs and images, with client-side 25MB validation and progress stages.
- **Structured Understanding**: Visual presentation of canonical extraction envelopes (summary bullets, high/medium risk banners, key field table).
- **Grounded Q&A**: Chat interface with evidence-based confidence pills (`HIGH`, `MEDIUM`, `LOW`, `UNSUPPORTED`).
- **Interactive Citations**: Verified citations with page numbers, exact quotes, and jump-to-page navigation.
- **Document Comparison**: Multi-document comparison matrix across policies, terms, and exclusions.
- **Deterministic Actions**: Review and explicit approval workflow for consequential actions and renewal reminders.

## Architecture & Tech Stack

- **Framework**: Flutter 3.x / Dart 3.x
- **State Management**: Riverpod (`flutter_riverpod`)
- **Networking**: `dio` with correlation IDs (`X-Correlation-ID`) and JWT interceptor
- **Secure Storage**: `flutter_secure_storage` for local token caching
- **Design System**: Design tokens defined in `lib/core/theme/app_theme.dart` adhering to WCAG 2.1 AA accessibility standards (min 44x44 touch targets, high contrast, non-color-only risk signaling).

## Directory Structure

```text
mobile/
├── lib/
│   ├── core/
│   │   ├── network/       # Dio ApiClient with auth & correlation interceptors
│   │   └── theme/         # AppTheme, AppColors, AppSpacing design tokens
│   ├── models/            # DocumentModel, ExtractionEnvelope, CitationModel, AskResponse, ActionModel
│   ├── providers/         # Riverpod StateNotifier and FutureProviders
│   ├── screens/
│   │   ├── home_screen.dart             # Document list, upload CTA, bottom navigation
│   │   ├── upload_screen.dart           # File selection & multi-stage processing state
│   │   ├── document_detail_screen.dart  # Summary, risk alerts, extracted fields, citations
│   │   ├── qa_screen.dart               # Grounded Q&A with citations and confidence badges
│   │   ├── compare_screen.dart          # 2-5 document comparison matrix
│   │   └── actions_screen.dart          # Reminders and action approval dialogs
│   ├── services/          # ApiService connecting to FastAPI backend
│   ├── widgets/           # ConfidenceBadge, CitationCard, SummaryCard
│   └── main.dart          # App entry point with ProviderScope
└── pubspec.yaml
```

## Running the App

### Prerequisites
1. Ensure the backend is running (`make dev` or `docker compose up -d`).
2. Make sure Flutter SDK is installed.

### Start the Flutter App
```bash
cd mobile
flutter pub get
flutter run
```
