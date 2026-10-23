import 'extraction_model.dart';

class DocumentModel {
  final String id;
  final String userId;
  final String title;
  final String fileName;
  final int fileSizeBytes;
  final String mimeType;
  final String status;
  final String? documentType;
  final double? confidenceScore;
  final int pageCount;
  final String? errorMessage;
  final DateTime createdAt;
  final DateTime updatedAt;
  final ExtractionEnvelope? latestExtraction;
  final List<CitationModel> citations;

  DocumentModel({
    required this.id,
    required this.userId,
    required this.title,
    required this.fileName,
    required this.fileSizeBytes,
    required this.mimeType,
    required this.status,
    this.documentType,
    this.confidenceScore,
    required this.pageCount,
    this.errorMessage,
    required this.createdAt,
    required this.updatedAt,
    this.latestExtraction,
    this.citations = const [],
  });

  factory DocumentModel.fromJson(Map<String, dynamic> json) {
    return DocumentModel(
      id: json['id'] ?? '',
      userId: json['userId'] ?? json['user_id'] ?? '',
      title: json['title'] ?? 'Untitled Document',
      fileName: json['fileName'] ?? json['file_name'] ?? '',
      fileSizeBytes: json['fileSizeBytes'] ?? json['file_size_bytes'] ?? 0,
      mimeType: json['mimeType'] ?? json['mime_type'] ?? 'application/pdf',
      status: json['status'] ?? 'UPLOADED',
      documentType: json['documentType'] ?? json['document_type'],
      confidenceScore: json['confidenceScore'] != null
          ? (json['confidenceScore'] as num).toDouble()
          : (json['confidence_score'] != null ? (json['confidence_score'] as num).toDouble() : null),
      pageCount: json['pageCount'] ?? json['page_count'] ?? 0,
      errorMessage: json['errorMessage'] ?? json['error_message'],
      createdAt: DateTime.tryParse(json['createdAt'] ?? json['created_at'] ?? '') ?? DateTime.now(),
      updatedAt: DateTime.tryParse(json['updatedAt'] ?? json['updated_at'] ?? '') ?? DateTime.now(),
      latestExtraction: json['latestExtraction'] != null
          ? ExtractionEnvelope.fromJson(json['latestExtraction'])
          : (json['latest_extraction'] != null
              ? ExtractionEnvelope.fromJson(json['latest_extraction'])
              : null),
      citations: (json['citations'] as List<dynamic>?)
              ?.map((e) => CitationModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

/// Paginated document list payload (ISSUE-013).
class PaginationMeta {
  final int page;
  final int pageSize;
  final int total;
  final int totalPages;
  final bool hasNext;

  const PaginationMeta({
    required this.page,
    required this.pageSize,
    required this.total,
    required this.totalPages,
    required this.hasNext,
  });

  factory PaginationMeta.fromJson(Map<String, dynamic> json) => PaginationMeta(
        page: (json['page'] as num?)?.toInt() ?? 1,
        pageSize: (json['pageSize'] ?? json['page_size'] as num?)?.toInt() ?? 20,
        total: (json['total'] as num?)?.toInt() ?? 0,
        totalPages: (json['totalPages'] ?? json['total_pages'] as num?)?.toInt() ?? 0,
        hasNext: (json['hasNext'] ?? json['has_next']) == true,
      );
}

class DocumentListResult {
  final List<DocumentModel> items;
  final PaginationMeta pagination;

  const DocumentListResult({required this.items, required this.pagination});

  factory DocumentListResult.fromJson(Map<String, dynamic> json) {
    final rawItems = (json['items'] as List<dynamic>?) ?? const [];
    final pg = json['pagination'];
    return DocumentListResult(
      items: rawItems.map((e) => DocumentModel.fromJson(e as Map<String, dynamic>)).toList(),
      pagination: pg is Map<String, dynamic>
          ? PaginationMeta.fromJson(pg)
          : PaginationMeta(page: 1, pageSize: rawItems.length, total: rawItems.length, totalPages: 1, hasNext: false),
    );
  }
}
