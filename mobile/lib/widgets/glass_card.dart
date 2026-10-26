import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// A sleek glassmorphic container with backdrop blur, specular border highlight,
/// and tactile micro-press spring animation.
class GlassCard extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  final double blur;
  final BorderRadius? borderRadius;
  final EdgeInsetsGeometry? padding;
  final EdgeInsetsGeometry? margin;
  final Color? backgroundColor;
  final Gradient? backgroundGradient;
  final Gradient? borderGradient;
  final double borderWidth;
  final List<BoxShadow>? shadows;
  final double scaleOnTap;
  final bool enableHaptics;

  const GlassCard({
    super.key,
    required this.child,
    this.onTap,
    this.blur = 12.0,
    this.borderRadius,
    this.padding,
    this.margin,
    this.backgroundColor,
    this.backgroundGradient,
    this.borderGradient,
    this.borderWidth = 1.0,
    this.shadows,
    this.scaleOnTap = 0.97,
    this.enableHaptics = true,
  });

  @override
  State<GlassCard> createState() => _GlassCardState();
}

class _GlassCardState extends State<GlassCard> {
  bool _isPressed = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final radius = widget.borderRadius ?? BorderRadius.circular(16);

    final defaultBgGradient = LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: isDark
          ? [
              const Color(0xFF1E293B).withValues(alpha: 0.70),
              const Color(0xFF0F172A).withValues(alpha: 0.50),
            ]
          : [
              Colors.white.withValues(alpha: 0.78),
              Colors.white.withValues(alpha: 0.52),
            ],
    );

    final defaultBorderGradient = LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: isDark
          ? [
              Colors.white.withValues(alpha: 0.22),
              Colors.white.withValues(alpha: 0.05),
            ]
          : [
              Colors.white.withValues(alpha: 0.85),
              Colors.white.withValues(alpha: 0.25),
            ],
    );

    final defaultShadows = [
      BoxShadow(
        color: isDark
            ? Colors.black.withValues(alpha: 0.35)
            : const Color(0xFF0F172A).withValues(alpha: 0.06),
        blurRadius: 18,
        offset: const Offset(0, 8),
      ),
      BoxShadow(
        color: isDark
            ? Colors.black.withValues(alpha: 0.20)
            : const Color(0xFF0F172A).withValues(alpha: 0.03),
        blurRadius: 6,
        offset: const Offset(0, 2),
      ),
    ];

    Widget content = Container(
      decoration: BoxDecoration(
        borderRadius: radius,
        gradient: widget.backgroundColor == null
            ? (widget.backgroundGradient ?? defaultBgGradient)
            : null,
        color: widget.backgroundColor,
      ),
      padding: widget.padding ?? const EdgeInsets.all(16),
      child: widget.child,
    );

    // Apply border gradient overlay if specified
    final borderGrad = widget.borderGradient ?? defaultBorderGradient;
    final innerBorder = CustomPaint(
      painter: _GradientBorderPainter(
        gradient: borderGrad,
        radius: radius,
        strokeWidth: widget.borderWidth,
      ),
      child: content,
    );

    Widget card = Container(
      margin: widget.margin,
      decoration: BoxDecoration(
        borderRadius: radius,
        boxShadow: widget.shadows ?? defaultShadows,
      ),
      child: ClipRRect(
        borderRadius: radius,
        child: BackdropFilter(
          filter: ImageFilter.blur(
            sigmaX: widget.blur,
            sigmaY: widget.blur,
          ),
          child: innerBorder,
        ),
      ),
    );

    if (widget.onTap != null) {
      card = GestureDetector(
        onTapDown: (_) {
          if (widget.enableHaptics) {
            HapticFeedback.lightImpact();
          }
          setState(() => _isPressed = true);
        },
        onTapUp: (_) => setState(() => _isPressed = false),
        onTapCancel: () => setState(() => _isPressed = false),
        onTap: widget.onTap,
        behavior: HitTestBehavior.opaque,
        child: AnimatedScale(
          scale: _isPressed ? widget.scaleOnTap : 1.0,
          duration: const Duration(milliseconds: 110),
          curve: Curves.easeOutCubic,
          child: card,
        ),
      );
    }

    return card;
  }
}

class _GradientBorderPainter extends CustomPainter {
  final Gradient gradient;
  final BorderRadius radius;
  final double strokeWidth;

  _GradientBorderPainter({
    required this.gradient,
    required this.radius,
    required this.strokeWidth,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (strokeWidth <= 0) return;

    final rect = Offset.zero & size;
    final rrect = radius.toRRect(rect).deflate(strokeWidth / 2);

    final paint = Paint()
      ..shader = gradient.createShader(rect)
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth;

    canvas.drawRRect(rrect, paint);
  }

  @override
  bool shouldRepaint(covariant _GradientBorderPainter oldDelegate) {
    return oldDelegate.gradient != gradient ||
        oldDelegate.radius != radius ||
        oldDelegate.strokeWidth != strokeWidth;
  }
}
