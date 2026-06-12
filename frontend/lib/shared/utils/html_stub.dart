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

class StyleElement extends Element {
  String text = '';
}

class Document {
  Element? get head => null;
  BodyElement? get body => null;
  Element? getElementById(String id) => null;
  List<Element> querySelectorAll(String selector) => <Element>[];
  Element? querySelector(String selector) => null;
  Element? get scrollingElement => null;
  Element? get documentElement => null;
  void addEventListener(String type, EventListener? callback, [bool? useCapture]) {}
  void removeEventListener(String type, EventListener? callback, [bool? useCapture]) {}
}

class BodyElement extends Element {
  @override
  void append(element) {}
}

class Element {
  String? id;
  String? get src => null;
  bool hasAttribute(String name) => false;
  Element? querySelector(String selector) => null;
  List<Element> querySelectorAll(String selector) => <Element>[];
  List<Element> get children => <Element>[];
  dynamic style;
  void append(node) {}
  void remove() {}
  num get scrollTop => 0;
  set scrollTop(num value) {}
  num get scrollLeft => 0;
  set scrollLeft(num value) {}
  num get scrollHeight => 0;
  num get clientHeight => 0;
  num get scrollWidth => 0;
  num get clientWidth => 0;
}

class IFrameElement extends Element {
  @override
  String? src;
  bool allowFullscreen = false;
  WindowBase? get contentWindow => null;
  Stream<Event> get onLoad => const Stream.empty();
  void setAttribute(String name, String value) {}
}

abstract class WindowBase {
  void postMessage(
    Object? message,
    String targetOrigin, [
    List<Object>? transfer,
  ]) {}
}

class Window implements WindowBase {
  Document get document => _stubDocument;
  Navigator get navigator => Navigator();
  void requestAnimationFrame(Function callback) {}
  void addEventListener(String type, EventListener? callback, [bool? useCapture]) {}
  void removeEventListener(String type, EventListener? callback, [bool? useCapture]) {}

  @override
  void postMessage(
    Object? message,
    String targetOrigin, [
    List<Object>? transfer,
  ]) {}
}

final Document _stubDocument = Document();

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
  Blob([List? parts, String? type, String? endings]);
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
