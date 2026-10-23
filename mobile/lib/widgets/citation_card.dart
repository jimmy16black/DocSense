import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';
import '../models/extraction_model.dart';

class CitationCard extends StatelessWidget {
  final CitationModel citation;
  final VoidCallback? onPageTap;

  const CitationCard({super.key, required this.citation, this.onPageTap});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.elevated,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  const Icon(Icons.bookmark_outline, size: 16, color: AppColors.primary),
                  const SizedBox(width: 4),
                  Text(
                    'Page ${citation.pageNumber}',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: AppColors.primary,
                    ),
                  ),
                  if (citation.sectionHeading != null) ...[
                    const SizedBox(width: 6),
                    Text(
                      '• ${citation.sectionHeading}',
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ],
              ),
              if (onPageTap != null)
                InkWell(
                  onTap: onPageTap,
                  child: const Text(
                    'Jump to page',
                    style: TextStyle(
                      fontSize: 11,
                      color: AppColors.primary,
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            '"${citation.exactQuote}"',
            style: const TextStyle(
              fontSize: 13,
              fontStyle: FontStyle.italic,
              color: AppColors.textPrimary,
            ),
          ),
        ],
      ),
    );
  }
}
