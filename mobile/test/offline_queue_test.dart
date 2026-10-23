import 'package:docsense_mobile/services/api_service.dart';
import 'package:docsense_mobile/services/offline_queue_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('QueueItem', () {
    test('serializes to and from json accurately', () {
      final now = DateTime.now();
      final item = QueueItem(
        id: 'test-id-1',
        idempotencyKey: 'idem-key-1',
        type: QueueItemType.createReminder,
        payload: {
          'documentId': 'doc-123',
          'title': 'Pay Insurance',
          'dueDate': now.toIso8601String(),
        },
        createdAt: now,
        retryCount: 1,
      );

      final json = item.toJson();
      expect(json['id'], equals('test-id-1'));
      expect(json['idempotencyKey'], equals('idem-key-1'));
      expect(json['type'], equals('createReminder'));
      expect(json['retryCount'], equals(1));

      final restored = QueueItem.fromJson(json);
      expect(restored.id, equals(item.id));
      expect(restored.idempotencyKey, equals(item.idempotencyKey));
      expect(restored.type, equals(QueueItemType.createReminder));
      expect(restored.payload['title'], equals('Pay Insurance'));
      expect(restored.retryCount, equals(1));
    });
  });

  group('OfflineQueueService', () {
    late OfflineQueueService service;

    setUp(() {
      service = OfflineQueueService(apiService: ApiService());
    });

    tearDown(() {
      service.dispose();
    });

    test('enqueue creates item with generated UUID and idempotency key', () {
      final id = service.enqueue(
        type: QueueItemType.askQuestion,
        payload: {
          'documentId': 'doc-1',
          'question': 'What is the policy limit?',
        },
      );

      expect(id, isNotEmpty);
      expect(service.pendingCount, equals(1));
      expect(service.pendingItems.first.id, equals(id));
      expect(service.pendingItems.first.idempotencyKey, isNotEmpty);
      expect(service.syncStatus, equals(SyncStatus.idle));
    });

    test('cancel removes item by id', () {
      final id1 = service.enqueue(
        type: QueueItemType.updateAction,
        payload: {'actionId': 'act-1'},
      );
      final id2 = service.enqueue(
        type: QueueItemType.updateAction,
        payload: {'actionId': 'act-2'},
      );
      expect(service.pendingCount, equals(2));

      final cancelled = service.cancel(id1);
      expect(cancelled, isTrue);
      expect(service.pendingCount, equals(1));
      expect(service.pendingItems.first.id, equals(id2));

      final notCancelled = service.cancel('non-existent');
      expect(notCancelled, isFalse);
      expect(service.pendingCount, equals(1));
    });

    test('processQueue on empty queue returns 0 and stays idle', () async {
      final count = await service.processQueue();
      expect(count, equals(0));
      expect(service.syncStatus, equals(SyncStatus.idle));
    });
  });
}
