class CitationModel {
  final int pageNumber;
  final String? sectionHeading;
  final String exactQuote;
  final Map<String, dynamic>? boundingBox;

  CitationModel({
    required this.pageNumber,
    this.sectionHeading,
    required this.exactQuote,
    this.boundingBox,
  });

  factory CitationModel.fromJson(Map<String, dynamic> json) {
    return CitationModel(
      pageNumber: json['pageNumber'] ?? json['page_number'] ?? 1,
      sectionHeading: json['sectionHeading'] ?? json['section_heading'],
      exactQuote: json['exactQuote'] ?? json['exact_quote'] ?? '',
      boundingBox: json['boundingBox'] ?? json['bounding_box'],
    );
  }

  Map<String, dynamic> toJson() => {
    'pageNumber': pageNumber,
    'sectionHeading': sectionHeading,
    'exactQuote': exactQuote,
    'boundingBox': boundingBox,
  };
}

class ExtractionEnvelope {
  final String documentType;
  final double confidenceScore;
  final String title;
  final List<String> summaryBullets;
  final List<String> importantAlerts;
  final List<String> suggestedQuestions;
  final List<Map<String, dynamic>> recommendedActions;
  final Map<String, dynamic> payload;
  final List<CitationModel> citations;

  ExtractionEnvelope({
    required this.documentType,
    required this.confidenceScore,
    required this.title,
    required this.summaryBullets,
    required this.importantAlerts,
    required this.suggestedQuestions,
    required this.recommendedActions,
    required this.payload,
    required this.citations,
  });

  factory ExtractionEnvelope.fromJson(Map<String, dynamic> json) {
    return ExtractionEnvelope(
      documentType: json['documentType'] ?? json['document_type'] ?? 'OTHER',
      confidenceScore:
          (json['confidenceScore'] ?? json['confidence_score'] ?? 0.0)
              .toDouble(),
      title: json['title'] ?? 'Untitled Document',
      summaryBullets:
          (json['summaryBullets'] ?? json['summary_bullets'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      importantAlerts:
          (json['importantAlerts'] ??
                  json['important_alerts'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      suggestedQuestions:
          (json['suggestedQuestions'] ??
                  json['suggested_questions'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      recommendedActions:
          (json['recommendedActions'] ??
                  json['recommended_actions'] as List<dynamic>?)
              ?.map((e) => e as Map<String, dynamic>)
              .toList() ??
          [],
      payload: (json['payload'] as Map<String, dynamic>?) ?? {},
      citations:
          (json['citations'] as List<dynamic>?)
              ?.map((e) => CitationModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}
