import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';

class ConfidenceBadge extends StatelessWidget {
  final String confidence;

  const ConfidenceBadge({super.key, required this.confidence});

  @override
  Widget build(BuildContext context) {
    Color bg;
    Color fg;
    IconData icon;
    String label;

    switch (confidence.toUpperCase()) {
      case 'HIGH':
        bg = const Color(0xFFDCFCE7);
        fg = AppColors.success;
        icon = Icons.verified_outlined;
        label = 'Verified Evidence';
        break;
      case 'MEDIUM':
        bg = const Color(0xFFFEF3C7);
        fg = AppColors.riskMedium;
        icon = Icons.info_outline;
        label = 'Moderate Confidence';
        break;
      case 'LOW':
        bg = const Color(0xFFFFEDD5);
        fg = Colors.orange;
        icon = Icons.warning_amber_rounded;
        label = 'Cautious Evidence';
        break;
      case 'UNSUPPORTED':
      default:
        bg = const Color(0xFFFEE2E2);
        fg = AppColors.riskHigh;
        icon = Icons.cancel_outlined;
        label = 'Unsupported by Doc';
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: fg),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              color: fg,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
