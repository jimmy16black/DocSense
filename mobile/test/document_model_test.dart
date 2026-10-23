import 'package:docsense_mobile/models/document_model.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('DocumentModel', () {
    test('parses snake_case and camelCase payloads correctly', () {
      final json = {
        'id': 'doc-uuid-1',
        'user_id': 'user-uuid-1',
        'title': 'Vehicle Insurance Policy',
        'file_name': 'policy.pdf',
        'file_size_bytes': 1048576,
        'mime_type': 'application/pdf',
        'status': 'PROCESSED',
        'document_type': 'INSURANCE_POLICY',
        'confidence_score': 0.94,
        'page_count': 12,
        'created_at': '2026-10-20T12:00:00Z',
        'updated_at': '2026-10-20T12:01:00Z',
      };

      final doc = DocumentModel.fromJson(json);
      expect(doc.id, equals('doc-uuid-1'));
      expect(doc.userId, equals('user-uuid-1'));
      expect(doc.title, equals('Vehicle Insurance Policy'));
      expect(doc.fileName, equals('policy.pdf'));
      expect(doc.fileSizeBytes, equals(1048576));
      expect(doc.mimeType, equals('application/pdf'));
      expect(doc.status, equals('PROCESSED'));
      expect(doc.documentType, equals('INSURANCE_POLICY'));
      expect(doc.confidenceScore, closeTo(0.94, 0.001));
      expect(doc.pageCount, equals(12));
    });

    test('handles default fallbacks for missing optional properties', () {
      final doc = DocumentModel.fromJson({});
      expect(doc.id, isEmpty);
      expect(doc.title, equals('Untitled Document'));
      expect(doc.status, equals('UPLOADED'));
      expect(doc.citations, isEmpty);
      expect(doc.latestExtraction, isNull);
    });
  });

  group('PaginationMeta and DocumentListResult', () {
    test('parses paginated envelope according to ISSUE-013 contract', () {
      final envelope = {
        'items': [
          {
            'id': 'doc-1',
            'title': 'Doc 1',
            'file_name': 'doc1.pdf',
            'status': 'PROCESSED',
          },
          {
            'id': 'doc-2',
            'title': 'Doc 2',
            'file_name': 'doc2.pdf',
            'status': 'FAILED',
          },
        ],
        'pagination': {
          'page': 1,
          'pageSize': 20,
          'total': 2,
          'totalPages': 1,
          'hasNext': false,
        },
      };

      final result = DocumentListResult.fromJson(envelope);
      expect(result.items.length, equals(2));
      expect(result.items[0].id, equals('doc-1'));
      expect(result.items[1].id, equals('doc-2'));
      expect(result.pagination.page, equals(1));
      expect(result.pagination.pageSize, equals(20));
      expect(result.pagination.total, equals(2));
      expect(result.pagination.totalPages, equals(1));
      expect(result.pagination.hasNext, isFalse);
    });
  });
}
