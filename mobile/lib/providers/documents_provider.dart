import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/document_model.dart';
import '../services/api_service.dart';

final apiServiceProvider = Provider<ApiService>((ref) => ApiService());

final documentListProvider = FutureProvider<List<DocumentModel>>((ref) async {
  final api = ref.watch(apiServiceProvider);
  return api.listDocuments();
});

final documentDetailProvider = FutureProvider.family<DocumentModel, String>((ref, documentId) async {
  final api = ref.watch(apiServiceProvider);
  return api.getDocument(documentId);
});
