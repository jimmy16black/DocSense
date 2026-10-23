import 'package:docsense_mobile/core/network/app_error.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('AppError', () {
    test('instantiates with expected defaults', () {
      const err = AppError(
        code: 'VALIDATION_ERROR',
        userMessage: 'Invalid input',
      );
      expect(err.code, equals('VALIDATION_ERROR'));
      expect(err.userMessage, equals('Invalid input'));
      expect(err.classification, equals('SYSTEM_FAILURE'));
      expect(err.isRetryable, isFalse);
      expect(err.correlationId, isNull);
    });

    test('friendlyMessages contains all canonical error codes', () {
      expect(
        AppError.friendlyMessages.containsKey('AUTHENTICATION_FAILED'),
        isTrue,
      );
      expect(AppError.friendlyMessages.containsKey('VALIDATION_ERROR'), isTrue);
      expect(AppError.friendlyMessages.containsKey('QUOTA_EXCEEDED'), isTrue);
      expect(AppError.friendlyMessages.containsKey('NETWORK_ERROR'), isTrue);
      expect(
        AppError.friendlyMessages.containsKey('INTERNAL_SERVER_ERROR'),
        isTrue,
      );
    });

    test('from returns existing AppError as-is', () {
      const original = AppError(
        code: 'TEST',
        userMessage: 'test msg',
        isRetryable: true,
      );
      final result = AppError.from(original);
      expect(result, same(original));
    });

    test(
      'from unknown exception falls back safely without leaking details',
      () {
        final genericErr = Exception('DB connection leaked: password=secret');
        final result = AppError.from(genericErr);
        expect(result.code, equals('UNKNOWN_ERROR'));
        expect(result.userMessage, equals(AppError.fallback));
        expect(result.userMessage.contains('secret'), isFalse);
      },
    );
  });
}
