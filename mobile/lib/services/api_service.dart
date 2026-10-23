import 'package:dio/dio.dart';
import '../core/network/api_client.dart';
import '../models/action_model.dart';
import '../models/document_model.dart';
import '../models/qa_model.dart';

class ApiService {
  final ApiClient client;

  ApiService({ApiClient? apiClient}) : client = apiClient ?? ApiClient();

  Future<Map<String, dynamic>> initUpload({
    required String fileName,
    required int fileSizeBytes,
    required String mimeType,
    String? documentType,
  }) async {
    final response = await client.dio.post(
      '/api/v1/documents/upload-init',
      data: {
        'fileName': fileName,
        'fileSizeBytes': fileSizeBytes,
        'mimeType': mimeType,
        if (documentType != null) 'documentType': documentType,
      },
    );
    return response.data['data'] as Map<String, dynamic>;
  }

  /// Uploads the raw bytes to the presigned URL returned by [initUpload].
  /// ISSUE-002: the server will not accept /process until it has verified
  /// these bytes via [completeUpload].
  Future<void> putPresigned({
    required String uploadUrl,
    required List<int> bytes,
    required String mimeType,
  }) async {
    await client.dio.put<void>(
      uploadUrl,
      data: bytes,
      options: Options(
        headers: {'Content-Type': mimeType},
        responseType: ResponseType.plain,
      ),
    );
  }

  /// Server-side verification of the uploaded object (size/MIME/checksum).
  Future<Map<String, dynamic>> completeUpload(
    String documentId, {
    String? checksumSha256,
  }) async {
    final response = await client.dio.post(
      '/api/v1/documents/$documentId/upload-complete',
      data: {
        if (checksumSha256 != null) 'checksumSha256': checksumSha256,
      },
    );
    return response.data['data'] as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> processDocument(
    String documentId, {
    bool forceReprocess = false,
  }) async {
    final response = await client.dio.post(
      '/api/v1/documents/$documentId/process',
      data: {'forceReprocess': forceReprocess},
    );
    return response.data['data'] as Map<String, dynamic>;
  }

  Future<DocumentModel> getDocument(String documentId) async {
    final response = await client.dio.get('/api/v1/documents/$documentId');
    return DocumentModel.fromJson(response.data['data']);
  }

  Future<List<DocumentModel>> listDocuments() async {
    final response = await client.dio.get('/api/v1/documents');
    final list = response.data['data'] as List<dynamic>;
    return list.map((e) => DocumentModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<AskResponse> askQuestion(String documentId, String question) async {
    final response = await client.dio.post(
      '/api/v1/documents/$documentId/ask',
      data: {'question': question},
    );
    return AskResponse.fromJson(response.data['data']);
  }

  Future<CompareResponse> compareDocuments(List<String> documentIds) async {
    final response = await client.dio.post(
      '/api/v1/documents/compare',
      data: {'documentIds': documentIds},
    );
    return CompareResponse.fromJson(response.data['data']);
  }

  Future<ActionModel> createReminder({
    required String documentId,
    required String title,
    required DateTime dueDate,
    String? description,
    String actionType = 'RENEWAL_REMINDER',
  }) async {
    final response = await client.dio.post(
      '/api/v1/actions/reminders',
      data: {
        'documentId': documentId,
        'title': title,
        'dueDate': dueDate.toIso8601String(),
        'description': description,
        'actionType': actionType,
      },
    );
    return ActionModel.fromJson(response.data['data']);
  }

  Future<List<ActionModel>> listActions() async {
    final response = await client.dio.get('/api/v1/actions');
    final list = response.data['data'] as List<dynamic>;
    return list.map((e) => ActionModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<ActionModel> updateAction(
    String actionId, {
    String? status,
    String? notes,
  }) async {
    final response = await client.dio.patch(
      '/api/v1/actions/$actionId',
      data: {
        if (status != null) 'status': status,
        if (notes != null) 'notes': notes,
      },
    );
    return ActionModel.fromJson(response.data['data']);
  }

  Future<void> deleteUserAccount() async {
    await client.dio.delete('/api/v1/users/me');
  }
}
