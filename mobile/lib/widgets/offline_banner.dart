import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/app_theme.dart';
import '../providers/connectivity_provider.dart';
import '../services/offline_queue_service.dart';

/// MOB-1 / MOB-2: Offline status banner with queued action counters and retry affordance.
class OfflineBanner extends ConsumerWidget {
  const OfflineBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOnline = ref.watch(isOnlineProvider);
    final queueService = ref.watch(offlineQueueServiceProvider);
    final pendingCount = queueService.pendingCount;
    final syncStatus = queueService.syncStatus;

    if (isOnline && pendingCount == 0 && syncStatus == SyncStatus.idle) {
      return const SizedBox.shrink();
    }

    final isSyncing = syncStatus == SyncStatus.syncing;
    final isError = syncStatus == SyncStatus.error;

    Color bgColor = isError
        ? const Color(0xFFFEE2E2)
        : (isOnline ? const Color(0xFFE0E7FF) : const Color(0xFFFEF3C7));
    Color textColor = isError
        ? AppColors.riskHigh
        : (isOnline ? AppColors.primary : const Color(0xFFB45309));
    IconData icon = isError
        ? Icons.error_outline
        : (isOnline ? Icons.sync : Icons.wifi_off);

    String message;
    if (!isOnline) {
      message = pendingCount > 0
          ? 'Offline mode — $pendingCount action${pendingCount > 1 ? 's' : ''} queued'
          : 'You are currently offline. Changes are saved locally.';
    } else if (isSyncing) {
      message = 'Syncing queued actions...';
    } else if (isError) {
      message = queueService.lastSyncError ?? 'Sync failed. Tap to retry.';
    } else {
      message =
          '$pendingCount queued action${pendingCount > 1 ? 's' : ''} pending sync';
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: AppSpacing.sm,
      ),
      color: bgColor,
      child: SafeArea(
        bottom: false,
        child: Row(
          children: [
            if (isSyncing)
              SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation<Color>(textColor),
                ),
              )
            else
              Icon(icon, size: 18, color: textColor),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Text(
                message,
                style: TextStyle(
                  color: textColor,
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            if (pendingCount > 0 && !isSyncing)
              TextButton(
                onPressed: () async {
                  await queueService.processQueue();
                },
                style: TextButton.styleFrom(
                  visualDensity: VisualDensity.compact,
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.sm,
                  ),
                  foregroundColor: textColor,
                ),
                child: const Text(
                  'Sync Now',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
