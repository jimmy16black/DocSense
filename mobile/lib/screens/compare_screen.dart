import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/network/app_error.dart';
import '../core/theme/app_theme.dart';
import '../models/qa_model.dart';
import '../providers/documents_provider.dart';
import '../services/api_service.dart';

class CompareScreen extends ConsumerStatefulWidget {
  const CompareScreen({super.key});

  @override
  ConsumerState<CompareScreen> createState() => _CompareScreenState();
}

class _CompareScreenState extends ConsumerState<CompareScreen> {
  final ApiService _apiService = ApiService();
  final Set<String> _selectedDocIds = {};
  CompareResponse? _comparisonResult;
  bool _isLoading = false;

  Future<void> _runComparison() async {
    if (_selectedDocIds.length < 2) return;

    setState(() => _isLoading = true);
    try {
      final res = await _apiService.compareDocuments(_selectedDocIds.toList());
      setState(() {
        _comparisonResult = res;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      if (!mounted) return;
      // BE-4: structured error → friendly copy only.
      final err = AppError.from(e);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(err.userMessage)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final docsAsync = ref.watch(documentListProvider);

    return Scaffold(
      body: docsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(child: Text('Error loading documents: $err')),
        data: (result) {
          final docs = result.items;
          if (docs.length < 2) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.xl),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: const [
                    Icon(Icons.compare_arrows, size: 64, color: AppColors.textTertiary),
                    SizedBox(height: AppSpacing.md),
                    Text(
                      'Need at least 2 documents',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                    SizedBox(height: AppSpacing.xs),
                    Text(
                      'Upload another policy or contract to compare coverage, room rents, and exclusions side-by-side.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: AppColors.textSecondary),
                    ),
                  ],
                ),
              ),
            );
          }

          return ListView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            children: [
              const Text(
                'Select 2 to 5 Documents to Compare',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: AppSpacing.sm),
              ...docs.map((doc) {
                final isSelected = _selectedDocIds.contains(doc.id);
                return CheckboxListTile(
                  value: isSelected,
                  title: Text(doc.title, style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text(doc.documentType ?? 'Document'),
                  onChanged: (val) {
                    setState(() {
                      if (val == true) {
                        if (_selectedDocIds.length < 5) _selectedDocIds.add(doc.id);
                      } else {
                        _selectedDocIds.remove(doc.id);
                      }
                    });
                  },
                );
              }),
              const SizedBox(height: AppSpacing.md),
              ElevatedButton(
                onPressed: _selectedDocIds.length >= 2 ? _runComparison : null,
                child: Text('Compare ${_selectedDocIds.length} Documents'),
              ),
              const SizedBox(height: AppSpacing.xl),
              if (_isLoading)
                const Center(child: CircularProgressIndicator())
              else if (_comparisonResult != null) ...[
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(AppSpacing.lg),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Comparison Summary',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: AppSpacing.sm),
                        Text(_comparisonResult!.summary, style: const TextStyle(fontSize: 14)),
                        const SizedBox(height: AppSpacing.md),
                        ..._comparisonResult!.comparisonMatrix.map(
                          (item) => Padding(
                            padding: const EdgeInsets.symmetric(vertical: 6),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  item.attribute,
                                  style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.primary),
                                ),
                                const SizedBox(height: 2),
                                ...item.values.entries.map(
                                  (e) => Text('• ${e.value}', style: const TextStyle(fontSize: 13)),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ],
          );
        },
      ),
    );
  }
}
