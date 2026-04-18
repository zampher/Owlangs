// Stub file for non-web platforms
// This file provides stub implementations for dart:ui_web when not on web platform

class PlatformViewRegistry {
  static void registerViewFactory(String viewTypeId, viewFactory) {
    // No-op on non-web platforms
  }
}

final PlatformViewRegistry platformViewRegistry = PlatformViewRegistry();
