import 'dart:io' show Platform;
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

class ApiClient {
  static String get defaultBaseUrl {
    const envUrl = String.fromEnvironment('API_BASE_URL');
    if (envUrl.isNotEmpty) return envUrl;

    if (!kIsWeb && Platform.isAndroid) {
      return 'http://10.0.2.2:8001';
    }

    return 'http://localhost:8001';
  }

  static String get baseUrl => defaultBaseUrl;
  final Dio dio;
  final FlutterSecureStorage storage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );

  ApiClient({String? customBaseUrl})
    : dio = Dio(
        BaseOptions(
          baseUrl: customBaseUrl ?? defaultBaseUrl,
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 30),
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
        ),
      ) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // Add correlation ID for tracing
          options.headers['X-Correlation-ID'] = const Uuid().v4();

          // Attach JWT token if stored (ISSUE-011)
          final token = await storage.read(key: 'jwt_token');
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }

          return handler.next(options);
        },
        onError: (DioException error, handler) {
          // Process centralized error response format
          return handler.next(error);
        },
      ),
    );
  }
}
