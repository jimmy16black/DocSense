import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../core/theme/app_theme.dart';
import '../models/document_model.dart';
import '../providers/documents_provider.dart';
import 'document_detail_screen.dart';
import 'upload_screen.dart';
import 'compare_screen.dart';
import 'actions_screen.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('DocSense'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.refresh(documentListProvider),
          ),
        ],
      ),
      body: IndexedStack(
        index: _currentIndex,
        children: const [
          _DocumentsTab(),
          CompareScreen(),
          ActionsScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (idx) => setState(() => _currentIndex = idx),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.description_outlined),
            selectedIcon: Icon(Icons.description),
            label: 'Documents',
          ),
          NavigationDestination(
            icon: Icon(Icons.compare_arrows_outlined),
            selectedIcon: Icon(Icons.compare_arrows),
            label: 'Compare',
          ),
          NavigationDestination(
            icon: Icon(Icons.alarm_outlined),
            selectedIcon: Icon(Icons.alarm),
            label: 'Actions',
          ),
        ],
      ),
      floatingActionButton: _currentIndex == 0
          ? FloatingActionButton.extended(
              onPressed: () async {
                final result = await Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const UploadScreen()),
                );
                if (result == true) {
                  ref.refresh(documentListProvider);
                }
              },
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              icon: const Icon(Icons.add),
              label: const Text('Add Document'),
            )
          : null,
    );
  }
}

class _DocumentsTab extends ConsumerWidget {
  const _DocumentsTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final docsAsync = ref.watch(documentListProvider);

    return docsAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (err, stack) => Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.cloud_off, size: 48, color: AppColors.textTertiary),
              const SizedBox(height: AppSpacing.md),
              Text(
                'Unable to load documents: $err',
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.textSecondary),
              ),
              const SizedBox(height: AppSpacing.md),
              ElevatedButton(
                onPressed: () => ref.refresh(documentListProvider),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      ),
      data: (docs) {
        if (docs.isEmpty) {
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.xl),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.folder_open, size: 64, color: AppColors.textTertiary),
                  const SizedBox(height: AppSpacing.md),
                  const Text(
                    'No documents yet',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  const Text(
                    'Upload an insurance policy, GST invoice, or contract to get grounded answers and actions.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AppColors.textSecondary),
                  ),
                ],
              ),
            ),
          );
        }

        return RefreshIndicator(
          onRefresh: () async => ref.refresh(documentListProvider),
          child: ListView.builder(
            padding: const EdgeInsets.all(AppSpacing.lg),
            itemCount: docs.length,
            itemBuilder: (context, index) {
              final doc = docs[index];
              return _DocumentCard(document: doc);
            },
          ),
        );
      },
    );
  }
}

class _DocumentCard extends StatelessWidget {
  final DocumentModel document;

  const _DocumentCard({required this.document});

  @override
  Widget build(BuildContext context) {
    final dateStr = DateFormat('dd MMM yyyy').format(document.createdAt);

    return Card(
      margin: const EdgeInsets.only(bottom: AppSpacing.md),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => DocumentDetailScreen(documentId: document.id),
            ),
          );
        },
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(AppSpacing.sm),
                    decoration: BoxDecoration(
                      color: AppColors.primaryLight,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.picture_as_pdf, color: AppColors.primary),
                  ),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          document.title,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textPrimary,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 2),
                        Text(
                          document.documentType ?? 'DOCUMENT',
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppColors.textSecondary,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),
                  _StatusBadge(status: document.status),
                ],
              ),
              const SizedBox(height: AppSpacing.md),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Added $dateStr',
                    style: const TextStyle(fontSize: 12, color: AppColors.textTertiary),
                  ),
                  Row(
                    children: [
                      const Text(
                        'View Analysis',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: AppColors.primary,
                        ),
                      ),
                      const SizedBox(width: 4),
                      const Icon(Icons.arrow_forward_ios, size: 12, color: AppColors.primary),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  final String status;

  const _StatusBadge({required this.status});

  @override
  Widget build(BuildContext context) {
    Color bg;
    Color fg;

    switch (status) {
      case 'COMPLETED':
        bg = const Color(0xFFDCFCE7);
        fg = AppColors.success;
        break;
      case 'EXTRACTING':
      case 'VALIDATING':
        bg = const Color(0xFFDBEAFE);
        fg = AppColors.primary;
        break;
      case 'FAILED':
        bg = const Color(0xFFFEE2E2);
        fg = AppColors.riskHigh;
        break;
      default:
        bg = const Color(0xFFF3F4F6);
        fg = AppColors.textSecondary;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        status,
        style: TextStyle(
          color: fg,
          fontSize: 11,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }
}
