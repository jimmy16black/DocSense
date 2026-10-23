import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/api_service.dart';
import '../services/offline_queue_service.dart';

/// Provider tracking whether the app is currently connected to the network.
/// Defaults to true; can be updated by connectivity listeners or manual toggle.
final isOnlineProvider = StateProvider<bool>((ref) => true);

/// Singleton instance of the offline queue service.
final offlineQueueServiceProvider = Provider<OfflineQueueService>((ref) {
  final service = OfflineQueueService(apiService: ApiService());
  ref.onDispose(() => service.dispose());
  return service;
});

/// Stream of sync status updates (idle, syncing, error).
final syncStatusStreamProvider = StreamProvider<SyncStatus>((ref) {
  final service = ref.watch(offlineQueueServiceProvider);
  return service.statusStream;
});

/// Number of pending offline queue actions.
final pendingQueueCountProvider = StateProvider<int>((ref) {
  final service = ref.watch(offlineQueueServiceProvider);
  return service.pendingCount;
});
