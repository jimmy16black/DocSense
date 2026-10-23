import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../core/network/app_error.dart';
import '../core/theme/app_theme.dart';
import '../models/action_model.dart';
import '../services/api_service.dart';

class ActionsScreen extends StatefulWidget {
  const ActionsScreen({super.key});

  @override
  State<ActionsScreen> createState() => _ActionsScreenState();
}

class _ActionsScreenState extends State<ActionsScreen> {
  final ApiService _apiService = ApiService();
  List<ActionModel> _actions = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadActions();
  }

  Future<void> _loadActions() async {
    setState(() => _isLoading = true);
    try {
      final list = await _apiService.listActions();
      setState(() {
        _actions = list;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _confirmAction(ActionModel action) async {
    // Show confirmation dialog before executing consequential action
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirm Consequential Action'),
        content: Text(
          'Do you confirm performing "${action.title}"?\n\n'
          'Deterministic execution will proceed upon your explicit approval.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Confirm & Proceed'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      try {
        await _apiService.updateAction(action.id, status: 'CONFIRMED');
        _loadActions();
      } catch (e) {
        if (!mounted) return;
        // BE-4: show only safe, friendly copy — never raw exception strings.
        final err = AppError.from(e);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(err.userMessage)),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_actions.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: const [
              Icon(Icons.event_available, size: 64, color: AppColors.textTertiary),
              SizedBox(height: AppSpacing.md),
              Text(
                'No pending actions or reminders',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              SizedBox(height: AppSpacing.xs),
              Text(
                'Actions recommended from policy expirations and GST deadlines will show up here.',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppColors.textSecondary),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadActions,
      child: ListView.builder(
        padding: const EdgeInsets.all(AppSpacing.lg),
        itemCount: _actions.length,
        itemBuilder: (context, index) {
          final action = _actions[index];
          final dueStr = action.dueDate != null
              ? DateFormat('dd MMM yyyy').format(action.dueDate!)
              : 'No deadline';

          return Card(
            margin: const EdgeInsets.only(bottom: AppSpacing.md),
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Text(
                          action.title,
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: action.status == 'CONFIRMED'
                              ? const Color(0xFFDCFCE7)
                              : const Color(0xFFFEF3C7),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          action.status,
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: action.status == 'CONFIRMED'
                                ? AppColors.success
                                : AppColors.riskMedium,
                          ),
                        ),
                      ),
                    ],
                  ),
                  if (action.description != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      action.description!,
                      style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                    ),
                  ],
                  const SizedBox(height: AppSpacing.sm),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.calendar_today, size: 14, color: AppColors.textTertiary),
                          const SizedBox(width: 4),
                          Text(
                            'Due: $dueStr',
                            style: const TextStyle(fontSize: 12, color: AppColors.textTertiary),
                          ),
                        ],
                      ),
                      if (action.status == 'PENDING')
                        TextButton(
                          onPressed: () => _confirmAction(action),
                          child: const Text('Approve Action'),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
