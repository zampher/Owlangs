// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

import 'dart:math';
import 'package:flutter/material.dart';

/// Global flag to enable/disable ads (hardcoded)
/// Set to false to hide all ads
const bool kAdsEnabled = true;

/// Pleasant short slogans shown in the ad placeholder (no real ads yet)
/// Tone: light, relaxed, easy; not all translation-related.
const List<String> kAdPlaceholderSlogans = <String>[
  'Make life easy.',
  'Start your translation, then have a cup of tea.',
  'Translate with Owlangs and AI, with ease.',
  'Work smarter with Owlangs, not harder.',
  'One click, Owlangs and AI, many languages.',
  'Your words, every language. Owlangs helps you.',
  'Simple. Fast. Private.',
  'Translate better, together.',
  'Less hassle, more flow. Owlangs in the loop.',
  'Bring ideas across borders.',
  'Clear words, clear world.',
  'Take it easy. Ow...l, Ow...l, Ow...l...',
  'Breathe. Then go.',
  'Slow down, you got this.',
  'Chill vibes only.',
  'Less rush, more hush.',
  'Easy does it. Ow...l, Ow...l, Ow...l...',
  'Unwind a little. Let AI handle the rest.',
  'Keep it light. Ow...l, Ow...l, Ow...l...',
  'No hurry, no worry.',
  'Soft pace, clear mind.',
  'One step at a time.',
  'Relax. You are enough.',
  'Pause. Smile. Let AI do the heavy lifting.',
  'Gentle on yourself.',
  "Flow with AI, don't force yourself.",
  'Cozy corner energy.',
  'Simple joys. Give it to Owlangs and AI.',
  'Stay loose. Ow...l, Ow...l, Ow...l...',
  'Breezy. Ow...l, Ow...l, Ow...l...',
  'All good. Ow...l, Ow...l, Ow...l...',
  'Have a good day. Ow...l, Ow...l, Ow...l...',
  'Let Owlangs and AI work hard for you. ',
  'Thanks for your support. Keep it flowing. ',
  'Grateful for your donation. Enjoy the app!',
  'Make translation easy! Earn a little bit if possible. Lose if necessary, but make translation a piece of cake!',
  'Make document secure to use AI! Earn a little bit if possible. Lose if necessary, but make document secure to use AI!',
];

/// Number of owl poses (front, tilted, lying, playing, sleeping, waving, sitting, back, bigEyes, logo)
const int kOwlPoseCount = 10;

/// Ad placeholder widget for visualizing ad placement areas
class AdPlaceholder extends StatefulWidget {
  const AdPlaceholder({
    required this.width,
    required this.height,
    required this.label,
    this.type = AdType.banner,
    this.poseSeed,
    this.onVisibilityChanged,
    super.key,
  });

  /// Width of the ad placeholder
  final double width;

  /// Height of the ad placeholder
  final double height;

  /// Label to display on the placeholder
  final String label;

  /// Type of ad (affects styling)
  final AdType type;

  /// Optional seed for owl pose and position; when changed (e.g. on new flow), pose updates.
  final int? poseSeed;

  /// Callback when visibility changes
  final ValueChanged<bool>? onVisibilityChanged;

  @override
  State<AdPlaceholder> createState() => _AdPlaceholderState();
}

class _AdPlaceholderState extends State<AdPlaceholder> {
  bool _isVisible = true;
  late String _randomSlogan;
  late int _randomPoseIndex;
  late double _randomOffsetX;
  late double _randomOffsetY;
  late double _randomOwlScaleFactor;
  late TextAlign _randomSloganAlign;
  late double _randomSloganBottom;

  @override
  void initState() {
    super.initState();
    final r = Random();
    _randomSlogan =
        kAdPlaceholderSlogans[r.nextInt(kAdPlaceholderSlogans.length)];
    _randomPoseIndex = r.nextInt(kOwlPoseCount);
    _randomOffsetX = (r.nextDouble() - 0.5) * 0.8;
    _randomOffsetY = (r.nextDouble() - 0.5) * 0.4;
    _randomOwlScaleFactor = 0.7 + r.nextDouble() * 0.6;
    _randomSloganAlign = <TextAlign>[
      TextAlign.left,
      TextAlign.center,
      TextAlign.right,
    ][r.nextInt(3)];
    _randomSloganBottom = 4.0 + r.nextInt(3) * 4.0;
  }

  void _handleClose() {
    setState(() {
      _isVisible = false;
    });
    widget.onVisibilityChanged?.call(false);
  }

  /// True if wide banner (e.g. 728×90), false if tall rectangle (e.g. 300×250)
  bool get _isWideBanner => widget.width / widget.height > 2.0;

  int get _poseIndex {
    if (widget.poseSeed != null) {
      return widget.poseSeed! % kOwlPoseCount;
    }
    return _randomPoseIndex;
  }

  /// Push offset values toward edges (less in center, more on sides).
  double _pushToEdge(double x, double maxAbs) {
    final sign = x >= 0 ? 1.0 : -1.0;
    final absX = x.abs();
    // If close to center, push toward edge; otherwise keep or slightly amplify
    if (absX < maxAbs * 0.3) {
      return sign * maxAbs * 0.35;
    }
    // Slightly amplify values that are already away from center
    return sign * (absX * 1.15).clamp(0.0, maxAbs);
  }

  double get _offsetX {
    if (widget.poseSeed != null) {
      // Range ±0.4 so owl center can reach near left/right edges (0.1 to 0.9 of width)
      final rawOffset = ((widget.poseSeed! * 7) % 11 - 5) / 12.5;
      return _pushToEdge(rawOffset, 0.4);
    }
    // For banner without seed (first display), position at bottom-left corner
    if (widget.type == AdType.banner) {
      return -0.48; // Further left to avoid blocking text, can overflow beyond edge
    }
    return _pushToEdge(_randomOffsetX, 0.4);
  }

  double get _offsetY {
    double baseOffset;
    if (widget.poseSeed != null) {
      // Range ±0.2 for vertical variation
      baseOffset = ((widget.poseSeed! * 13) % 11 - 5) / 25.0;
    } else {
      baseOffset = _randomOffsetY;
    }
    // Push toward edges (top/bottom), less in center
    final edgeOffset = _pushToEdge(baseOffset, 0.2);
    // For banner without seed (first display), position at bottom-left corner
    if (widget.type == AdType.banner && widget.poseSeed == null) {
      return 0.42; // Bottom side, can overflow beyond edge
    }
    // For square/tall, bias downward to avoid text
    return _isWideBanner ? edgeOffset : edgeOffset + 0.15;
  }

  /// Owl scale factor (0.7..1.3) so size varies; derived from poseSeed when set.
  double get _owlScaleFactor {
    if (widget.poseSeed != null) {
      return 0.7 + ((widget.poseSeed! * 17) % 7) / 7.0 * 0.6;
    }
    return _randomOwlScaleFactor;
  }

  /// Slogan horizontal alignment; prefer opposite side of owl to reduce overlap.
  TextAlign get _sloganAlign {
    final ox = _offsetX;
    if (ox < -0.15) return TextAlign.right;
    if (ox > 0.15) return TextAlign.left;
    if (widget.poseSeed != null) {
      final n = (widget.poseSeed! * 19) % 3;
      return <TextAlign>[TextAlign.left, TextAlign.center, TextAlign.right][n];
    }
    return _randomSloganAlign;
  }

  /// Slogan bottom padding (4, 8, or 12).
  double get _sloganBottom {
    if (widget.poseSeed != null) {
      return 4.0 + ((widget.poseSeed! * 23) % 3) * 4.0;
    }
    return _randomSloganBottom;
  }

  /// Default banner slogan (two lines for first display)
  static const String _defaultBannerSloganLine1 =
      'Make translation easy! Earn a little bit if possible';
  static const String _defaultBannerSloganLine2 =
      'Lose if necessary, but make translation a piece of cake!';

  /// Slogan text; changes when poseSeed changes. Banner uses two-line default slogan only on first display.
  String get _slogan {
    // Banner: two-line default slogan only on first display (no seed), then random from list
    if (widget.type == AdType.banner) {
      // For first display (no seed), return empty string (will use two-line layout)
      if (widget.poseSeed == null) {
        return '';
      }
      // For subsequent displays, select from list based on seed
      final index = (widget.poseSeed! * 31) % kAdPlaceholderSlogans.length;
      return kAdPlaceholderSlogans[index];
    }
    // Other types: use seed-based or random selection
    if (widget.poseSeed != null) {
      final index = (widget.poseSeed! * 31) % kAdPlaceholderSlogans.length;
      return kAdPlaceholderSlogans[index];
    }
    return _randomSlogan;
  }

  /// Whether to show two-line default banner slogan (first display only)
  bool get _showTwoLineBannerSlogan =>
      widget.type == AdType.banner && widget.poseSeed == null;

  @override
  Widget build(BuildContext context) {
    if (!kAdsEnabled || !_isVisible) {
      return const SizedBox.shrink();
    }

    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final colorScheme = theme.colorScheme;
    // Use theme colors for coordination with main page; softer contrast
    final borderColor = colorScheme.outlineVariant.withOpacity(0.8);
    final backgroundColor = isDark
        ? colorScheme.surfaceContainerHighest.withOpacity(0.4)
        : colorScheme.surfaceContainerLow.withOpacity(0.6);
    // Owl color: keep unchanged (sky blue, relaxed)
    final owlColor =
        isDark ? Colors.lightBlue.shade200 : Colors.lightBlue.shade400;
    // Slogan text color: match home screen blue (drawn on top of owl so not obscured)
    final sloganColor = isDark ? Colors.blue.shade300 : Colors.blue.shade700;

    final sloganFontSize = (widget.height * 0.22).clamp(14.0, 28.0);
    // Dynamic font sizes for two-line default banner slogan, based on height with min/max limits
    final double baseTwoLineSize = (widget.height * 0.25).clamp(12.0, 20.0);
    final double firstLineFontSize = baseTwoLineSize;
    final double secondLineFontSize = (baseTwoLineSize + 4.0).clamp(16.0, 24.0);
    // For square/tall rectangles, reserve top area for text to avoid overlap
    final textAreaHeight = _isWideBanner ? 0.0 : widget.height * 0.25;
    final owlHeight = widget.height * 0.8;
    final owlBottomOverflow = widget.height * 0.2;
    final owlPaintHeight = owlHeight + owlBottomOverflow;

    return Stack(
      clipBehavior: Clip.none,
      children: <Widget>[
        Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            color: backgroundColor,
            border: Border.all(color: borderColor),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Stack(
            clipBehavior: Clip.none,
            children: <Widget>[
              Positioned(
                left: 0,
                top: textAreaHeight,
                right: 0,
                height: owlPaintHeight,
                child: CustomPaint(
                  painter: _OwlPainter(
                    color: owlColor,
                    isWideBanner: _isWideBanner,
                    poseIndex: _poseIndex,
                    offsetX: _offsetX,
                    offsetY: _offsetY,
                    scaleFactor: _owlScaleFactor,
                  ),
                  size: Size(widget.width, owlPaintHeight),
                ),
              ),
            ],
          ),
        ),
        Positioned(
          top: 4,
          right: 4,
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: _handleClose,
              // Match circular 20x20 hit target (radius 10) so ripple clips as a circle.
              borderRadius: BorderRadius.circular(10),
              child: Container(
                width: 20,
                height: 20,
                decoration: BoxDecoration(
                  color: colorScheme.surfaceContainerHighest,
                  shape: BoxShape.circle,
                  border: Border.all(color: borderColor),
                ),
                child: Icon(
                  Icons.close,
                  size: 14,
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ),
        ),
        // Slogan drawn on top of owl so text is not obscured; color matches home screen
        Positioned(
          left: 8,
          right: 8,
          top: _sloganBottom,
          child: _showTwoLineBannerSlogan
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Text(
                      _defaultBannerSloganLine1,
                      style: TextStyle(
                        color: sloganColor,
                        fontSize: firstLineFontSize,
                        fontWeight: FontWeight.w500,
                        letterSpacing: 0.5,
                      ),
                      textAlign: TextAlign.left,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    Text(
                      _defaultBannerSloganLine2,
                      style: TextStyle(
                        color: sloganColor,
                        fontSize: secondLineFontSize,
                        fontWeight: FontWeight.w500,
                        letterSpacing: 0.5,
                      ),
                      textAlign: TextAlign.right,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                )
              : Text(
                  _slogan,
                  style: TextStyle(
                    color: sloganColor,
                    fontSize: sloganFontSize,
                    fontWeight: FontWeight.w500,
                    letterSpacing: 0.5,
                  ),
                  textAlign: _sloganAlign,
                  maxLines: 5,
                  overflow: TextOverflow.ellipsis,
                ),
        ),
      ],
    );
  }
}

/// Paints a simple owl; pose, position and size vary by poseIndex, offset and scaleFactor.
class _OwlPainter extends CustomPainter {
  _OwlPainter({
    required this.color,
    required this.isWideBanner,
    required this.poseIndex,
    required this.offsetX,
    required this.offsetY,
    this.scaleFactor = 1.0,
  });
  final Color color;
  final bool isWideBanner;
  final int poseIndex;
  final double offsetX;
  final double offsetY;
  final double scaleFactor;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color;
    final stroke = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = size.shortestSide * 0.04;

    // Larger base scale so owl is more prominent; wide banner uses bigger base, overflow allowed
    final baseScale = isWideBanner ? 0.48 : 0.40;
    final scale = size.shortestSide * baseScale * scaleFactor;
    final cx = size.width * (0.5 + offsetX);
    final cy = size.height * (0.5 + offsetY);

    switch (poseIndex % kOwlPoseCount) {
      case 0:
        _drawOwlFront(canvas, cx, cy, scale, paint, stroke);
        break;
      case 1:
        _drawOwlTilted(canvas, cx, cy, scale, paint, stroke);
        break;
      case 2:
        _drawOwlLying(canvas, cx, cy, scale, paint, stroke);
        break;
      case 3:
        _drawOwlPlaying(canvas, cx, cy, scale, paint, stroke);
        break;
      case 4:
        _drawOwlSleeping(canvas, cx, cy, scale, paint, stroke);
        break;
      case 5:
        _drawOwlWaving(canvas, cx, cy, scale, paint, stroke);
        break;
      case 6:
        _drawOwlSitting(canvas, cx, cy, scale, paint, stroke);
        break;
      case 7:
        _drawOwlBack(canvas, cx, cy, scale, paint, stroke);
        break;
      case 8:
        _drawOwlBigEyes(canvas, cx, cy, scale, paint, stroke);
        break;
      case 9:
        _drawOwlLogo(canvas, cx, cy, scale, paint, stroke);
        break;
      default:
        _drawOwlFront(canvas, cx, cy, scale, paint, stroke);
    }
  }

  void _drawOwlFront(
    Canvas canvas,
    double cx,
    double cy,
    double s,
    Paint fill,
    Paint stroke,
  ) {
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.2),
        width: s * 1.4,
        height: s * 1.1,
      ),
      fill,
    );
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.2),
        width: s * 1.4,
        height: s * 1.1,
      ),
      stroke,
    );
    canvas.drawCircle(Offset(cx, cy - s * 0.5), s * 0.55, fill);
    canvas.drawCircle(Offset(cx, cy - s * 0.5), s * 0.55, stroke);
    _drawEarTufts(canvas, cx, cy, s, true, true, fill, stroke);
    // Big eyes for front-facing pose
    _drawEyes(canvas, cx, cy - s * 0.05, s * 1.2, false, fill, stroke);
    _drawBeak(canvas, cx, cy - s * 0.35, s, fill, stroke);
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx - s * 0.5, cy + s * 0.1),
        width: s * 0.6,
        height: s * 0.7,
      ),
      -0.3 * pi,
      0.6 * pi,
      false,
      stroke,
    );
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx + s * 0.5, cy + s * 0.1),
        width: s * 0.6,
        height: s * 0.7,
      ),
      0.7 * pi,
      0.6 * pi,
      false,
      stroke,
    );
  }

  void _drawOwlTilted(
    Canvas canvas,
    double cx,
    double cy,
    double s,
    Paint fill,
    Paint stroke,
  ) {
    final cxL = cx - s * 0.15;
    final cyL = cy - s * 0.1;
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.35),
        width: s * 1.3,
        height: s * 1.2,
      ),
      fill,
    );
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.35),
        width: s * 1.3,
        height: s * 1.2,
      ),
      stroke,
    );
    canvas.drawCircle(Offset(cxL, cyL - s * 0.5), s * 0.5, fill);
    canvas.drawCircle(Offset(cxL, cyL - s * 0.5), s * 0.5, stroke);
    _drawEarTufts(canvas, cxL, cyL, s, true, true, fill, stroke);
    _drawEyes(canvas, cxL, cyL - s * 0.05, s, false, fill, stroke);
    _drawBeak(canvas, cxL, cyL - s * 0.32, s, fill, stroke);
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cxL + s * 0.55, cyL + s * 0.05),
        width: s * 0.5,
        height: s * 0.85,
      ),
      0.5 * pi,
      0.85 * pi,
      false,
      stroke,
    );
  }

  void _drawOwlLying(
    Canvas canvas,
    double cx,
    double cy,
    double s,
    Paint fill,
    Paint stroke,
  ) {
    canvas.save();
    // Cat-like side lying: head left, body right (horizontal), no rotation so it appears lying on its side
    final cx2 = cx;
    final cy2 = cy + s * 0.2;
    // Cat-like elongated body, lying flat on side
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx2, cy2),
        width: s * 1.8,
        height: s * 0.65,
      ),
      fill,
    );
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx2, cy2),
        width: s * 1.8,
        height: s * 0.65,
      ),
      stroke,
    );
    // Head resting on side, slightly tilted
    canvas.drawCircle(Offset(cx2 - s * 0.5, cy2), s * 0.45, fill);
    canvas.drawCircle(Offset(cx2 - s * 0.5, cy2), s * 0.45, stroke);
    // Relaxed ear tufts, lying flat
    _drawEarTufts(
      canvas,
      cx2 - s * 0.5,
      cy2,
      s * 0.8,
      true,
      true,
      fill,
      stroke,
    );
    // Half-closed, lazy eyes
    _drawEyes(canvas, cx2 - s * 0.5, cy2, s * 0.85, true, fill, stroke);
    // Small relaxed beak
    _drawBeak(canvas, cx2 - s * 0.5, cy2 + s * 0.15, s * 0.8, fill, stroke);
    // Front "paw" (wing) curled, cat-like
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx2 + s * 0.3, cy2 - s * 0.1),
        width: s * 0.5,
        height: s * 0.4,
      ),
      -0.3 * pi,
      0.5 * pi,
      false,
      stroke,
    );
    // Back "paw" (wing) extended, relaxed
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx2 + s * 0.6, cy2 + s * 0.15),
        width: s * 0.4,
        height: s * 0.35,
      ),
      0.2 * pi,
      0.4 * pi,
      false,
      stroke,
    );
    canvas.restore();
  }

  void _drawOwlPlaying(
    Canvas canvas,
    double cx,
    double cy,
    double s,
    Paint fill,
    Paint stroke,
  ) {
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.25),
        width: s * 1.2,
        height: s * 1.0,
      ),
      fill,
    );
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.25),
        width: s * 1.2,
        height: s * 1.0,
      ),
      stroke,
    );
    canvas.drawCircle(Offset(cx, cy - s * 0.55), s * 0.5, fill);
    canvas.drawCircle(Offset(cx, cy - s * 0.55), s * 0.5, stroke);
    _drawEarTufts(canvas, cx, cy - s * 0.05, s, true, true, fill, stroke);
    _drawEyes(canvas, cx, cy - s * 0.6, s, false, fill, stroke);
    _drawBeak(canvas, cx, cy - s * 0.4, s, fill, stroke);
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx - s * 0.45, cy - s * 0.2),
        width: s * 0.5,
        height: s * 0.9,
      ),
      -0.5 * pi,
      0.7 * pi,
      false,
      stroke,
    );
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx + s * 0.45, cy - s * 0.2),
        width: s * 0.5,
        height: s * 0.9,
      ),
      0.2 * pi,
      0.7 * pi,
      false,
      stroke,
    );
  }

  void _drawOwlSleeping(
    Canvas canvas,
    double cx,
    double cy,
    double s,
    Paint fill,
    Paint stroke,
  ) {
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.3),
        width: s * 1.3,
        height: s * 1.1,
      ),
      fill,
    );
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.3),
        width: s * 1.3,
        height: s * 1.1,
      ),
      stroke,
    );
    canvas.drawCircle(Offset(cx, cy - s * 0.45), s * 0.5, fill);
    canvas.drawCircle(Offset(cx, cy - s * 0.45), s * 0.5, stroke);
    _drawEarTufts(canvas, cx, cy + s * 0.05, s, true, true, fill, stroke);
    _drawEyes(canvas, cx, cy - s * 0.5, s, true, fill, stroke);
    _drawBeak(canvas, cx, cy - s * 0.28, s, fill, stroke);
  }

  void _drawOwlWaving(
    Canvas canvas,
    double cx,
    double cy,
    double s,
    Paint fill,
    Paint stroke,
  ) {
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.2),
        width: s * 1.3,
        height: s * 1.1,
      ),
      fill,
    );
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.2),
        width: s * 1.3,
        height: s * 1.1,
      ),
      stroke,
    );
    canvas.drawCircle(Offset(cx, cy - s * 0.5), s * 0.52, fill);
    canvas.drawCircle(Offset(cx, cy - s * 0.5), s * 0.52, stroke);
    _drawEarTufts(canvas, cx, cy, s, true, true, fill, stroke);
    _drawEyes(canvas, cx, cy - s * 0.05, s, false, fill, stroke);
    _drawBeak(canvas, cx, cy - s * 0.32, s, fill, stroke);
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx - s * 0.5, cy + s * 0.05),
        width: s * 0.55,
        height: s * 0.75,
      ),
      -0.35 * pi,
      0.55 * pi,
      false,
      stroke,
    );
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx + s * 0.48, cy - s * 0.35),
        width: s * 0.5,
        height: s * 0.9,
      ),
      0.1 * pi,
      0.75 * pi,
      false,
      stroke,
    );
  }

  void _drawOwlSitting(
    Canvas canvas,
    double cx,
    double cy,
    double s,
    Paint fill,
    Paint stroke,
  ) {
    // Cat-like sitting pose: upright body, front paws together
    // Body: more upright and compact
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.15),
        width: s * 1.1,
        height: s * 1.0,
      ),
      fill,
    );
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.15),
        width: s * 1.1,
        height: s * 1.0,
      ),
      stroke,
    );
    // Head: upright, alert but relaxed
    canvas.drawCircle(Offset(cx, cy - s * 0.4), s * 0.5, fill);
    canvas.drawCircle(Offset(cx, cy - s * 0.4), s * 0.5, stroke);
    // Ear tufts: perked up but relaxed
    _drawEarTufts(canvas, cx, cy - s * 0.15, s, true, true, fill, stroke);
    // Eyes: open, calm and content
    _drawEyes(canvas, cx, cy - s * 0.45, s, false, fill, stroke);
    // Beak: small and relaxed
    _drawBeak(canvas, cx, cy - s * 0.3, s, fill, stroke);
    // Front "paws" (wings) together in front, cat-like sitting position
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx - s * 0.25, cy + s * 0.25),
        width: s * 0.4,
        height: s * 0.5,
      ),
      -0.2 * pi,
      0.5 * pi,
      false,
      stroke,
    );
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx + s * 0.25, cy + s * 0.25),
        width: s * 0.4,
        height: s * 0.5,
      ),
      0.7 * pi,
      0.5 * pi,
      false,
      stroke,
    );
    // Back "paws" (wings) tucked under, sitting position
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx - s * 0.3, cy + s * 0.5),
        width: s * 0.35,
        height: s * 0.4,
      ),
      0.3 * pi,
      0.4 * pi,
      false,
      stroke,
    );
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx + s * 0.3, cy + s * 0.5),
        width: s * 0.35,
        height: s * 0.4,
      ),
      0.3 * pi,
      0.4 * pi,
      false,
      stroke,
    );
  }

  void _drawOwlBack(
    Canvas canvas,
    double cx,
    double cy,
    double s,
    Paint fill,
    Paint stroke,
  ) {
    // Back-facing pose: no eyes, only body and head outline
    // Body
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.2),
        width: s * 1.3,
        height: s * 1.1,
      ),
      fill,
    );
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.2),
        width: s * 1.3,
        height: s * 1.1,
      ),
      stroke,
    );
    // Head (back view, no face details)
    canvas.drawCircle(Offset(cx, cy - s * 0.5), s * 0.5, fill);
    canvas.drawCircle(Offset(cx, cy - s * 0.5), s * 0.5, stroke);
    // Ear tufts visible from back
    _drawEarTufts(canvas, cx, cy, s, true, true, fill, stroke);
    // Wings (back view)
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx - s * 0.5, cy + s * 0.1),
        width: s * 0.6,
        height: s * 0.7,
      ),
      -0.3 * pi,
      0.6 * pi,
      false,
      stroke,
    );
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx + s * 0.5, cy + s * 0.1),
        width: s * 0.6,
        height: s * 0.7,
      ),
      0.7 * pi,
      0.6 * pi,
      false,
      stroke,
    );
    // No eyes, no beak for back view
  }

  void _drawOwlBigEyes(
    Canvas canvas,
    double cx,
    double cy,
    double s,
    Paint fill,
    Paint stroke,
  ) {
    // Front-facing owl with very prominent, large eyes (alert/cute look)
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.2),
        width: s * 1.4,
        height: s * 1.1,
      ),
      fill,
    );
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, cy + s * 0.2),
        width: s * 1.4,
        height: s * 1.1,
      ),
      stroke,
    );
    canvas.drawCircle(Offset(cx, cy - s * 0.5), s * 0.55, fill);
    canvas.drawCircle(Offset(cx, cy - s * 0.5), s * 0.55, stroke);
    _drawEarTufts(canvas, cx, cy, s, true, true, fill, stroke);
    _drawEyesProminent(canvas, cx, cy - s * 0.05, s, fill, stroke);
    _drawBeak(canvas, cx, cy - s * 0.35, s, fill, stroke);
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx - s * 0.5, cy + s * 0.1),
        width: s * 0.6,
        height: s * 0.7,
      ),
      -0.3 * pi,
      0.6 * pi,
      false,
      stroke,
    );
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx + s * 0.5, cy + s * 0.1),
        width: s * 0.6,
        height: s * 0.7,
      ),
      0.7 * pi,
      0.6 * pi,
      false,
      stroke,
    );
  }

  void _drawEyesProminent(
    Canvas canvas,
    double cx,
    double cy,
    double s,
    Paint fill,
    Paint stroke,
  ) {
    // Larger eyes with white sclera (留白) so eyes are visible against the head
    const eyeScale = 1.5;
    final outerR = s * 0.2 * eyeScale;
    final pupilR = s * 0.08 * eyeScale;
    final spacing = s * 0.44;
    final leftC = Offset(cx - spacing * 0.5, cy);
    final rightC = Offset(cx + spacing * 0.5, cy);
    final eyeWhite = Paint()..color = Colors.white;
    // Eye white first, then outline, then pupil
    canvas.drawCircle(leftC, outerR, eyeWhite);
    canvas.drawCircle(rightC, outerR, eyeWhite);
    canvas.drawCircle(leftC, outerR, stroke);
    canvas.drawCircle(rightC, outerR, stroke);
    canvas.drawCircle(leftC, pupilR, fill);
    canvas.drawCircle(rightC, pupilR, fill);
  }

  /// Logo-style owl (from owlangs_owl_solid.svg): head arc, large ellipses eyes, beak, rounded body.
  /// Uses same orange color as other poses.
  void _drawOwlLogo(
    Canvas canvas,
    double cx,
    double cy,
    double s,
    Paint fill,
    Paint stroke,
  ) {
    // Eyes: two ellipses (logo proportions)
    final eyeRx = s * 0.31;
    final eyeRy = s * 0.31;
    final leftEyeC = Offset(cx - s * 0.35, cy - s * 0.57);
    final rightEyeC = Offset(cx + s * 0.37, cy - s * 0.57);
    canvas.drawOval(
      Rect.fromCenter(center: leftEyeC, width: eyeRx * 2, height: eyeRy * 2),
      stroke,
    );
    canvas.drawOval(
      Rect.fromCenter(center: rightEyeC, width: eyeRx * 2, height: eyeRy * 2),
      stroke,
    );
    // Pupils (solid fill)
    final pr = s * 0.1;
    canvas.drawCircle(leftEyeC, pr, fill);
    canvas.drawCircle(rightEyeC, pr, fill);
    // Beak: inverted triangle (base at top, point at bottom)
    final beakPath = Path()
      ..moveTo(cx - s * 0.2, cy - s * 0.29)
      ..lineTo(cx + s * 0.2, cy - s * 0.29)
      ..lineTo(cx, cy - s * 0.07)
      ..close();
    canvas.drawPath(beakPath, stroke);
    // Body: rounded fill (logo body shape), same orange as other owls
    final bodyPath = Path()
      ..moveTo(cx - s * 0.75, cy - s * 0.05)
      ..quadraticBezierTo(
        cx - s * 0.95,
        cy + s * 0.2,
        cx - s * 0.5,
        cy + s * 0.45,
      )
      ..lineTo(cx + s * 0.5, cy + s * 0.45)
      ..quadraticBezierTo(
        cx + s * 0.95,
        cy + s * 0.2,
        cx + s * 0.75,
        cy - s * 0.05,
      )
      ..close();
    canvas.drawPath(bodyPath, fill);
    // Body outline curve (left arc only; right arc removed to avoid extra line by right foot)
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset(cx - s * 0.5, cy + s * 0.15),
        width: s * 0.5,
        height: s * 0.9,
      ),
      -0.5 * pi,
      0.7 * pi,
      false,
      stroke,
    );
    // Legs (short lines like logo)
    canvas.drawLine(
      Offset(cx - s * 0.4, cy + s * 0.45),
      Offset(cx - s * 0.45, cy + s * 0.55),
      stroke,
    );
    canvas.drawLine(
      Offset(cx + s * 0.4, cy + s * 0.45),
      Offset(cx + s * 0.45, cy + s * 0.55),
      stroke,
    );
  }

  void _drawEarTufts(
    Canvas canvas,
    double cx,
    double cy,
    double s,
    bool left,
    bool right,
    Paint fill,
    Paint stroke,
  ) {
    if (left) {
      final pathL = Path()
        ..moveTo(cx - s * 0.35, cy - s * 0.95)
        ..lineTo(cx - s * 0.55, cy - s * 1.35)
        ..lineTo(cx - s * 0.15, cy - s * 0.95)
        ..close();
      canvas.drawPath(pathL, fill);
      canvas.drawPath(pathL, stroke);
    }
    if (right) {
      final pathR = Path()
        ..moveTo(cx + s * 0.35, cy - s * 0.95)
        ..lineTo(cx + s * 0.55, cy - s * 1.35)
        ..lineTo(cx + s * 0.15, cy - s * 0.95)
        ..close();
      canvas.drawPath(pathR, fill);
      canvas.drawPath(pathR, stroke);
    }
  }

  void _drawEyes(
    Canvas canvas,
    double cx,
    double cy,
    double s,
    bool closed,
    Paint fill,
    Paint stroke,
  ) {
    if (closed) {
      canvas.drawLine(
        Offset(cx - s * 0.22, cy),
        Offset(cx - s * 0.08, cy),
        stroke,
      );
      canvas.drawLine(
        Offset(cx + s * 0.08, cy),
        Offset(cx + s * 0.22, cy),
        stroke,
      );
      return;
    }
    canvas.drawCircle(Offset(cx - s * 0.2, cy), s * 0.2, stroke);
    canvas.drawCircle(Offset(cx + s * 0.2, cy), s * 0.2, stroke);
    canvas.drawCircle(Offset(cx - s * 0.2, cy), s * 0.08, fill);
    canvas.drawCircle(Offset(cx + s * 0.2, cy), s * 0.08, fill);
  }

  void _drawBeak(
    Canvas canvas,
    double cx,
    double cy,
    double s,
    Paint fill,
    Paint stroke,
  ) {
    final beak = Path()
      ..moveTo(cx, cy)
      ..lineTo(cx - s * 0.1, cy + s * 0.2)
      ..lineTo(cx + s * 0.1, cy + s * 0.2)
      ..close();
    canvas.drawPath(beak, fill);
    canvas.drawPath(beak, stroke);
  }

  @override
  bool shouldRepaint(covariant _OwlPainter oldDelegate) =>
      oldDelegate.poseIndex != poseIndex ||
      oldDelegate.offsetX != offsetX ||
      oldDelegate.offsetY != offsetY ||
      oldDelegate.scaleFactor != scaleFactor ||
      oldDelegate.color != color;
}

/// Ad type enumeration
enum AdType {
  banner,
  rectangle,
  square,
  skyscraper,
}
