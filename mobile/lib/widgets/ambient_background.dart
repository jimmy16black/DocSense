import 'dart:math' as math;
import 'package:flutter/material.dart';

import '../core/theme/app_theme.dart';

/// An animated ambient background with smooth floating organic color orbs.
/// Creates depth and visual delight underneath glassmorphic cards and surfaces.
class AmbientBackground extends StatefulWidget {
  final Widget child;
  final bool animate;
  final List<Color>? orbColors;

  const AmbientBackground({
    super.key,
    required this.child,
    this.animate = true,
    this.orbColors,
  });

  @override
  State<AmbientBackground> createState() => _AmbientBackgroundState();
}

class _AmbientBackgroundState extends State<AmbientBackground>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 10),
    );
    if (widget.animate) {
      _controller.repeat(reverse: true);
    }
  }

  @override
  void didUpdateWidget(covariant AmbientBackground oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.animate != oldWidget.animate) {
      if (widget.animate) {
        _controller.repeat(reverse: true);
      } else {
        _controller.stop();
      }
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    final baseColor = isDark
        ? const Color(0xFF0F172A)
        : const Color(0xFFF8FAFC);

    final defaultOrbs = isDark
        ? [
            const Color(0xFF3B82F6).withValues(alpha: 0.18),
            const Color(0xFF6366F1).withValues(alpha: 0.15),
            const Color(0xFF06B6D4).withValues(alpha: 0.12),
          ]
        : [
            AppColors.primary.withValues(alpha: 0.12),
            const Color(0xFF8B5CF6).withValues(alpha: 0.10),
            const Color(0xFF06B6D4).withValues(alpha: 0.08),
          ];

    final colors = widget.orbColors ?? defaultOrbs;

    return Stack(
      children: [
        Positioned.fill(
          child: Container(color: baseColor),
        ),
        Positioned.fill(
          child: RepaintBoundary(
            child: AnimatedBuilder(
              animation: _controller,
              builder: (context, _) {
                final progress = _controller.value;
                return CustomPaint(
                  painter: _AmbientMeshPainter(
                    progress: progress,
                    colors: colors,
                  ),
                );
              },
            ),
          ),
        ),
        Positioned.fill(child: widget.child),
      ],
    );
  }
}

class _AmbientMeshPainter extends CustomPainter {
  final double progress;
  final List<Color> colors;

  _AmbientMeshPainter({
    required this.progress,
    required this.colors,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (size.width == 0 || size.height == 0) return;

    final angle = progress * 2 * math.pi;

    // Orb 1: Top-Right shifting
    final o1X = size.width * (0.75 + 0.15 * math.cos(angle));
    final o1Y = size.height * (0.15 + 0.10 * math.sin(angle));
    final o1Radius = size.width * 0.65;

    final paint1 = Paint()
      ..shader = RadialGradient(
        colors: [
          colors[0],
          colors[0].withValues(alpha: 0.0),
        ],
      ).createShader(Rect.fromCircle(center: Offset(o1X, o1Y), radius: o1Radius));

    canvas.drawCircle(Offset(o1X, o1Y), o1Radius, paint1);

    // Orb 2: Bottom-Left shifting
    if (colors.length > 1) {
      final o2X = size.width * (0.20 + 0.12 * math.sin(angle));
      final o2Y = size.height * (0.65 + 0.12 * math.cos(angle));
      final o2Radius = size.width * 0.70;

      final paint2 = Paint()
        ..shader = RadialGradient(
          colors: [
            colors[1],
            colors[1].withValues(alpha: 0.0),
          ],
        ).createShader(
          Rect.fromCircle(center: Offset(o2X, o2Y), radius: o2Radius),
        );

      canvas.drawCircle(Offset(o2X, o2Y), o2Radius, paint2);
    }

    // Orb 3: Center floating highlight
    if (colors.length > 2) {
      final o3X = size.width * (0.50 + 0.10 * math.cos(angle + math.pi / 3));
      final o3Y = size.height * (0.40 + 0.10 * math.sin(angle + math.pi / 3));
      final o3Radius = size.width * 0.50;

      final paint3 = Paint()
        ..shader = RadialGradient(
          colors: [
            colors[2],
            colors[2].withValues(alpha: 0.0),
          ],
        ).createShader(
          Rect.fromCircle(center: Offset(o3X, o3Y), radius: o3Radius),
        );

      canvas.drawCircle(Offset(o3X, o3Y), o3Radius, paint3);
    }
  }

  @override
  bool shouldRepaint(covariant _AmbientMeshPainter oldDelegate) {
    return oldDelegate.progress != progress || oldDelegate.colors != colors;
  }
}
