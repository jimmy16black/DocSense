import 'dart:async';

import 'package:uuid/uuid.dart';

import '../core/network/app_error.dart';
import 'api_service.dart';

enum QueueItemType { createReminder, updateAction, askQuestion }

enum SyncStatus { idle, syncing, error }

class QueueItem {
  final String id;
  final String idempotencyKey;
  final QueueItemType type;
  final Map<String, dynamic> payload;
  final DateTime createdAt;
  int retryCount;

  QueueItem({
    required this.id,
    required this.idempotencyKey,
    required this.type,
    required this.payload,
    required this.createdAt,
    this.retryCount = 0,
  });

  Map<String, dynamic> toJson() => {
    'id': id,
    'idempotencyKey': idempotencyKey,
    'type': type.name,
    'payload': payload,
    'createdAt': createdAt.toIso8601String(),
    'retryCount': retryCount,
  };

  factory QueueItem.fromJson(Map<String, dynamic> json) => QueueItem(
    id: json['id'] as String,
    idempotencyKey: json['idempotencyKey'] as String,
    type: QueueItemType.values.byName(json['type'] as String),
    payload: Map<String, dynamic>.from(json['payload'] as Map),
    createdAt: DateTime.parse(json['createdAt'] as String),
    retryCount: (json['retryCount'] as int?) ?? 0,
  );
}

/// MOB-1 & MOB-2: Offline action queue and retry manager.
///
/// Ensures user actions (creating reminders, updating action statuses)
/// are preserved during offline states and reliably replayed when network
/// is restored, leveraging backend Idempotency-Key support.
class OfflineQueueService {
  final ApiService apiService;
  final List<QueueItem> _queue = [];
  final _uuid = const Uuid();

  SyncStatus _syncStatus = SyncStatus.idle;
  String? _lastSyncError;

  final _statusController = StreamController<SyncStatus>.broadcast();
  Stream<SyncStatus> get statusStream => _statusController.stream;

  SyncStatus get syncStatus => _syncStatus;
  String? get lastSyncError => _lastSyncError;
  int get pendingCount => _queue.length;
  List<QueueItem> get pendingItems => List.unmodifiable(_queue);

  OfflineQueueService({required this.apiService});

  /// Enqueue an action to be executed when online.
  String enqueue({
    required QueueItemType type,
    required Map<String, dynamic> payload,
    String? idempotencyKey,
  }) {
    final item = QueueItem(
      id: _uuid.v4(),
      idempotencyKey: idempotencyKey ?? _uuid.v4(),
      type: type,
      payload: payload,
      createdAt: DateTime.now(),
    );
    _queue.add(item);
    return item.id;
  }

  /// Remove an item by ID (e.g. user cancelled pending action).
  bool cancel(String itemId) {
    final initialLen = _queue.length;
    _queue.removeWhere((item) => item.id == itemId);
    return _queue.length < initialLen;
  }

  /// Drain and sync pending queued actions against the backend.
  Future<int> processQueue() async {
    if (_queue.isEmpty || _syncStatus == SyncStatus.syncing) {
      return 0;
    }

    _setSyncStatus(SyncStatus.syncing);
    _lastSyncError = null;

    int syncedCount = 0;
    final failedItems = <QueueItem>[];

    final itemsToProcess = List<QueueItem>.from(_queue);

    for (final item in itemsToProcess) {
      try {
        await _executeItem(item);
        _queue.removeWhere((q) => q.id == item.id);
        syncedCount++;
      } catch (e) {
        final err = AppError.from(e);
        item.retryCount++;
        _lastSyncError = err.userMessage;

        // If not retryable or exceeded max retries, don't retry forever
        if (!err.isRetryable && item.retryCount >= 3) {
          _queue.removeWhere((q) => q.id == item.id);
        } else {
          failedItems.add(item);
        }
      }
    }

    _setSyncStatus(failedItems.isNotEmpty ? SyncStatus.error : SyncStatus.idle);
    return syncedCount;
  }

  Future<void> _executeItem(QueueItem item) async {
    switch (item.type) {
      case QueueItemType.createReminder:
        await apiService.createReminder(
          documentId: item.payload['documentId'] as String,
          title: item.payload['title'] as String,
          description: item.payload['description'] as String?,
          dueDate: item.payload['dueDate'] != null
              ? DateTime.parse(item.payload['dueDate'] as String)
              : DateTime.now().add(const Duration(days: 7)),
          actionType:
              item.payload['actionType'] as String? ?? 'RENEWAL_REMINDER',
        );
        break;

      case QueueItemType.updateAction:
        await apiService.updateAction(
          actionId: item.payload['actionId'] as String,
          status: item.payload['status'] as String?,
          notes: item.payload['notes'] as String?,
        );
        break;

      case QueueItemType.askQuestion:
        await apiService.askQuestion(
          item.payload['documentId'] as String,
          item.payload['question'] as String,
        );
        break;
    }
  }

  void _setSyncStatus(SyncStatus status) {
    _syncStatus = status;
    _statusController.add(status);
  }

  void dispose() {
    _statusController.close();
  }
}
