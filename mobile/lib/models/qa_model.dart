import 'extraction_model.dart';

class AskResponse {
  final String answer;
  final String confidence; // HIGH, MEDIUM, LOW, UNSUPPORTED
  final List<CitationModel> citations;
  final List<String> suggestedFollowUps;
  final bool groundedInEvidence;

  AskResponse({
    required this.answer,
    required this.confidence,
    this.citations = const [],
    this.suggestedFollowUps = const [],
    this.groundedInEvidence = true,
  });

  factory AskResponse.fromJson(Map<String, dynamic> json) {
    return AskResponse(
      answer: json['answer'] ?? '',
      confidence: json['confidence'] ?? 'HIGH',
      citations:
          (json['citations'] as List<dynamic>?)
              ?.map((e) => CitationModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      suggestedFollowUps:
          (json['suggestedFollowUps'] ??
                  json['suggested_follow_ups'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      groundedInEvidence:
          json['groundedInEvidence'] ?? json['grounded_in_evidence'] ?? true,
    );
  }
}

class ComparisonItem {
  final String attribute;
  final Map<String, dynamic> values;
  final String? winnerDocumentId;
  final String? notes;

  ComparisonItem({
    required this.attribute,
    required this.values,
    this.winnerDocumentId,
    this.notes,
  });

  factory ComparisonItem.fromJson(Map<String, dynamic> json) {
    return ComparisonItem(
      attribute: json['attribute'] ?? '',
      values: (json['values'] as Map<String, dynamic>?) ?? {},
      winnerDocumentId: json['winnerDocumentId'] ?? json['winner_document_id'],
      notes: json['notes'],
    );
  }
}

class CompareResponse {
  final String summary;
  final List<ComparisonItem> comparisonMatrix;
  final List<String> recommendations;

  CompareResponse({
    required this.summary,
    this.comparisonMatrix = const [],
    this.recommendations = const [],
  });

  factory CompareResponse.fromJson(Map<String, dynamic> json) {
    return CompareResponse(
      summary: json['summary'] ?? '',
      comparisonMatrix:
          (json['comparisonMatrix'] ??
                  json['comparison_matrix'] as List<dynamic>?)
              ?.map((e) => ComparisonItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      recommendations:
          (json['recommendations'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
    );
  }
}
