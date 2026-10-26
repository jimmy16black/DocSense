import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:docsense_mobile/widgets/glass_card.dart';
import 'package:docsense_mobile/widgets/ambient_background.dart';
import 'package:docsense_mobile/widgets/shimmer_skeleton.dart';
import 'package:docsense_mobile/widgets/staggered_fade_slide.dart';

void main() {
  group('Glass UI Widgets', () {
    testWidgets('GlassCard renders child widget and responds to onTap', (tester) async {
      bool tapped = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: GlassCard(
              onTap: () => tapped = true,
              child: const Text('Hello Glass'),
            ),
          ),
        ),
      );

      expect(find.text('Hello Glass'), findsOneWidget);

      await tester.tap(find.text('Hello Glass'));
      await tester.pumpAndSettle();

      expect(tapped, isTrue);
    });

    testWidgets('AmbientBackground renders child widget', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AmbientBackground(
              animate: false,
              child: Text('Ambient Content'),
            ),
          ),
        ),
      );

      expect(find.text('Ambient Content'), findsOneWidget);
    });

    testWidgets('StaggeredFadeSlide renders child and animates in', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: StaggeredFadeSlide(
              index: 0,
              child: Text('Sliding Item'),
            ),
          ),
        ),
      );

      expect(find.text('Sliding Item'), findsOneWidget);

      // Advance through animation
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pumpAndSettle();

      expect(find.text('Sliding Item'), findsOneWidget);
    });

    testWidgets('Shimmer and DocumentListSkeleton render placeholders', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: DocumentListSkeleton(count: 2),
          ),
        ),
      );

      expect(find.byType(DocumentCardSkeleton), findsNWidgets(2));
      // Pump a frame to advance shimmer controller
      await tester.pump(const Duration(milliseconds: 300));
      expect(find.byType(Shimmer), findsOneWidget);
    });
  });
}
