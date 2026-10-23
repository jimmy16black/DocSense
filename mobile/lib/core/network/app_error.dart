import 'dart:convert';

import 'package:dio/dio.dart';

/// BE-4 / ISSUE-014: structured client errors.
///
/// Mirrors the backend error envelope produced by
/// `app.core.errors.docsense_exception_handler`:
///
/// ```json
/// { "success": false,
///   "error": { "code": "...", "message": "...", "classification": "...",
///              "isRetryable": true, "correlationId": "...", "details": {} } }
/// ```
///
/// Screens must display [userMessage] only — never `exception.toString()` —
/// so internal details can never leak into the UI (spec Document_23 §5).
class AppError implements Exception {
  const AppError({
    required this.code,
    required this.userMessage,
    this.classification = 'SYSTEM_FAILURE',
    this.isRetryable = false,
    this.correlationId,
    this.statusCode,
    this.retryAfterSeconds,
  });

  final String code;
  final String userMessage;
  final String classification;
  final bool isRetryable;
  final String? correlationId;
  final int? statusCode;
  final int? retryAfterSeconds;

  static const String fallback = 'Something went wrong. Please try again.';

  /// Map well-known backend codes to polished, non-technical copy.
  static const Map<String, String> friendlyMessages = {
    'AUTHENTICATION_FAILED': 'Your session expired. Please sign in again.',
    'PERMISSION_DENIED': "You don't have access to this document.",
    'RESOURCE_NOT_FOUND': 'We could not find what you were looking for.',
    'VALIDATION_ERROR': 'Some of the information provided is invalid.',
    'RATE_LIMIT_EXCEEDED': 'You are doing that too fast. Please wait a moment.',
    'QUOTA_EXCEEDED': "You've reached this month's processing limit. Documents remain available to read.",
    'GATEWAY_TIMEOUT': 'The analysis service timed out. Please try again.',
    'INTERNAL_SERVER_ERROR': fallback,
    'UPLOAD_NOT_VERIFIED':
        'Upload verification failed. Please re-upload the file.',
    'STORAGE_UNAVAILABLE': 'Storage is temporarily unavailable. Your file was not lost — try again shortly.',
    'DOCUMENT_NOT_READY':
        'This document is still being processed. Check back in a moment.',
    'NETWORK_ERROR': 'No internet connection. Check your network and retry.',
    'TIMEOUT': 'The request took too long. Please try again.',
    'SERVER_MALFUNCTION': fallback,
    'UNKNOWN_ERROR': fallback,
  };

  /// Parse any thrown object (DioException or otherwise) into an AppError.
  factory AppError.from(Object error) {
    if (error is AppError) return error;

    if (error is DioException) {
      // 1) Structured backend envelope?
      final data = error.response?.data;
      Map<String, dynamic>? body;
      if (data is Map<String, dynamic>) {
        body = data;
      } else if (data is String && data.trimLeft().startsWith('{')) {
        try {
          body = jsonDecode(data) as Map<String, dynamic>;
        } catch (_) {
          /* not JSON — fall through to transport handling */
        }
      }
      final errNode = body?['error'];
      if (errNode is Map<String, dynamic>) {
        final code = (errNode['code'] ?? 'SERVER_MALFUNCTION') as String;
        int? retryAfter;
        final raValues = error.response?.headers['retry-after'];
        if (raValues != null && raValues.isNotEmpty) {
          retryAfter = int.tryParse(raValues.first.trim());
        }
        final serverMessage = errNode['message'] as String?;
        return AppError(
          code: code,
          // Friendly copy wins; server copy only when it is safe-looking
          // (never stack traces — those arrive under INTERNAL_SERVER_ERROR
          // which maps to fallback above anyway).
          userMessage:
              friendlyMessages[code] ??
              ((serverMessage != null && serverMessage.isNotEmpty)
                  ? serverMessage
                  : fallback),
          classification:
              (errNode['classification'] ?? 'SYSTEM_FAILURE') as String,
          isRetryable: errNode['isRetryable'] == true,
          correlationId: errNode['correlationId'] as String?,
          statusCode: error.response?.statusCode,
          retryAfterSeconds: retryAfter,
        );
      }

      // 2) Transport-level failures.
      switch (error.type) {
        case DioExceptionType.connectionTimeout:
        case DioExceptionType.sendTimeout:
        case DioExceptionType.receiveTimeout:
          return const AppError(
            code: 'TIMEOUT',
            userMessage: 'The request took too long. Please try again.',
            isRetryable: true,
          );
        case DioExceptionType.connectionError:
          return const AppError(
            code: 'NETWORK_ERROR',
            userMessage:
                'No internet connection. Check your network and retry.',
            isRetryable: true,
          );
        default:
          final status = error.response?.statusCode ?? 500;
          return AppError(
            code: 'SERVER_MALFUNCTION',
            userMessage: fallback,
            statusCode: status,
            isRetryable: status >= 500,
          );
      }
    }

    return const AppError(code: 'UNKNOWN_ERROR', userMessage: fallback);
  }

  @override
  String toString() => 'AppError($code): $userMessage';
}
