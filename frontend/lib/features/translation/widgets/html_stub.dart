// Stub file for non-web platforms
// This file provides stub implementations for dart:html when not on web platform

class IFrameElement {
  IFrameElement() {
    style = Style();
  }
  String? src;
  Style? style;
  bool? allowFullscreen;
}

class Style {
  String? border;
  String? width;
  String? height;
}

class Blob {
  Blob([List? parts, String? type, String? endings]);
}

class Url {
  static String createObjectUrlFromBlob(Blob blob) => '';
}
