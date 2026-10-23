import 'package:flutter/material.dart';
import '../core/network/app_error.dart';
import '../core/theme/app_theme.dart';
import '../models/document_model.dart';
import '../models/qa_model.dart';
import '../services/api_service.dart';
import '../widgets/citation_card.dart';
import '../widgets/confidence_badge.dart';

class QAScreen extends StatefulWidget {
  final DocumentModel document;

  const QAScreen({super.key, required this.document});

  @override
  State<QAScreen> createState() => _QAScreenState();
}

class _QAScreenState extends State<QAScreen> {
  final ApiService _apiService = ApiService();
  final TextEditingController _controller = TextEditingController();
  final List<_ChatMessageItem> _messages = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    // Pre-populate with suggested questions from document extraction if available
    final suggestions = widget.document.latestExtraction?.suggestedQuestions ?? [];
    if (suggestions.isNotEmpty) {
      _messages.add(
        _ChatMessageItem(
          isUser: false,
          text: 'Hello! I have analyzed "${widget.document.title}". You can ask me anything about clauses, coverage, terms, or exclusions.',
          confidence: 'HIGH',
        ),
      );
    }
  }

  Future<void> _sendQuestion(String question) async {
    final trimmed = question.trim();
    if (trimmed.isEmpty || _isLoading) return;

    _controller.clear();
    setState(() {
      _messages.add(_ChatMessageItem(isUser: true, text: trimmed));
      _isLoading = true;
    });

    try {
      final response = await _apiService.askQuestion(widget.document.id, trimmed);
      setState(() {
        _messages.add(
          _ChatMessageItem(
            isUser: false,
            text: response.answer,
            confidence: response.confidence,
            citations: response.citations,
            suggestedFollowUps: response.suggestedFollowUps,
          ),
        );
        _isLoading = false;
      });
    } catch (e) {
      // BE-4: structured error → friendly copy only (no raw exception text).
      final err = AppError.from(e);
      setState(() {
        _messages.add(
          _ChatMessageItem(
            isUser: false,
            text: err.isRetryable
                ? '${err.userMessage} (Tap send to retry)'
                : err.userMessage,
            confidence: 'UNSUPPORTED',
          ),
        );
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final suggestedQuestions = widget.document.latestExtraction?.suggestedQuestions ?? [];

    return Scaffold(
      appBar: AppBar(
        title: Text('Q&A: ${widget.document.title}'),
      ),
      body: Column(
        children: [
          // Suggested Questions Chips
          if (suggestedQuestions.isNotEmpty)
            Container(
              height: 48,
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                itemCount: suggestedQuestions.length,
                itemBuilder: (context, index) {
                  final q = suggestedQuestions[index];
                  return Padding(
                    padding: const EdgeInsets.only(right: AppSpacing.sm),
                    child: ActionChip(
                      label: Text(q, style: const TextStyle(fontSize: 12)),
                      onPressed: () => _sendQuestion(q),
                    ),
                  );
                },
              ),
            ),

          // Chat Messages
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(AppSpacing.md),
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final msg = _messages[index];
                return _MessageBubble(message: msg, onSuggestionTap: _sendQuestion);
              },
            ),
          ),

          if (_isLoading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                  SizedBox(width: 8),
                  Text('Searching document & verifying quotes...', style: TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                ],
              ),
            ),

          // Input Bar
          Container(
            padding: const EdgeInsets.all(AppSpacing.md),
            decoration: const BoxDecoration(
              color: AppColors.card,
              border: Border(top: BorderSide(color: Color(0xFFE5E7EB))),
            ),
            child: SafeArea(
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      decoration: const InputDecoration(
                        hintText: 'Ask a grounded question...',
                        contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      ),
                      onSubmitted: _sendQuestion,
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  IconButton(
                    icon: const Icon(Icons.send, color: AppColors.primary),
                    onPressed: () => _sendQuestion(_controller.text),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChatMessageItem {
  final bool isUser;
  final String text;
  final String? confidence;
  final List<dynamic>? citations;
  final List<String>? suggestedFollowUps;

  _ChatMessageItem({
    required this.isUser,
    required this.text,
    this.confidence,
    this.citations,
    this.suggestedFollowUps,
  });
}

class _MessageBubble extends StatelessWidget {
  final _ChatMessageItem message;
  final Function(String) onSuggestionTap;

  const _MessageBubble({required this.message, required this.onSuggestionTap});

  @override
  Widget build(BuildContext context) {
    if (message.isUser) {
      return Align(
        alignment: Alignment.centerRight,
        child: Container(
          margin: const EdgeInsets.only(bottom: AppSpacing.sm),
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: 10),
          decoration: BoxDecoration(
            color: AppColors.primary,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            message.text,
            style: const TextStyle(color: Colors.white, fontSize: 14),
          ),
        ),
      );
    }

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: AppSpacing.md),
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFE5E7EB)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (message.confidence != null) ...[
              ConfidenceBadge(confidence: message.confidence!),
              const SizedBox(height: AppSpacing.sm),
            ],
            Text(
              message.text,
              style: const TextStyle(fontSize: 14, color: AppColors.textPrimary),
            ),
            if (message.citations != null && message.citations!.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.sm),
              const Text(
                'Source Citations:',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.textSecondary),
              ),
              ...message.citations!.map((c) => CitationCard(citation: c)),
            ],
            if (message.suggestedFollowUps != null && message.suggestedFollowUps!.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.md),
              Wrap(
                spacing: 6,
                children: message.suggestedFollowUps!.map(
                  (f) => ActionChip(
                    label: Text(f, style: const TextStyle(fontSize: 11)),
                    onPressed: () => onSuggestionTap(f),
                  ),
                ).toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
