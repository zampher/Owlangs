// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:math' as math;
import 'package:flutter/material.dart';

class _LetterBurstParticle {
  const _LetterBurstParticle(
    this.char,
    this.angle,
    this.maxDistance,
    this.delay,
  );
  final String char;
  final double angle; // radians
  final double maxDistance;
  final double delay;
}

const List<_LetterBurstParticle> _letterBurstParticles = <_LetterBurstParticle>[
  _LetterBurstParticle('A', -math.pi + (2 * math.pi / 26) * 0, 78, 0),
  _LetterBurstParticle('Q', -math.pi + (2 * math.pi / 26) * 16, 71, 0.03),
  _LetterBurstParticle('H', -math.pi + (2 * math.pi / 26) * 7, 86, 0.06),
  _LetterBurstParticle('T', -math.pi + (2 * math.pi / 26) * 19, 66, 0.09),
  _LetterBurstParticle('C', -math.pi + (2 * math.pi / 26) * 2, 83, 0.12),
  _LetterBurstParticle('Z', -math.pi + (2 * math.pi / 26) * 25, 84, 0.15),
  _LetterBurstParticle('B', -math.pi + (2 * math.pi / 26) * 1, 70, 0.18),
  _LetterBurstParticle('R', -math.pi + (2 * math.pi / 26) * 17, 85, 0.21),
  _LetterBurstParticle('K', -math.pi + (2 * math.pi / 26) * 10, 82, 0.24),
  _LetterBurstParticle('E', -math.pi + (2 * math.pi / 26) * 4, 68, 0.27),
  _LetterBurstParticle('Y', -math.pi + (2 * math.pi / 26) * 24, 70, 0.30),
  _LetterBurstParticle('D', -math.pi + (2 * math.pi / 26) * 3, 74, 0.33),
  _LetterBurstParticle('U', -math.pi + (2 * math.pi / 26) * 20, 81, 0.36),
  _LetterBurstParticle('L', -math.pi + (2 * math.pi / 26) * 11, 73, 0.39),
  _LetterBurstParticle('O', -math.pi + (2 * math.pi / 26) * 14, 69, 0.42),
  _LetterBurstParticle('S', -math.pi + (2 * math.pi / 26) * 18, 74, 0.45),
  _LetterBurstParticle('V', -math.pi + (2 * math.pi / 26) * 21, 72, 0.48),
  _LetterBurstParticle('W', -math.pi + (2 * math.pi / 26) * 22, 87, 0.51),
  _LetterBurstParticle('X', -math.pi + (2 * math.pi / 26) * 23, 77, 0.54),
  _LetterBurstParticle('N', -math.pi + (2 * math.pi / 26) * 13, 76, 0.57),
  _LetterBurstParticle('G', -math.pi + (2 * math.pi / 26) * 6, 72, 0.60),
  _LetterBurstParticle('P', -math.pi + (2 * math.pi / 26) * 15, 83, 0.63),
  _LetterBurstParticle('J', -math.pi + (2 * math.pi / 26) * 9, 67, 0.66),
  _LetterBurstParticle('F', -math.pi + (2 * math.pi / 26) * 5, 80, 0.69),
  _LetterBurstParticle('I', -math.pi + (2 * math.pi / 26) * 8, 75, 0.72),
  _LetterBurstParticle('M', -math.pi + (2 * math.pi / 26) * 12, 88, 0.75),
];

/// Animated owl logo widget showing document processing workflow
///
/// Animation flow:
/// 1. Document travels from the user (left) to the owl (center)
/// 2. Document moves into the cloud service on the right for processing
/// 3. Cloud animates/shakes and emits characters while processing
/// 4. Document returns to the owl and then back to the user
class AnimatedOwlLogo extends StatefulWidget {
  const AnimatedOwlLogo({
    super.key,
    this.width = 512,
    this.height = 256,
    this.animationDuration = const Duration(seconds: 16),
    this.autoPlay = true,
  });
  final double width;
  final double height;
  final Duration animationDuration;
  final bool autoPlay;

  @override
  State<AnimatedOwlLogo> createState() => _AnimatedOwlLogoState();
}

class _AnimatedOwlLogoState extends State<AnimatedOwlLogo>
    with TickerProviderStateMixin {
  late AnimationController _mainController;
  late AnimationController _blinkController;
  late AnimationController _cloudController;

  // Document position animation (0.0 = left, 1.0 = right)
  late Animation<double> _documentPosition;

  // Document Y position (lower to be near owl's feet)
  late Animation<double> _documentY;

  late Animation<double> _documentVisibility;
  late Animation<double> _cloudShake;
  late Animation<double> _letterBurstProgress;

  // Cloud processing animation
  late Animation<double> _cloudScale;
  late Animation<double> _cloudRotation;

  // Owl blink animation
  late Animation<double> _eyeScale;

  @override
  void initState() {
    super.initState();

    // Main animation controller (16 seconds loop)
    _mainController = AnimationController(
      duration: widget.animationDuration,
      vsync: this,
    );

    // Blink controller (for panda eyes)
    _blinkController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );

    // Cloud processing controller (continuous rotation - 10 seconds per rotation)
    _cloudController = AnimationController(
      duration: const Duration(seconds: 12),
      vsync: this,
    );

    // Cloud rotation animation (continuous)
    _cloudRotation = Tween<double>(
      begin: 0,
      end: 2 * math.pi, // Full rotation in radians
    ).animate(
      CurvedAnimation(
        parent: _cloudController,
        curve: Curves.linear,
      ),
    );

    // Document position: Single cycle (16s)
    // Flow: user -> owl -> cloud (pause 8s) -> owl -> user
    _documentPosition = TweenSequence<double>(<TweenSequenceItem<double>>[
      TweenSequenceItem(
        tween: Tween<double>(begin: 0, end: 1).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 1,
      ), // 0-1s: user to owl
      TweenSequenceItem(
        tween: ConstantTween<double>(1),
        weight: 0.5,
      ), // 1-1.5s: at owl
      TweenSequenceItem(
        tween: Tween<double>(begin: 1, end: 2).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 1,
      ), // 1.5-2.5s: owl to cloud
      TweenSequenceItem(
        tween: ConstantTween<double>(2),
        weight: 8,
      ), // 2.5-10.5s: stay at cloud
      TweenSequenceItem(
        tween: Tween<double>(begin: 2, end: 3).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 1,
      ), // 10.5-11.5s: cloud to owl
      TweenSequenceItem(
        tween: ConstantTween<double>(3),
        weight: 0.5,
      ), // 11.5-12s: at owl
      TweenSequenceItem(
        tween: Tween<double>(begin: 3, end: 4).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 1,
      ), // 12-13s: owl to user
      TweenSequenceItem(
        tween: ConstantTween<double>(4),
        weight: 3,
      ), // 13-16s: rest at user
    ]).animate(_mainController);

    const double userDocY = 25;
    const double owlDocY = 57;
    const double cloudDocY = 5;
    _documentY = TweenSequence<double>(<TweenSequenceItem<double>>[
      TweenSequenceItem(
        tween: Tween<double>(begin: userDocY, end: owlDocY).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 1,
      ), // user -> owl
      TweenSequenceItem(
        tween: ConstantTween<double>(owlDocY),
        weight: 0.5,
      ), // at owl
      TweenSequenceItem(
        tween: Tween<double>(begin: owlDocY, end: cloudDocY).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 1,
      ), // owl -> cloud
      TweenSequenceItem(
        tween: ConstantTween<double>(cloudDocY),
        weight: 8,
      ), // stay at cloud
      TweenSequenceItem(
        tween: Tween<double>(begin: cloudDocY, end: owlDocY).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 1,
      ), // cloud -> owl
      TweenSequenceItem(
        tween: ConstantTween<double>(owlDocY),
        weight: 0.5,
      ), // at owl
      TweenSequenceItem(
        tween: Tween<double>(begin: owlDocY, end: userDocY).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 1,
      ), // owl -> user
      TweenSequenceItem(
        tween: ConstantTween<double>(userDocY),
        weight: 3,
      ), // rest at user
    ]).animate(_mainController);

    _documentVisibility = TweenSequence<double>(<TweenSequenceItem<double>>[
      TweenSequenceItem(
        tween: ConstantTween<double>(1),
        weight: 2.5,
      ), // visible until cloud
      TweenSequenceItem(
        tween: Tween<double>(begin: 1, end: 0).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 0.5,
      ), // fade out entering cloud
      TweenSequenceItem(
        tween: ConstantTween<double>(0),
        weight: 7.5,
      ), // hidden while processing
      TweenSequenceItem(
        tween: Tween<double>(begin: 0, end: 1).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 0.5,
      ), // fade in when leaving cloud
      TweenSequenceItem(
        tween: ConstantTween<double>(1),
        weight: 1.5,
      ), // visible back at owl
      TweenSequenceItem(
        tween: Tween<double>(begin: 1, end: 0).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 0.5,
      ), // fade out before reaching user
      TweenSequenceItem(
        tween: ConstantTween<double>(0),
        weight: 3,
      ), // hidden at user rest
    ]).animate(_mainController);

    _cloudShake = TweenSequence<double>(<TweenSequenceItem<double>>[
      TweenSequenceItem(tween: ConstantTween<double>(0), weight: 2.5),
      TweenSequenceItem(
        tween: Tween<double>(begin: 0, end: 1).chain(
          CurveTween(curve: Curves.easeIn),
        ),
        weight: 0.5,
      ),
      TweenSequenceItem(tween: ConstantTween<double>(1), weight: 7),
      TweenSequenceItem(
        tween: Tween<double>(begin: 1, end: 0).chain(
          CurveTween(curve: Curves.easeOut),
        ),
        weight: 0.5,
      ),
      TweenSequenceItem(tween: ConstantTween<double>(0), weight: 5.5),
    ]).animate(_mainController);

    _letterBurstProgress = TweenSequence<double>(<TweenSequenceItem<double>>[
      TweenSequenceItem(tween: ConstantTween<double>(0), weight: 2.5),
      TweenSequenceItem(
        tween: Tween<double>(begin: 0, end: 1).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 11,
      ), // keep burst active longer (~11s)
      TweenSequenceItem(tween: ConstantTween<double>(0), weight: 2.5),
    ]).animate(_mainController);

    // Cloud scale animation (pulsing during processing)
    _cloudScale = TweenSequence<double>(<TweenSequenceItem<double>>[
      TweenSequenceItem(
        tween: ConstantTween<double>(1),
        weight: 2.5,
      ), // 0-2.5s: normal
      TweenSequenceItem(
        tween: Tween<double>(begin: 1, end: 1.2).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 0.25,
      ), // 2.5-2.75s: scale up
      TweenSequenceItem(
        tween: Tween<double>(begin: 1.2, end: 1).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 0.25,
      ), // 2.75-3s: scale down
      TweenSequenceItem(
        tween: ConstantTween<double>(1),
        weight: 5,
      ), // 3-8s: normal
    ]).animate(_mainController);

    // Panda eye blink animation
    _eyeScale = TweenSequence<double>(<TweenSequenceItem<double>>[
      TweenSequenceItem(
        tween: ConstantTween<double>(1),
        weight: 1.2,
      ), // 0-1.2s: normal
      TweenSequenceItem(
        tween: Tween<double>(begin: 1, end: 0.3).chain(
          CurveTween(curve: Curves.easeIn),
        ),
        weight: 0.15,
      ), // 1.2-1.35s: close
      TweenSequenceItem(
        tween: Tween<double>(begin: 0.3, end: 1).chain(
          CurveTween(curve: Curves.easeOut),
        ),
        weight: 0.15,
      ), // 1.35-1.5s: open
      TweenSequenceItem(
        tween: ConstantTween<double>(1),
        weight: 3.5,
      ), // 1.5-5s: normal
      TweenSequenceItem(
        tween: Tween<double>(begin: 1, end: 0.3).chain(
          CurveTween(curve: Curves.easeIn),
        ),
        weight: 0.15,
      ), // 5-5.15s: close
      TweenSequenceItem(
        tween: Tween<double>(begin: 0.3, end: 1).chain(
          CurveTween(curve: Curves.easeOut),
        ),
        weight: 0.15,
      ), // 5.15-5.3s: open
      TweenSequenceItem(
        tween: ConstantTween<double>(1),
        weight: 2.7,
      ), // 5.3-8s: normal
    ]).animate(_mainController);

    // Start animations - play once instead of looping to save resources
    if (widget.autoPlay) {
      Future<void> playLoop(int remainingLoops) async {
        if (remainingLoops <= 0) {
          _cloudController.stop();
          return;
        }
        await _mainController.forward(from: 0);
        await playLoop(remainingLoops - 1);
      }

      _cloudController.forward();
      playLoop(3);
    }
  }

  @override
  void dispose() {
    _mainController.dispose();
    _blinkController.dispose();
    _cloudController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final isLight = theme.brightness == Brightness.light;

    // Use SVG theme color (#1976D2) for light theme to match owlangs_owl_solid.svg
    final primaryColor = isLight
        ? const Color(0xFF1976D2) // SVG theme color
        : colorScheme.primary;
    final secondaryColor = isLight
        ? const Color(0xFF64B5F6) // Light blue variant for cloud highlights
        : colorScheme.secondary;
    final onPrimaryColor = isLight
        ? Colors.white // White for contrast on blue background
        : colorScheme.onPrimary;

    return SizedBox(
      width: widget.width,
      height: widget.height,
      child: CustomPaint(
        painter: _AnimatedOwlPainter(
          documentPosition: _documentPosition,
          documentY: _documentY,
          documentVisibility: _documentVisibility,
          cloudShake: _cloudShake,
          letterBurstProgress: _letterBurstProgress,
          cloudScale: _cloudScale,
          cloudRotation: _cloudRotation,
          eyeScale: _eyeScale,
          backgroundColor: colorScheme.surface,
          primaryColor: primaryColor,
          secondaryColor: secondaryColor,
          onPrimaryColor: onPrimaryColor,
          onSurfaceVariantColor: colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }
}

class _AnimatedOwlPainter extends CustomPainter {
  _AnimatedOwlPainter({
    required this.documentPosition,
    required this.documentY,
    required this.documentVisibility,
    required this.cloudShake,
    required this.letterBurstProgress,
    required this.cloudScale,
    required this.cloudRotation,
    required this.eyeScale,
    required this.backgroundColor,
    required this.primaryColor,
    required this.secondaryColor,
    required this.onPrimaryColor,
    required this.onSurfaceVariantColor,
  }) : super(
          repaint: Listenable.merge(<Listenable?>[
            documentPosition,
            documentY,
            documentVisibility,
            cloudShake,
            letterBurstProgress,
            cloudScale,
            cloudRotation,
            eyeScale,
          ]),
        );
  final Animation<double> documentPosition;
  final Animation<double> documentY;
  final Animation<double> documentVisibility;
  final Animation<double> cloudShake;
  final Animation<double> letterBurstProgress;
  final Animation<double> cloudScale;
  final Animation<double> cloudRotation;
  final Animation<double> eyeScale;
  final Color backgroundColor;
  final Color primaryColor;
  final Color secondaryColor;
  final Color onPrimaryColor;
  final Color onSurfaceVariantColor;
  @override
  void paint(Canvas canvas, Size size) {
    // Background
    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.width, size.height),
      Paint()..color = backgroundColor,
    );

    // Shift entire animation left by 40 pixels
    canvas.save();
    canvas.translate(-40, 0);

    final centerY = size.height / 2;
    final centerX = size.width / 2;
    final leftX = centerX - 75.0; // User icon position (closer to owl)
    final rightX = size.width - 50.0;

    // Left: User icon (simple person silhouette)
    _drawUserIcon(canvas, Offset(leftX, centerY));

    // Right: Cloud (LLM service)
    final cloudScaleValue = cloudScale.value;
    canvas.save();
    canvas.translate(rightX, centerY - 40);
    canvas.scale(cloudScaleValue);
    _drawCloudIcon(
      canvas,
      Offset.zero,
      cloudRotation.value,
      cloudShake.value,
      letterBurstProgress.value,
    );
    canvas.restore();

    // Center: Panda
    _drawPanda(canvas, Offset(centerX, centerY), eyeScale.value);

    // Document position & height: 0=user, 1=owl, 2=cloud, 3=back at owl, 4=user
    final owlDocX = centerX + 12;
    double docX;
    if (documentPosition.value <= 1.0) {
      docX = leftX + (owlDocX - leftX) * documentPosition.value;
    } else if (documentPosition.value <= 2.0) {
      docX = owlDocX + (rightX - owlDocX) * (documentPosition.value - 1.0);
    } else if (documentPosition.value <= 3.0) {
      docX = rightX - (rightX - owlDocX) * (documentPosition.value - 2.0);
    } else {
      docX = owlDocX - (owlDocX - leftX) * (documentPosition.value - 3.0);
    }
    final docY = centerY + documentY.value;
    final docVisibility = documentVisibility.value;
    if (docVisibility > 0) {
      _drawDocument(canvas, Offset(docX, docY));
    }

    // Restore canvas after shifting
    canvas.restore();
  }

  void _drawUserIcon(Canvas canvas, Offset center) {
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 10 // Thick lines for bold, simple style
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..color = primaryColor;

    canvas.save();
    canvas.translate(center.dx, center.dy + 15);
    canvas.scale(0.5);

    // Person sitting (very simple - just essential elements)
    // Head (circle) - positioned at top
    canvas.drawCircle(const Offset(-15, -15), 14, paint);

    // Body (thick vertical line segment from head to hip)
    final bodyPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 16 // Thicker for body
      ..strokeCap = StrokeCap.round
      ..color = primaryColor;
    canvas.drawLine(const Offset(-15, -1), const Offset(-15, 15), bodyPaint);

    // Legs (bent, sitting position - two segments)
    final legPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 12 // Medium thickness for legs
      ..strokeCap = StrokeCap.round
      ..color = primaryColor;
    // Left leg (bent forward)
    canvas.drawLine(const Offset(-15, 15), const Offset(-5, 25), legPaint);
    // Right leg (bent forward)
    canvas.drawLine(const Offset(-15, 15), const Offset(-25, 25), legPaint);

    // Laptop - positioned to the right with more spacing from person
    canvas.save();
    canvas.translate(35, 10); // Position further to the right with more spacing
    canvas.rotate(0.2); // Slight tilt

    // Laptop base
    final laptopRect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: const Offset(0, 2), width: 24, height: 16),
      const Radius.circular(2),
    );
    canvas.drawRRect(laptopRect, paint);

    // Laptop screen (upper part)
    final screenRect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: const Offset(0, -6), width: 22, height: 14),
      const Radius.circular(2),
    );
    canvas.drawRRect(screenRect, paint);

    // Screen content (simple grid lines)
    final screenPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..color = primaryColor.withOpacity(0.6);
    canvas.drawLine(const Offset(-9, -9), const Offset(9, -9), screenPaint);
    canvas.drawLine(const Offset(-9, -6), const Offset(9, -6), screenPaint);
    canvas.drawLine(const Offset(-9, -3), const Offset(9, -3), screenPaint);

    canvas.restore();

    canvas.restore();
  }

  void _drawPanda(Canvas canvas, Offset center, double eyeScale) {
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..color = primaryColor; // themable color

    final fillPaint = Paint()
      ..style = PaintingStyle.fill
      ..color = primaryColor;

    canvas.save();
    canvas.translate(center.dx, center.dy);
    canvas.scale(0.6);

    // Head (semi-circle with thicker cap - matching SVG)
    final headPath = Path()
      ..moveTo(-92.5, -58.3)
      ..quadraticBezierTo(0, -142.12, 92.5, -58.3);
    // Draw with thicker stroke to match SVG's stroke-width:20
    final thickPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 12 // 20 * 0.6 scale
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..color = primaryColor;
    canvas.drawPath(headPath, thickPaint);

    // Face mask (removed in SVG, but keep for panda face structure)
    // Panda has distinctive black eye patches, so we'll draw those instead

    // Eyes (enlarged - doubled in size to match SVG)
    const eyeLeft = Offset(-32.5, -39.7);
    const eyeRight = Offset(32.5, -39.7);
    // Eye radius doubled: 27.675442 * 0.6 (scale) * 2 (double size) = 33.2
    const eyeRadiusX = 33.2;
    const eyeRadiusY = 33.6; // 27.939064 * 0.6 * 2

    // Panda eye patches (black circles around eyes)
    canvas.drawOval(
      Rect.fromCenter(
        center: eyeLeft,
        width: eyeRadiusX * 2,
        height: eyeRadiusY * 2,
      ),
      fillPaint, // Filled for panda's black eye patches
    );
    canvas.drawOval(
      Rect.fromCenter(
        center: eyeRight,
        width: eyeRadiusX * 2,
        height: eyeRadiusY * 2,
      ),
      fillPaint,
    );

    // Pupils (white/blue circles inside eye patches, with blink effect)
    final pupilRadius = 11.07 * eyeScale;
    final pupilPaint = Paint()
      ..style = PaintingStyle.fill
      ..color = onPrimaryColor; // contrast color
    canvas.drawCircle(eyeLeft, pupilRadius, pupilPaint);
    canvas.drawCircle(eyeRight, pupilRadius, pupilPaint);
    // Small black dots in center
    final blackDotPaint = Paint()
      ..style = PaintingStyle.fill
      ..color = primaryColor;
    canvas.drawCircle(eyeLeft, pupilRadius * 0.4, blackDotPaint);
    canvas.drawCircle(eyeRight, pupilRadius * 0.4, blackDotPaint);

    // Nose (panda has a black nose, similar to beak position but rounded)
    final nosePath = Path()
      ..addOval(
        Rect.fromCenter(center: const Offset(0, -19.2), width: 12, height: 10),
      );
    canvas.drawPath(nosePath, fillPaint);

    // Mouth (small curve below nose)
    final mouthPath = Path()
      ..moveTo(-6, -12)
      ..quadraticBezierTo(0, -8, 6, -12);
    canvas.drawPath(mouthPath, paint..strokeWidth = 3);

    // Body outline
    final bodyLeft = Path()
      ..moveTo(-64.5, -35)
      ..quadraticBezierTo(-73.8, 16.2, -41.5, 48.8);
    canvas.drawPath(bodyLeft, paint);

    final bodyRight = Path()
      ..moveTo(64.5, -35)
      ..quadraticBezierTo(73.8, 16.2, 41.5, 48.8);
    canvas.drawPath(bodyRight, paint);

    // Left leg and claws
    canvas.drawLine(
      const Offset(-41.5, 48.8),
      const Offset(-46.1, 62.8),
      paint,
    );
    canvas.drawLine(const Offset(-46.1, 62.8), const Offset(-53, 62.8), paint);

    // Right leg and claws (will be extended when locking/unlocking)
    const rightLegEnd = Offset(46.1, 62.8);
    canvas.drawLine(const Offset(41.5, 48.8), rightLegEnd, paint);

    // Document lines (positioned closer to panda's feet, matching SVG)
    const docY = 62.8; // Match the panda's foot position
    canvas.drawLine(const Offset(-73.8, docY), const Offset(73.8, docY), paint);
    canvas.drawLine(
      const Offset(-73.8, docY + 18.6),
      const Offset(73.8, docY + 18.6),
      paint,
    );
    canvas.drawLine(
      const Offset(-73.8, docY + 37.2),
      const Offset(73.8, docY + 37.2),
      paint,
    );

    canvas.restore();
  }

  void _drawCloudIcon(
    Canvas canvas,
    Offset center,
    double rotation,
    double shake,
    double letterProgress,
  ) {
    final baseBlue = primaryColor;
    final lightBlue = secondaryColor;
    final cloudPaint = Paint()
      ..style = PaintingStyle.fill
      ..color = baseBlue;

    final shakeOffsetX = math.sin(shake * math.pi * 8) * 5 * shake;
    final shakeOffsetY = math.cos(shake * math.pi * 6) * 4 * shake;
    final shakeRotation = math.sin(shake * math.pi * 5) * 0.08 * shake;
    canvas.save();
    canvas.translate(shakeOffsetX, shakeOffsetY);
    canvas.rotate(shakeRotation);

    // Additional cloud 1 (left, partially overlapping)
    final cloud1Paint = Paint()
      ..style = PaintingStyle.fill
      ..color = lightBlue.withOpacity(0.9);
    canvas.drawCircle(Offset(center.dx - 35, center.dy - 5), 12, cloud1Paint);
    canvas.drawCircle(Offset(center.dx - 25, center.dy - 15), 15, cloud1Paint);
    canvas.drawCircle(Offset(center.dx - 15, center.dy - 8), 13, cloud1Paint);
    final cloud1BaseRect = Rect.fromCenter(
      center: Offset(center.dx - 25, center.dy + 2),
      width: 50,
      height: 20,
    );
    canvas.drawOval(cloud1BaseRect, cloud1Paint);

    // Additional cloud 2 (right, partially overlapping)
    final cloud2Paint = Paint()
      ..style = PaintingStyle.fill
      ..color = lightBlue.withOpacity(0.9);
    canvas.drawCircle(Offset(center.dx + 15, center.dy - 8), 13, cloud2Paint);
    canvas.drawCircle(Offset(center.dx + 25, center.dy - 15), 15, cloud2Paint);
    canvas.drawCircle(Offset(center.dx + 35, center.dy - 5), 12, cloud2Paint);
    final cloud2BaseRect = Rect.fromCenter(
      center: Offset(center.dx + 25, center.dy + 2),
      width: 50,
      height: 20,
    );
    canvas.drawOval(cloud2BaseRect, cloud2Paint);

    // Main cloud bubbles (on top, fully opaque)
    canvas.drawCircle(Offset(center.dx - 18, center.dy + 2), 14, cloudPaint);
    canvas.drawCircle(Offset(center.dx, center.dy - 10), 18, cloudPaint);
    canvas.drawCircle(Offset(center.dx + 18, center.dy + 4), 16, cloudPaint);

    // Base ellipse
    final baseRect = Rect.fromCenter(
      center: Offset(center.dx, center.dy + 12),
      width: 60,
      height: 24,
    );
    canvas.drawOval(baseRect, cloudPaint);

    // Server indicator inside cloud
    final serverPaint = Paint()
      ..style = PaintingStyle.fill
      ..color = onPrimaryColor.withOpacity(0.9);
    final serverRect = RRect.fromRectAndRadius(
      Rect.fromCenter(
        center: Offset(center.dx, center.dy + 5),
        width: 32,
        height: 20,
      ),
      const Radius.circular(4),
    );
    canvas.drawRRect(serverRect, serverPaint);

    final aiTextPainter = TextPainter(
      text: TextSpan(
        text: 'AI',
        style: TextStyle(
          color:
              onPrimaryColor, // Use theme-aware color (white in light, appropriate contrast in dark)
          fontSize: 13,
          fontWeight: FontWeight.bold,
        ),
      ),
      textDirection: TextDirection.ltr,
      textAlign: TextAlign.center,
    );
    aiTextPainter.layout();
    aiTextPainter.paint(
      canvas,
      Offset(center.dx - aiTextPainter.width / 2, center.dy + 5),
    );

    // Server vents
    final ventPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round
      ..color = baseBlue.withOpacity(0.85);
    canvas.drawLine(
      Offset(center.dx - 10, center.dy + 1),
      Offset(center.dx + 10, center.dy + 1),
      ventPaint,
    );
    canvas.drawLine(
      Offset(center.dx - 10, center.dy + 6),
      Offset(center.dx + 10, center.dy + 6),
      ventPaint,
    );

    if (letterProgress > 0) {
      _drawLetterBurst(
        canvas,
        Offset(center.dx, center.dy - 5),
        letterProgress,
      );
    }

    canvas.restore();
  }

  void _drawLetterBurst(Canvas canvas, Offset origin, double progressValue) {
    for (final particle in _letterBurstParticles) {
      final effective = (progressValue - particle.delay).clamp(0.0, 1.0);
      if (effective <= 0) continue;
      final eased = Curves.easeOut.transform(effective);
      final distance = particle.maxDistance * eased;
      final dx = origin.dx + math.cos(particle.angle) * distance;
      final dy = origin.dy + math.sin(particle.angle) * distance - eased * 10;
      final opacity = (1 - eased).clamp(0.0, 1.0);
      final textPainter = TextPainter(
        text: TextSpan(
          text: particle.char,
          style: TextStyle(
            color: onPrimaryColor.withOpacity(opacity),
            fontSize: 12 + 6 * (1 - eased),
            fontWeight: FontWeight.bold,
          ),
        ),
        textDirection: TextDirection.ltr,
      );
      textPainter.layout();
      canvas.save();
      canvas.translate(dx - textPainter.width / 2, dy - textPainter.height / 2);
      final rotation = particle.angle / 3;
      canvas.rotate(rotation);
      textPainter.paint(canvas, Offset.zero);
      canvas.restore();
    }
  }

  void _drawDocument(Canvas canvas, Offset center) {
    final docPaint = Paint()
      ..style = PaintingStyle.fill
      ..color = onPrimaryColor.withOpacity(0.95);
    final docStroke = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2
      ..color = primaryColor;

    final docRect = RRect.fromRectAndRadius(
      Rect.fromCenter(center: center, width: 24, height: 30),
      const Radius.circular(2),
    );
    canvas.drawRRect(docRect, docPaint);
    canvas.drawRRect(docRect, docStroke);

    // Document lines
    final linePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = primaryColor;

    canvas.drawLine(
      Offset(center.dx - 9, center.dy - 8),
      Offset(center.dx + 9, center.dy - 8),
      linePaint,
    );
    canvas.drawLine(
      Offset(center.dx - 9, center.dy - 3),
      Offset(center.dx + 9, center.dy - 3),
      linePaint,
    );
    canvas.drawLine(
      Offset(center.dx - 9, center.dy + 2),
      Offset(center.dx - 1, center.dy + 2),
      linePaint,
    );

    // Draw "1037" text on document
    final textPainter = TextPainter(
      text: TextSpan(
        text: '1037',
        style: TextStyle(
          color: primaryColor,
          fontSize: 8,
          fontWeight: FontWeight.bold,
        ),
      ),
      textDirection: TextDirection.ltr,
      textAlign: TextAlign.center,
    );
    textPainter.layout();
    textPainter.paint(
      canvas,
      Offset(
        center.dx - textPainter.width / 2,
        center.dy + 6, // Position below the document lines
      ),
    );

    // Paw stamp intentionally removed per latest design.
  }

  @override
  bool shouldRepaint(_AnimatedOwlPainter oldDelegate) =>
      documentPosition != oldDelegate.documentPosition ||
      documentY != oldDelegate.documentY ||
      documentVisibility != oldDelegate.documentVisibility ||
      cloudShake != oldDelegate.cloudShake ||
      letterBurstProgress != oldDelegate.letterBurstProgress ||
      cloudScale != oldDelegate.cloudScale ||
      cloudRotation != oldDelegate.cloudRotation ||
      eyeScale != oldDelegate.eyeScale;
}
