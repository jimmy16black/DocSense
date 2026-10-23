import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/document_model.dart';
import '../services/api_service.dart';

final apiServiceProvider = Provider<ApiService>((ref) => ApiService());

/// Active library filters (ISSUE-013): search text + status filter drive the
/// paginated backend query so the home screen is search-first and bounded.
class DocumentListFilter {
  final String search;
  final String? status;

  const DocumentListFilter({this.search = '', this.status});

  DocumentListFilter copyWith({String? search, String? status}) =>
      DocumentListFilter(
        search: search ?? this.search,
        status: status ?? this.status,
      );

  @override
  bool operator ==(Object other) =>
      other is DocumentListFilter &&
      other.search == search &&
      other.status == status;

  @override
  int get hashCode => Object.hash(search, status);
}

final documentListFilterProvider = StateProvider<DocumentListFilter>(
  (ref) => const DocumentListFilter(),
);

/// How many items to fetch (grows in steps of 20 via "Load more").
final documentPageSizeProvider = StateProvider<int>((ref) => 20);

final documentListProvider = FutureProvider<DocumentListResult>((ref) async {
  final api = ref.watch(apiServiceProvider);
  final filter = ref.watch(documentListFilterProvider);
  final pageSize = ref.watch(documentPageSizeProvider);
  return api.listDocuments(
    page: 1,
    pageSize: pageSize,
    search: filter.search.isEmpty ? null : filter.search,
    status: filter.status,
  );
});

final documentDetailProvider = FutureProvider.family<DocumentModel, String>((
  ref,
  documentId,
) async {
  final api = ref.watch(apiServiceProvider);
  return api.getDocument(documentId);
});
