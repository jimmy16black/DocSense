import 'package:flutter/material.dart';

/// Staggered fade and slide-in animation for list items and cards.
/// Provides a fluid, high-frame-rate entry feel.
class StaggeredFadeSlide extends StatefulWidget {
  final Widget child;
  final int index;
  final Duration duration;
  final Duration delayPerItem;
  final Offset slideOffset;

  const StaggeredFadeSlide({
    super.key,
    required this.child,
    required this.index,
    this.duration = const Duration(milliseconds: 380),
    this.delayPerItem = const Duration(milliseconds: 45),
    this.slideOffset = const Offset(0, 20),
  });

  @override
  State<StaggeredFadeSlide> createState() => _StaggeredFadeSlideState();
}

class _StaggeredFadeSlideState extends State<StaggeredFadeSlide>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _fadeAnimation;
  late final Animation<Offset> _slideAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: widget.duration,
    );

    final curvedAnimation = CurvedAnimation(
      parent: _controller,
      curve: Curves.easeOutCubic,
    );

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(curvedAnimation);
    _slideAnimation = Tween<Offset>(
      begin: widget.slideOffset,
      end: Offset.zero,
    ).animate(curvedAnimation);

    // Calculate staggered delay, capped at 300ms
    final delayMs = (widget.index * widget.delayPerItem.inMilliseconds).clamp(0, 300);
    Future.delayed(Duration(milliseconds: delayMs), () {
      if (mounted) {
        _controller.forward();
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Opacity(
          opacity: _fadeAnimation.value,
          child: Transform.translate(
            offset: _slideAnimation.value,
            child: child,
          ),
        );
      },
      child: widget.child,
    );
  }
}
