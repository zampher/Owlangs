// SPDX-FileCopyrightText: 2025 QinHan
// SPDX-License-Identifier: MPL-2.0

/// Stub for dart:html on non-web platforms (Windows desktop, etc.).
/// Used when dart.library.html is false. All code paths using html/* on desktop
/// are guarded by kIsWeb, so these stubs are never called at runtime.
library;

import 'dart:async';

class ScriptElement {
  String text = '';
  void remove() {}
}

class Document {
  BodyElement? get body => null;
  Element? getElementById(String id) => null;
  List<Element> querySelectorAll(String selector) => <Element>[];
  Element? querySelector(String selector) => null;
}

class BodyElement {
  void append(element) {}
}

class Element {
  String? id;
  String? get src => null;
  bool hasAttribute(String name) => false;
  Element? querySelector(String selector) => null;
  List<Element> querySelectorAll(String selector) => <Element>[];
  dynamic style;
  void append(node) {}
}

class IFrameElement extends Element {
  @override
  String? src;
  bool allowFullscreen = false;
  void setAttribute(String name, String value) {}
}

class Event {
  void preventDefault() {}
  void stopPropagation() {}
}

class FileReader {
  static const int DONE = 2;
  Stream get onLoadEnd => const Stream.empty();
  Stream get onError => const Stream.empty();
  dynamic get result => null;
  int get readyState => 0;
  void readAsArrayBuffer(blob) {}
}

class Blob {
  /// Matches dart:html Blob(List parts, [String? type, String? endings]).
  Blob();
}

class Url {
  static String createObjectUrlFromBlob(Blob blob) => '';
  static void revokeObjectUrl(String url) {}
}

final Document _documentInstance = Document();
final Document document = _documentInstance;
final Window window = Window();

class Clipboard {
  Future<void> writeText(String text) async {}
}

class Navigator {
  String get userAgent => '';
  Clipboard? get clipboard => null;
}

/// Stub for dart:html EventListener on non-web (callback type for addEventListener).
typedef EventListener = void Function(Event event);

class Window {
  void requestAnimationFrame(Function callback) {}
  void addEventListener(String type, EventListener? callback) {}
  void removeEventListener(String type, EventListener? callback) {}
  Document get document => _documentInstance;
  Navigator get navigator => Navigator();
}
