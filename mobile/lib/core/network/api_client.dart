import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

class ApiClient {
  static const String baseUrl = 'http://localhost:8000'; // Default for iOS simulator / web; 10.0.2.2 for Android
  final Dio dio;
  final FlutterSecureStorage storage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );

  ApiClient({String? customBaseUrl})
    : dio = Dio(
        BaseOptions(
          baseUrl: customBaseUrl ?? baseUrl,
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
